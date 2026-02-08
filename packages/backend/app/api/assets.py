from __future__ import annotations

from pathlib import Path
from typing import Generator, Optional, Union

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session as DbSession

from ..db.models import Session as SessionModel
from ..db.utils import get_db
from ..schemas.asset import AssetRef, AssetRegistry, AssetType
from ..services.asset_registry import AssetRegistryService

router = APIRouter(prefix="/api/sessions", tags=["assets"])


def _get_db_session() -> Generator[DbSession, None, None]:
    with get_db() as session:
        yield session


def _infer_asset_type(asset_id: str) -> Optional[AssetType]:
    normalized = asset_id
    if normalized.startswith("asset:"):
        normalized = normalized.split("asset:", 1)[1]
    stem = Path(normalized).stem
    if "_" not in stem:
        return None
    prefix = stem.split("_", 1)[0]
    try:
        return AssetType(prefix)
    except ValueError:
        return None


class AssetDetail(BaseModel):
    id: str
    url: str
    type: str
    width: Optional[int] = None
    height: Optional[int] = None
    asset_type: Optional[AssetType] = None
    filename: Optional[str] = None
    size: Optional[int] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


@router.post(
    "/{session_id}/assets",
    response_model=Union[AssetRef, list[AssetRef]],
)
async def upload_asset(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
    asset_type: AssetType = Query(..., description="logo/style_ref/background/product_image"),
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
) -> AssetRef | list[AssetRef]:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    uploads: list[UploadFile] = []
    if file is not None:
        uploads.append(file)
    if files:
        uploads.extend(files)
    if not uploads:
        raise HTTPException(status_code=400, detail="No files uploaded")

    service = AssetRegistryService(session_id)
    results: list[AssetRef] = []
    for item in uploads:
        try:
            results.append(await service.register_asset(item, asset_type))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if len(results) == 1:
        return results[0]
    return results


@router.get("/{session_id}/assets", response_model=AssetRegistry)
async def list_assets(
    session_id: str,
    db: DbSession = Depends(_get_db_session),
    asset_type: Optional[AssetType] = Query(None),
) -> AssetRegistry:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = AssetRegistryService(session_id)
    registry = service.get_registry()
    if asset_type is None:
        return registry
    filtered = AssetRegistry()
    if asset_type == AssetType.logo:
        filtered.logo = registry.logo
    elif asset_type == AssetType.style_ref:
        filtered.style_refs = registry.style_refs
    elif asset_type == AssetType.background:
        filtered.backgrounds = registry.backgrounds
    elif asset_type == AssetType.product_image:
        filtered.product_images = registry.product_images
    return filtered


@router.get("/{session_id}/assets/{asset_id}", response_model=AssetDetail)
async def get_asset_detail(
    session_id: str,
    asset_id: str,
    db: DbSession = Depends(_get_db_session),
) -> AssetDetail:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = AssetRegistryService(session_id)
    try:
        asset_path = service.get_asset_path(asset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    meta = service.get_asset_meta(asset_id)
    asset_type = _infer_asset_type(asset_id)
    asset_stem = asset_path.stem
    content_type = (
        meta.content_type if meta else service._content_type_for_extension(asset_path.suffix)
    )
    asset_ref = AssetRef(
        id=f"asset:{asset_stem}",
        url=f"/assets/{session_id}/{asset_path.name}",
        type=content_type or "application/octet-stream",
        width=meta.width if meta else None,
        height=meta.height if meta else None,
    )
    return AssetDetail(
        id=asset_ref.id,
        url=asset_ref.url,
        type=asset_ref.type,
        width=asset_ref.width,
        height=asset_ref.height,
        asset_type=asset_type,
        filename=meta.filename if meta else asset_path.name,
        size=asset_path.stat().st_size if asset_path.exists() else None,
        created_at=meta.created_at if meta else None,
    )


@router.delete("/{session_id}/assets/{asset_id}")
async def delete_asset(
    session_id: str,
    asset_id: str,
    db: DbSession = Depends(_get_db_session),
) -> dict:
    if db.get(SessionModel, session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    service = AssetRegistryService(session_id)
    if not service.delete_asset(asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "deleted"}


__all__ = ["router"]
