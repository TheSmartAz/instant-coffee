"""Tests for DeferredPersistenceBuffer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.engine.deferred_buffer import DeferredPersistenceBuffer


class TestRecording:
    """Buffer correctly captures and overwrites product-doc entries."""

    def test_record_product_doc_last_write_wins(self):
        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "v1")
        buf.record_product_doc("PRODUCT.md", "v2")
        buf.record_product_doc("PRODUCT.md", "v3")
        assert buf._product_doc is not None
        assert buf._product_doc.content == "v3"

    def test_has_pending(self):
        buf = DeferredPersistenceBuffer()
        assert not buf.has_pending

        buf.record_product_doc("PRODUCT.md", "content")
        assert buf.has_pending


class TestClear:
    """clear() discards buffered writes."""

    def test_clear_discards_everything(self):
        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "content")
        assert buf.has_pending

        buf.clear()
        assert not buf.has_pending
        assert buf._product_doc is None


class TestFlush:
    """flush() persists the product doc exactly once."""

    @patch("app.engine.deferred_buffer.DeferredPersistenceBuffer._flush_product_doc")
    def test_flush_product_doc_called_once(self, mock_flush_pd):
        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "v1")
        buf.record_product_doc("PRODUCT.md", "v2")
        buf.record_product_doc("PRODUCT.md", "v3")

        db = MagicMock()
        buf.flush(db, "session-1", emitter=None)

        mock_flush_pd.assert_called_once_with(db, "session-1", None)

    def test_flush_clears_buffer(self):
        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "content")

        with patch.object(buf, "_flush_product_doc"):
            buf.flush(MagicMock(), "session-1", emitter=None)

        assert not buf.has_pending

    def test_flush_with_no_db_clears_without_persisting(self):
        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "content")

        buf.flush(None, "session-1", emitter=None)
        assert not buf.has_pending

    @patch("app.engine.deferred_buffer.DeferredPersistenceBuffer._flush_product_doc")
    def test_flush_clears_on_product_doc_error(self, mock_flush_pd):
        mock_flush_pd.side_effect = Exception("DB error")

        buf = DeferredPersistenceBuffer()
        buf.record_product_doc("PRODUCT.md", "content")

        buf.flush(MagicMock(), "session-1", emitter=None)

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
