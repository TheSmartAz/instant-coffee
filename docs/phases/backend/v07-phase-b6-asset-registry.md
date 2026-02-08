# Phase B6: Asset Registry Service

## Metadata

- **Category**: Backend
- **Priority**: P0 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel with B1
- **Dependencies**:
  - **Blocked by**: None (can start anytime)
  - **Blocks**: B8 (Asset API depends on this)

## Goal

Implement asset upload, storage, and management service for Logo, Style Reference, Background, and Product Image assets.

## Detailed Tasks

### Task 1: Create Asset Registry Schemas

**Description**: Define Pydantic models for asset references and registry

**Implementation Details**:
- [ ] Create `packages/backend/app/schemas/asset.py`
- [ ] Define AssetRef, AssetRegistry, AssetType enums
- [ ] Add width/height for image assets
- [ ] Define session-scoped asset storage

**Files to create**:
- `packages/backend/app/schemas/asset.py`

**Acceptance Criteria**:
- [ ] AssetRef matches spec section 5.3
- [ ] AssetRegistry includes all asset types
- [ ] AssetType enum values: logo, style_ref, background, product_image

---

### Task 2: Implement AssetRegistryService

**Description**: Create service class for asset file operations and URL mapping

**Implementation Details**:
- [ ] Create `packages/backend/app/services/asset_registry.py`
- [ ] Implement AssetRegistryService class
- [ ] Add register_asset(file, asset_type) -> AssetRef
- [ ] Add get_registry() -> AssetRegistry
- [ ] Add get_asset_path(asset_id) -> Path
- [ ] Handle file saving with session isolation

**Files to create**:
- `packages/backend/app/services/asset_registry.py`

**Acceptance Criteria**:
- [ ] Assets stored in ~/.instant-coffee/sessions/{session_id}/assets/
- [ ] Asset IDs follow format: {asset_type}_{hash}
- [ ] URLs follow format: /assets/{session_id}/{asset_id}{ext}
- [ ] Image dimensions auto-detected

---

### Task 3: Implement Style Extractor

**Description**: Create Claude Vision API integration for style token extraction

**Implementation Details**:
- [ ] Create `packages/backend/app/services/style_extractor.py`
- [ ] Implement StyleExtractorService class
- [ ] Add extract_style_tokens(image_url) -> StyleTokens
- [ ] Create STYLE_EXTRACTION_PROMPT
- [ ] Parse JSON response from Vision API

**Files to create**:
- `packages/backend/app/services/style_extractor.py`

**Acceptance Criteria**:
- [ ] Returns StyleTokens matching spec section 9.2
- [ ] Extracts colors, typography, radius, spacing, shadow, style
- [ ] Falls back to rule-based extraction if Vision fails

---

### Task 4: Create Style Extractor Node

**Description**: Implement style_extractor_node for LangGraph integration

**Implementation Details**:
- [ ] Create `packages/backend/app/graph/nodes/style_extractor.py`
- [ ] Implement style_extractor_node(state) function
- [ ] Check if assets contain style_refs
- [ ] Extract tokens and add to state.style_tokens
- [ ] Handle case with no style references

**Files to create**:
- `packages/backend/app/graph/nodes/style_extractor.py`

**Acceptance Criteria**:
- [ ] Node triggered when assets have style_refs
- [ ] Output matches state.style_tokens expected format
- [ ] Graceful handling when no style refs present

## Technical Specifications

### Asset Schemas

```python
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum

class AssetType(str, Enum):
    logo = "logo"
    style_ref = "style_ref"
    background = "background"
    product_image = "product_image"

class AssetRef(BaseModel):
    id: str           # asset:{type}_{hash}
    url: str          # /assets/{session_id}/logo_1.png
    type: str         # "image/png" | "image/jpeg" | "image/webp" | "image/svg+xml"
    width: Optional[int] = None
    height: Optional[int] = None

class AssetRegistry(BaseModel):
    logo: Optional[AssetRef] = None
    style_refs: List[AssetRef] = []
    backgrounds: List[AssetRef] = []
    product_images: List[AssetRef] = []
```

### AssetRegistryService

```python
from pathlib import Path
from fastapi import UploadFile

class AssetRegistryService:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.base_path = Path(f"~/.instant-coffee/sessions/{session_id}/assets").expanduser()
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def register_asset(self, file: UploadFile, asset_type: str) -> AssetRef:
        """注册资产并返回引用"""
        asset_id = f"{asset_type}_{uuid4().hex[:8]}"
        file_ext = Path(file.filename).suffix
        file_path = self.base_path / f"{asset_id}{file_ext}"

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(await file.read())

        with Image.open(file_path) as img:
            width, height = img.size

        return AssetRef(
            id=f"asset:{asset_id}",
            url=f"/assets/{self.session_id}/{asset_id}{file_ext}",
            type=file.content_type,
            width=width,
            height=height
        )

    def get_registry(self) -> AssetRegistry:
        """获取当前会话的资产注册表"""
        # Implementation to scan assets directory
        pass
```

### StyleTokens Structure

```python
class StyleTokens(BaseModel):
    colors: dict
    typography: dict
    radius: str       # "none" | "small" | "medium" | "large" | "full"
    spacing: str     # "compact" | "normal" | "airy"
    shadow: str      # "none" | "subtle" | "medium" | "strong"
    style: str       # "modern" | "classic" | "playful" | "minimal" | "bold"

class ColorTokens(BaseModel):
    primary: str
    secondary: str
    accent: str
    background: str
    surface: str
    text: dict  # primary, secondary, muted
```

### Style Extraction Prompt

```python
STYLE_EXTRACTION_PROMPT = """
分析这张图片的视觉设计风格，提取以下信息并以 JSON 格式返回：

1. colors: 识别主色、辅色、强调色、背景色、文字色
2. typography: 字体风格（现代/经典）、间距密度
3. radius: 圆角程度 (none/small/medium/large/full)
4. spacing: 元素间距 (compact/normal/airy)
5. shadow: 阴影强度 (none/subtle/medium/strong)
6. style: 整体风格 (modern/classic/playful/minimal/bold)

返回格式：
```json
{
  "colors": { ... },
  "typography": { ... },
  "radius": "...",
  "spacing": "...",
  "shadow": "...",
  "style": "..."
}
```
"""
```

## Testing Requirements

- [ ] Unit test: Asset registration with various file types
- [ ] Unit test: Image dimension detection
- [ ] Unit test: Style extraction with sample images
- [ ] Integration test: Asset API with frontend upload
- [ ] Test Vision API fallback to rule-based extraction

## Notes & Warnings

- Asset IDs must be unique per session
- Support PNG, JPEG, WebP, SVG formats
- Vision API requires Claude API key
- Fallback extraction should use simple color analysis
- Asset URLs are session-scoped for security
