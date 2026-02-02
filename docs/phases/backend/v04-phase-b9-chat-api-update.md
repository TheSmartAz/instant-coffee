# Phase B9: Chat API Update

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B5 (Orchestrator Update)
  - **Blocks**: F4

## Goal

Extend the Chat API to support the new ProductDoc flow, Generate Now mode, and return enhanced response fields for frontend coordination.

## Detailed Tasks

### Task 1: Add generate_now Request Parameter

**Description**: Add optional generate_now flag to chat request.

**Implementation Details**:
- [ ] Add `generate_now: bool = False` to ChatRequest schema
- [ ] Pass parameter to Orchestrator
- [ ] Document parameter in OpenAPI

**Files to modify/create**:
- `packages/backend/app/api/chat.py`
- `packages/backend/app/schemas/chat.py`

**Acceptance Criteria**:
- [ ] Parameter accepted in request
- [ ] Default is False
- [ ] Passed to Orchestrator correctly

---

### Task 2: Add Response Fields for ProductDoc

**Description**: Add new response fields related to ProductDoc state.

**Implementation Details**:
- [ ] Add `product_doc_updated: bool` - true if ProductDoc was created/updated
- [ ] Add `affected_pages: List[str]` - list of affected page slugs
- [ ] Add `action: str` - describes what action was taken
- [ ] Define action values:
  - `product_doc_generated`
  - `product_doc_updated`
  - `product_doc_confirmed`
  - `pages_generated`
  - `page_refined`
  - `direct_reply`

**Files to modify/create**:
- `packages/backend/app/schemas/chat.py`
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] New fields in response
- [ ] Fields accurately reflect what happened
- [ ] Action value correctly set

---

### Task 3: Update Preview Fields for Multi-Page

**Description**: Update preview_url and preview_html for multi-page context.

**Implementation Details**:
- [ ] If single page generated/refined, return that page's preview
- [ ] If multiple pages generated, return index page preview
- [ ] Ensure preview_html is self-contained (inline CSS)
- [ ] Add `active_page_slug: str` to indicate which page preview refers to

**Files to modify/create**:
- `packages/backend/app/api/chat.py`
- `packages/backend/app/schemas/chat.py`

**Acceptance Criteria**:
- [ ] Preview shows relevant page
- [ ] Preview is self-contained
- [ ] Active page identified

---

### Task 4: Handle Generate Now Flow

**Description**: Implement Generate Now path in chat handler.

**Implementation Details**:
- [ ] If generate_now=true and no ProductDoc exists:
  - Generate ProductDoc
  - Auto-confirm (status=confirmed)
  - Trigger generation pipeline
  - Return full result
- [ ] If generate_now=true and ProductDoc is draft:
  - Confirm ProductDoc
  - Trigger generation pipeline
- [ ] Ensure atomic transaction handling

**Files to modify/create**:
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] Generate Now creates and confirms ProductDoc
- [ ] Pipeline triggers immediately
- [ ] Errors handled gracefully

---

### Task 5: Integrate with Updated Orchestrator

**Description**: Wire chat endpoint to use updated Orchestrator routing.

**Implementation Details**:
- [ ] Call Orchestrator.route() with generate_now flag
- [ ] Handle each route type appropriately
- [ ] Collect results from various agents
- [ ] Aggregate token usage
- [ ] Emit appropriate SSE events

**Files to modify/create**:
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] All route types handled
- [ ] Correct agents called
- [ ] Events emitted properly

---

### Task 6: Add Backward Compatibility

**Description**: Ensure old clients continue to work.

**Implementation Details**:
- [ ] Old clients not sending generate_now still work (defaults to false)
- [ ] Old response fields still present (preview_url, preview_html, message)
- [ ] Old sessions without ProductDoc handled (create default on first interaction)

**Files to modify/create**:
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] Old API calls still work
- [ ] No breaking changes to existing fields
- [ ] Old sessions functional

---

## Technical Specifications

### Updated Request Schema

```python
class ChatRequest(BaseModel):
    session_id: UUID | None = None  # None = create new session
    message: str
    generate_now: bool = False  # Skip ProductDoc confirmation

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "创建一个咖啡店的移动端网站",
                "generate_now": False
            }
        }
    )
```

### Updated Response Schema

```python
class ChatResponse(BaseModel):
    session_id: UUID
    message: str  # Agent's response message

    # Preview (for backward compatibility + multi-page)
    preview_url: str | None = None
    preview_html: str | None = None
    active_page_slug: str | None = None  # Which page the preview is for

    # ProductDoc state
    product_doc_updated: bool = False  # True if ProductDoc created/updated
    affected_pages: List[str] = []  # Slugs of affected pages

    # Action indicator
    action: str  # What action was taken
    # Values: product_doc_generated, product_doc_updated,
    #         product_doc_confirmed, pages_generated, page_refined, direct_reply

    # Token usage
    tokens_used: int = 0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "这是为您生成的产品文档，请查看 Product Doc 标签页。",
                "preview_url": None,
                "preview_html": None,
                "active_page_slug": None,
                "product_doc_updated": True,
                "affected_pages": [],
                "action": "product_doc_generated",
                "tokens_used": 1234
            }
        }
    )
```

### Chat Handler Flow

```python
async def chat(request: ChatRequest, ...) -> ChatResponse:
    # 1. Get or create session
    session = await get_or_create_session(request.session_id)

    # 2. Route the message
    route_result = await orchestrator.route(
        user_message=request.message,
        session=session,
        generate_now=request.generate_now
    )

    # 3. Execute based on route
    result = None
    if route_result.route == "product_doc_generation":
        result = await handle_product_doc_generation(session, request.message)
    elif route_result.route == "product_doc_generation_generate_now":
        result = await handle_generate_now(session, request.message)
    elif route_result.route == "product_doc_confirm":
        result = await handle_product_doc_confirm(session)
    elif route_result.route == "product_doc_update":
        result = await handle_product_doc_update(session, request.message)
    elif route_result.route == "refinement":
        result = await handle_refinement(session, request.message, route_result.target_page)
    elif route_result.route == "generation_pipeline":
        result = await handle_generation_pipeline(session)
    else:  # direct_reply
        result = await handle_direct_reply(session, request.message)

    # 4. Build response
    return ChatResponse(
        session_id=session.id,
        message=result.message,
        preview_url=result.preview_url,
        preview_html=result.preview_html,
        active_page_slug=result.active_page_slug,
        product_doc_updated=result.product_doc_updated,
        affected_pages=result.affected_pages,
        action=result.action,
        tokens_used=result.tokens_used
    )
```

### Action Values

| Action | When Used |
|--------|-----------|
| `product_doc_generated` | ProductDoc first created (draft) |
| `product_doc_updated` | ProductDoc modified |
| `product_doc_confirmed` | User confirmed ProductDoc |
| `pages_generated` | Pages generated from ProductDoc |
| `page_refined` | Single page modified |
| `direct_reply` | Question/feedback, no generation |

## Testing Requirements

- [ ] Unit tests for new request parameters
- [ ] Unit tests for new response fields
- [ ] Integration test for Generate Now flow
- [ ] Integration test for standard confirmation flow
- [ ] Integration test for refinement flow
- [ ] Backward compatibility test with old request format

## Notes & Warnings

- **Generate Now Transaction**: Should be atomic - if any step fails, roll back all
- **Preview Selection**: For multi-page, always default to index for preview
- **Event Timing**: Emit SSE events after DB commits, before response
- **Token Aggregation**: Sum tokens from all agents called in single request
- **Error Messages**: Return helpful messages for failures, not stack traces
