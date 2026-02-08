# Phase B8: API - Chat Image Upload

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Low
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: None

## Goal

Update the Chat API to accept image attachments and @Page targeting information, storing images and passing them to the Orchestrator for style reference processing.

## Detailed Tasks

### Task 1: Update Chat Request Schema

**Description**: Add image attachments and page targets to chat request.

**Implementation Details**:
- [ ] Add `images` field to chat request (list of base64 or URLs)
- [ ] Add `target_pages` field (list of @Page mentions)
- [ ] Add `style_reference_mode` field (full_mimic, style_only)
- [ ] Validate image count (1-3 max)

**Files to modify/create**:
- `packages/backend/app/schemas/chat.py` (update)

**Acceptance Criteria**:
- [ ] Images field accepts 0-3 images
- [ ] Images can be base64 or URLs
- [ ] target_pages is optional, defaults to empty
- [ ] style_reference_mode defaults to full_mimic

### Task 2: Implement Image Storage

**Description**: Store uploaded images for reference during generation.

**Implementation Details**:
- [ ] Create image storage service
- [ ] Save base64 images to temporary storage
- [ ] Generate unique image IDs
- [ ] Return image IDs and URLs for retrieval
- [ ] Set TTL for temporary images

**Files to modify/create**:
- `packages/backend/app/services/image_storage.py` (new file)

**Acceptance Criteria**:
- [ ] Base64 images saved to disk/memory
- [ ] Unique IDs generated for each image
- [ ] Images retrievable by ID
- [ ] Images expire after session ends

### Task 3: Update Chat Endpoint

**Description**: Modify chat endpoint to handle images and page targets.

**Implementation Details**:
- [ ] Accept images in request body
- [ ] Parse @Page mentions from message
- [ ] Store images and get IDs
- [ ] Pass image metadata to Orchestrator
- [ ] Include style_reference context

**Files to modify/create**:
- `packages/backend/app/api/chat.py` (update)

**Acceptance Criteria**:
- [ ] Endpoint accepts images without error
- [ ] @Page syntax parsed from message text
- [ ] Images stored and IDs returned
- [ ] Orchestrator receives style reference info

### Task 4: Parse @Page Mentions

**Description**: Extract @Page mentions from user message text.

**Implementation Details**:
- [ ] Create `parse_page_mentions` utility
- [ ] Support @PageName syntax
- [ ] Case-insensitive matching
- [ ] Validate against existing project pages
- [ ] Return list of matched page slugs

**Files to modify/create**:
- `packages/backend/app/utils/chat.py` (new file)

**Acceptance Criteria**:
- [ ] Extracts "@Home" from "Update @Home header"
- [ ] Handles multiple @Page mentions
- [ ] Returns empty list if none found
- [ ] Validates pages exist in project

## Technical Specifications

### Chat Request Schema (Updated)

```python
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    images: List[str] = []  # Base64 data or URLs
    target_pages: List[str] = []  # Parsed from @Page mentions

class ChatRequest(BaseModel):
    session_id: str
    message: ChatMessage
    stream: bool = True
    style_reference: Optional[StyleReferenceInput] = None

class StyleReferenceInput(BaseModel):
    mode: Literal["full_mimic", "style_only"] = "full_mimic"
    images: List[str] = []  # 1-3 images
    scope_pages: List[str] = []  # Specific pages, empty = model decides
```

### Image Storage Service

```python
class ImageStorageService:
    def __init__(self, storage_dir: str, ttl_seconds: int = 3600):
        self.storage_dir = storage_dir
        self.ttl = ttl_seconds

    async def save_image(self, data: str, session_id: str) -> str:
        """Save base64 image and return ID."""
        image_id = f"{session_id}_{uuid4().hex[:8]}"
        # Decode and save
        # Return image_id

    async def get_image(self, image_id: str) -> Optional[dict]:
        """Retrieve image by ID."""
        # Return {id, data, content_type, created_at}

    async def cleanup_session(self, session_id: str):
        """Remove all images for a session."""
```

### @Page Parser

```python
def parse_page_mentions(
    message: str,
    existing_pages: List[str]
) -> List[str]:
    """
    Extract @Page mentions from message.

    Examples:
    - "Update @Home with new hero" -> ["home"]
    - "Change @Cart and @Checkout" -> ["cart", "checkout"]
    - "Add a button" -> []
    """
    import re
    pattern = r'@(\w+)'
    mentions = re.findall(pattern, message)
    # Case-insensitive match against existing_pages
    return [m.lower() for m in mentions if m.lower() in existing_pages]
```

### Chat Endpoint Updates

```python
@router.post("/chat")
async def chat(request: ChatRequest):
    # 1. Store images if present
    image_refs = []
    if request.message.images:
        for img in request.message.images[:3]:  # Max 3
            img_id = await image_storage.save_image(img, request.session_id)
            image_refs.append({"id": img_id, "source": "upload"})

    # 2. Parse @Page mentions
    target_pages = parse_page_mentions(
        request.message.content,
        get_project_pages(request.session_id)
    )

    # 3. Build style reference context
    style_context = None
    if image_refs:
        style_context = StyleReference(
            mode=request.style_reference.mode if request.style_reference else "full_mimic",
            scope={"type": "specific_pages" if target_pages else "model_decide",
                   "pages": target_pages},
            images=image_refs
        )

    # 4. Pass to orchestrator
    result = await orchestrator.run(
        session_id=request.session_id,
        message=request.message.content,
        style_reference=style_context,
        target_pages=target_pages
    )

    return result
```

## Testing Requirements

- [ ] Unit tests for schema validation
- [ ] Unit tests for @Page parsing
- [ ] Unit tests for image storage
- [ ] Integration tests for chat endpoint with images
- [ ] Tests with valid and invalid page mentions
- [ ] Tests with 0, 1, 3, and 4+ images (4 should fail)

## Notes & Warnings

- Limit images to 3 to avoid overwhelming the vision model
- Base64 encoding increases payload size by ~33%
- Consider image size limits (e.g., 5MB per image)
- @Page parsing should be case-insensitive but preserve original slug format
- Style reference images should be cleaned up after session
- Non-existent @Page mentions should be ignored (not error)
