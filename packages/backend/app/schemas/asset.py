from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AssetType(str, Enum):
    logo = "logo"
    style_ref = "style_ref"
    background = "background"
    product_image = "product_image"


class AssetRef(BaseModel):
    id: str
    url: str
    type: str
    width: Optional[int] = None
    height: Optional[int] = None

    model_config = ConfigDict(extra="forbid")


class AssetRegistry(BaseModel):
    logo: Optional[AssetRef] = None
    style_refs: List[AssetRef] = Field(default_factory=list)
    backgrounds: List[AssetRef] = Field(default_factory=list)
    product_images: List[AssetRef] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


__all__ = ["AssetType", "AssetRef", "AssetRegistry"]
