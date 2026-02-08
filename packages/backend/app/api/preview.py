from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter(tags=["preview"])


def _resolve_dist_dir(session_id: str) -> Path:
    base = Path("~/.instant-coffee/sessions").expanduser()
    return (base / session_id / "dist").resolve()


def _safe_resolve(dist_dir: Path, path: str) -> Path:
    candidate = (dist_dir / path).resolve()
    if candidate != dist_dir and dist_dir not in candidate.parents:
        raise HTTPException(status_code=400, detail="Invalid path")
    return candidate


@router.get("/preview/{session_id}")
async def preview_index(session_id: str):
    return RedirectResponse(f"/preview/{session_id}/index.html")


@router.get("/preview/{session_id}/{path:path}")
async def serve_preview(session_id: str, path: str):
    dist_dir = _resolve_dist_dir(session_id)
    if not dist_dir.exists():
        raise HTTPException(status_code=404, detail="Build output not found")

    file_path = _safe_resolve(dist_dir, path)

    if file_path.is_dir() or not file_path.exists():
        file_path = _safe_resolve(file_path, "index.html")

    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    raise HTTPException(status_code=404, detail="File not found")


@router.get("/share/{session_id}")
async def share_preview(session_id: str):
    return RedirectResponse(f"/preview/{session_id}/index.html")


__all__ = ["router"]
