import asyncio
import io
from pathlib import Path

from fastapi import UploadFile
from starlette.datastructures import Headers
from PIL import Image

from app.services.asset_registry import AssetRegistryService
from app.schemas.asset import AssetType


def _make_png_bytes(size=(12, 8), color=(120, 50, 200)) -> bytes:
    image = Image.new("RGB", size, color=color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_register_asset_png_and_registry(tmp_path: Path) -> None:
    service = AssetRegistryService("session-123", base_dir=tmp_path)
    payload = _make_png_bytes()
    file = UploadFile(
        file=io.BytesIO(payload),
        filename="logo.png",
        headers=Headers({"content-type": "image/png"}),
    )

    asset = asyncio.run(service.register_asset(file, AssetType.logo))

    assert asset.id.startswith("asset:logo_")
    assert asset.url.startswith("/assets/session-123/")
    assert asset.width == 12
    assert asset.height == 8

    registry = service.get_registry()
    assert registry.logo is not None
    assert registry.logo.id == asset.id

    asset_path = service.get_asset_path(asset.id)
    assert asset_path.exists()


def test_register_asset_svg_dimensions(tmp_path: Path) -> None:
    service = AssetRegistryService("session-456", base_dir=tmp_path)
    svg_payload = (
        b"<svg width=\"200\" height=\"100\" xmlns=\"http://www.w3.org/2000/svg\"></svg>"
    )
    file = UploadFile(
        file=io.BytesIO(svg_payload),
        filename="ref.svg",
        headers=Headers({"content-type": "image/svg+xml"}),
    )

    asset = asyncio.run(service.register_asset(file, AssetType.style_ref))

    assert asset.width == 200
    assert asset.height == 100

    registry = service.get_registry()
    assert len(registry.style_refs) == 1
