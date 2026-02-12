# Phase v10-B2: Structured HTML Generation Tool

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v10-B1 (Token Calculation)
  - **Blocks**: v10-B3 (Atomic Multi-file Operations)

## Goal

Create a structured HTML generation tool that returns validated JSON output with built-in mobile compliance checks.

## Detailed Tasks

### Task 1: Create generate_html tool

**Description**: New agent tool that returns structured JSON with validation.

**Implementation Details**:
- [ ] Create packages/agent/src/ic/tools/generate_html.py
- [ ] Define GenerateHtmlInput Pydantic model
- [ ] Define GenerateHtmlOutput Pydantic model
- [ ] Implement validation logic

**Files to create**:
- `packages/agent/src/ic/tools/generate_html.py`

**Acceptance Criteria**:
- [ ] Tool registered in tool registry
- [ ] Returns structured JSON output

---

### Task 2: Implement validation logic

**Description**: Add mobile compliance validation checks.

**Implementation Details**:
- [ ] Viewport meta tag presence check
- [ ] max-width 430px constraint check
- [ ] Touch target minimum 44px check
- [ ] Scrollbar hiding check
- [ ] Font size compliance check

**Files to modify**:
- `packages/agent/src/ic/tools/generate_html.py`

**Acceptance Criteria**:
- [ ] Validation failures prevent write
- [ ] Validation results included in output

---

### Task 3: Backend version of generate_html

**Description**: Create backend version for DBWriteFile integration.

**Implementation Details**:
- [ ] Add generate_html to packages/backend/app/engine/db_tools.py
- [ ] Ensure consistency with agent version

**Files to modify**:
- `packages/backend/app/engine/db_tools.py`

**Acceptance Criteria**:
- [ ] Backend can use same validation logic

---

### Task 4: Register tool in agent

**Description**: Register generate_html in the agent tool system.

**Implementation Details**:
- [ ] Add to tools/__init__.py
- [ ] Add to tool registry

**Files to modify**:
- `packages/agent/src/ic/tools/__init__.py`

**Acceptance Criteria**:
- [ ] Tool available to agent

## Technical Specifications

### Input Model

```python
class GenerateHtmlInput(BaseModel):
    slug: str          # Page slug
    title: str         # Page title
    description: str   # Page description
    data_model: Optional[dict] = None
    design_system_css: Optional[str] = None
```

### Output Model

```python
class GenerateHtmlOutput(BaseModel):
    slug: str
    title: str
    html: str          # Generated HTML
    css: str           # Page-specific CSS
    validation: dict   # Validation results
```

### Validation Rules

| Rule | Check |
|------|-------|
| Viewport | `<meta name="viewport"` present |
| Max Width | `max-width: 430px` in container |
| Touch Target | Min height 44px for interactive elements |
| Scrollbar | `.hide-scrollbar` or `overflow: hidden` |
| Font Size | Body >= 16px, headings >= 24px |

## Testing Requirements

- [ ] Unit tests for validation logic
- [ ] Integration tests with agent

## Notes & Warnings

- This is a critical path item - other phases depend on it
- Validation should be fast to not impact generation speed
