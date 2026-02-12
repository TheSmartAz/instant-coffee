"""Tests for DeferredPersistenceBuffer."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from app.engine.deferred_buffer import DeferredPersistenceBuffer


class TestRecording:
    """Buffer correctly captures and overwrites entries."""

    def test_record_product_doc_last_write_wins(self):
        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "v1")
        buf.record_product_doc("PRODUCT.md", "v2")
        buf.record_product_doc("PRODUCT.md", "v3")
        assert buf._product_doc is not None
        assert buf._product_doc.content == "v3"

    def test_record_html_last_write_wins_per_slug(self):
        buf = DeferredPersistenceBuffer()
        buf.record_html("landing.html", "<h1>v1</h1>", "landing")
        buf.record_html("landing.html", "<h1>v2</h1>", "landing")
        assert len(buf._html) == 1
        assert buf._html["landing"].content == "<h1>v2</h1>"

    def test_multiple_slugs_independent(self):
        buf = DeferredPersistenceBuffer()
        buf.record_html("landing.html", "<h1>Landing</h1>", "landing")
        buf.record_html("about.html", "<h1>About</h1>", "about")
        assert len(buf._html) == 2
        assert buf._html["landing"].content == "<h1>Landing</h1>"
        assert buf._html["about"].content == "<h1>About</h1>"

    def test_has_pending(self):
        buf = DeferredPersistenceBuffer()
        assert not buf.has_pending

        buf.record_product_doc("PRODUCT.md", "content")
        assert buf.has_pending

    def test_has_pending_html(self):
        buf = DeferredPersistenceBuffer()
        buf.record_html("index.html", "<h1>Hi</h1>", "index")
        assert buf.has_pending


class TestClear:
    """clear() discards all buffered writes."""

    def test_clear_discards_everything(self):
        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "content")
        buf.record_html("landing.html", "<h1>Hi</h1>", "landing")
        assert buf.has_pending

        buf.clear()
        assert not buf.has_pending
        assert buf._product_doc is None
        assert len(buf._html) == 0


class TestFlush:
    """flush() persists each key exactly once."""

    @patch("app.engine.deferred_buffer.DeferredPersistenceBuffer._flush_product_doc")
    def test_flush_product_doc_called_once(self, mock_flush_pd):
        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "v1")
        buf.record_product_doc("PRODUCT.md", "v2")
        buf.record_product_doc("PRODUCT.md", "v3")

        db = MagicMock()
        buf.flush(db, "session-1", emitter=None)

        mock_flush_pd.assert_called_once_with(db, "session-1", None)

    @patch("app.engine.deferred_buffer.DeferredPersistenceBuffer._flush_html")
    def test_flush_html_called_once_per_slug(self, mock_flush_html):
        buf = DeferredPersistenceBuffer()
        buf.record_html("landing.html", "<h1>v1</h1>", "landing")
        buf.record_html("landing.html", "<h1>v2</h1>", "landing")
        buf.record_html("about.html", "<h1>About</h1>", "about")

        db = MagicMock()
        buf.flush(db, "session-1", emitter=None)

        assert mock_flush_html.call_count == 2

    def test_flush_clears_buffer(self):
        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "content")
        buf.record_html("landing.html", "<h1>Hi</h1>", "landing")

        with patch.object(buf, "_flush_product_doc"), \
             patch.object(buf, "_flush_html"):
            buf.flush(MagicMock(), "session-1", emitter=None)

        assert not buf.has_pending

    def test_flush_with_no_db_clears_without_persisting(self):
        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "content")

        buf.flush(None, "session-1", emitter=None)
        assert not buf.has_pending

    @patch("app.engine.deferred_buffer.DeferredPersistenceBuffer._flush_product_doc")
    def test_flush_continues_on_product_doc_error(self, mock_flush_pd):
        """If product doc flush fails, HTML flush should still run."""
        mock_flush_pd.side_effect = Exception("DB error")

        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "content")
        buf.record_html("landing.html", "<h1>Hi</h1>", "landing")

        with patch.object(buf, "_flush_html") as mock_flush_html:
            buf.flush(MagicMock(), "session-1", emitter=None)
            mock_flush_html.assert_called_once()

        # Buffer should still be cleared
        assert not buf.has_pending


class TestFlushIntegration:
    """Integration-style tests using mocked services."""

    @patch("app.services.product_doc.ProductDocService", autospec=False)
    def test_flush_creates_new_product_doc(self, MockPDService):
        mock_svc = MagicMock()
        mock_svc.get_by_session_id.return_value = None
        MockPDService.return_value = mock_svc

        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "final content")

        db = MagicMock()
        buf.flush(db, "session-1", emitter=None)

        mock_svc.create.assert_called_once_with(
            session_id="session-1",
            content="final content",
            structured={},
        )
        db.commit.assert_called()

    @patch("app.services.product_doc.ProductDocService", autospec=False)
    def test_flush_updates_existing_product_doc(self, MockPDService):
        existing = MagicMock()
        existing.id = "doc-42"
        mock_svc = MagicMock()
        mock_svc.get_by_session_id.return_value = existing
        MockPDService.return_value = mock_svc

        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "updated content")

        db = MagicMock()
        buf.flush(db, "session-1", emitter=None)

        mock_svc.update.assert_called_once_with(
            "doc-42",
            content="updated content",
            change_summary="Updated via engine (deferred)",
        )

    @patch("app.engine.db_tools.persist_html_page")
    def test_flush_html_calls_persist_html_page(self, mock_persist):
        buf = DeferredPersistenceBuffer()
        buf.record_html("landing.html", "<h1>Final</h1>", "landing")

        db = MagicMock()
        emitter = MagicMock()
        buf.flush(db, "session-1", emitter=emitter)

        mock_persist.assert_called_once_with(
            db,
            "session-1",
            "landing.html",
            "<h1>Final</h1>",
            emitter=emitter,
            description="Generated by engine (deferred)",
        )
