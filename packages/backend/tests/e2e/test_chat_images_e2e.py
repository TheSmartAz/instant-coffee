import pytest
from fastapi.testclient import TestClient

from app.agents.orchestrator import AgentOrchestrator, OrchestratorResponse


class TestChatImagesE2E:
    def _patch_stream(self, monkeypatch, capture):
        async def fake_stream_responses(self, **kwargs):
            capture.update(kwargs)
            yield OrchestratorResponse(
                session_id=self.session.id,
                phase="product_doc",
                message="ok",
                is_complete=True,
                action="product_doc_generated",
            )

        monkeypatch.setattr(AgentOrchestrator, "stream_responses", fake_stream_responses)

    def test_images_field_accepts_zero_to_three_images(self, test_client, monkeypatch, sample_png_base64):
        capture = {}
        self._patch_stream(monkeypatch, capture)

        response1 = test_client.post(
            "/api/chat",
            json={"message": "Create a landing page", "images": []},
        )
        assert response1.status_code == 200

        response2 = test_client.post(
            "/api/chat",
            json={"message": "Create a landing page", "images": [sample_png_base64]},
        )
        assert response2.status_code == 200

        response3 = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": [sample_png_base64, sample_png_base64, sample_png_base64],
            },
        )
        assert response3.status_code == 200

    def test_more_than_three_images_rejected(self, test_client, sample_png_base64):
        response = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": [
                    sample_png_base64,
                    sample_png_base64,
                    sample_png_base64,
                    sample_png_base64,
                ],
            },
        )
        assert response.status_code == 422

    def test_images_can_be_base64_or_urls(self, test_client, monkeypatch, sample_png_base64):
        capture = {}
        self._patch_stream(monkeypatch, capture)

        response1 = test_client.post(
            "/api/chat",
            json={"message": "Create a landing page", "images": [sample_png_base64]},
        )
        assert response1.status_code == 200

        response2 = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": ["https://example.com/style.png"],
            },
        )
        assert response2.status_code == 200

        response3 = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": [sample_png_base64, "https://example.com/style.png"],
            },
        )
        assert response3.status_code == 200

    def test_target_pages_optional_defaults_to_empty(self, test_client, monkeypatch):
        capture = {}
        self._patch_stream(monkeypatch, capture)

        response = test_client.post(
            "/api/chat",
            json={"message": "Create a landing page"},
        )

        assert response.status_code == 200
        assert capture.get("target_pages") == []

    def test_style_reference_mode_defaults_to_full_mimic(self, test_client, monkeypatch, sample_png_base64):
        capture = {}
        self._patch_stream(monkeypatch, capture)

        response = test_client.post(
            "/api/chat",
            json={"message": "Create a landing page", "images": [sample_png_base64]},
        )

        assert response.status_code == 200
        assert capture.get("style_reference", {}).get("mode") == "full_mimic"

    def test_style_reference_mode_can_be_explicit(self, test_client, monkeypatch, sample_png_base64):
        capture = {}
        self._patch_stream(monkeypatch, capture)

        response = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "style_reference_mode": "style_only",
                "images": [sample_png_base64],
            },
        )

        assert response.status_code == 200
        assert capture.get("style_reference", {}).get("mode") == "style_only"

    def test_combined_images_and_style_reference(self, test_client, monkeypatch, sample_png_base64):
        capture = {}
        self._patch_stream(monkeypatch, capture)

        response = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": [sample_png_base64],
                "style_reference": {
                    "mode": "full_mimic",
                    "images": [sample_png_base64],
                },
            },
        )

        assert response.status_code == 200

    def test_combined_exceeds_max_rejected(self, test_client, sample_png_base64):
        response = test_client.post(
            "/api/chat",
            json={
                "message": "Create a landing page",
                "images": [sample_png_base64, sample_png_base64],
                "style_reference": {
                    "mode": "full_mimic",
                    "images": [sample_png_base64, sample_png_base64],
                },
            },
        )

        assert response.status_code == 422
