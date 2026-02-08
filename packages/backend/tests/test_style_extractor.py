import asyncio
from pathlib import Path

from PIL import Image

from app.services.style_extractor import StyleExtractorService


def _write_sample_image(path: Path) -> None:
    image = Image.new("RGB", (32, 24), color=(20, 40, 200))
    image.save(path, format="PNG")


def test_style_extractor_fallback(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.png"
    _write_sample_image(image_path)

    service = StyleExtractorService(api_key="")
    tokens = asyncio.run(service.extract_style_tokens(str(image_path)))

    assert tokens is not None
    assert tokens.colors.primary.startswith("#")
    assert tokens.typography.scale in {"compact", "normal", "spacious"}
