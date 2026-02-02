from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel


class FileTreeNode(BaseModel):
    name: str
    path: str
    type: Literal["file", "directory"]
    size: Optional[int] = None
    children: Optional[List["FileTreeNode"]] = None


class FileTreeResponse(BaseModel):
    tree: List[FileTreeNode]


class FileContentResponse(BaseModel):
    path: str
    content: str
    language: str
    size: int


if hasattr(FileTreeNode, "model_rebuild"):  # pragma: no cover - pydantic v1 compatibility
    FileTreeNode.model_rebuild()
else:  # pragma: no cover
    FileTreeNode.update_forward_refs()


__all__ = ["FileContentResponse", "FileTreeNode", "FileTreeResponse"]
