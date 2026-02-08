# Phase B1: Contract Freeze & Tool System Foundation

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel (no dependencies)
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: v09-B2, v09-B3, v09-B5

## Goal

Freeze the immutable API contracts that the new system must preserve, then build the foundational tool abstraction layer (`BaseTool`, `ToolContext`, `ToolResult`, `ToolRegistry`) that all subsequent tools will implement.

## Detailed Tasks

### Task 1: Contract Freeze Document

**Description**: Explicitly document the immutable contracts before writing any code. This prevents accidental breakage during migration.

**Implementation Details**:
- [ ] Document `OrchestratorResponse` 12-field contract: `session_id`, `phase`, `message`, `is_complete`, `preview_url`, `preview_html`, `progress`, `questions`, `action`, `product_doc_updated`, `affected_pages`, `active_page_slug`
- [ ] Document SSE event types that must not be removed (existing `EventType` enum values)
- [ ] Document Run state machine transitions: `queued → running → waiting_input → completed/failed/cancelled`
- [ ] Document Chat API response shape for `POST /api/chat` and `POST /api/chat/stream`
- [ ] Document Interview payload contract: `questions` field with `type: "radio" | "checkbox" | "text"` and `options: list[str]`

**Files to modify/create**:
- Section within this phase doc serves as the contract reference

**Acceptance Criteria**:
- [ ] All 5 contract areas documented with field-level detail
- [ ] Can be used as a checklist during integration testing

---

### Task 2: BaseTool Abstract Base Class

**Description**: Create the `BaseTool` ABC that all tools will implement, along with `ToolContext` and `ToolResult` types.

**Implementation Details**:
- [ ] Create `BaseTool` ABC with: `name: str`, `description: str`, `parameters_model: type[BaseModel]`
- [ ] Implement `async execute(params: BaseModel, ctx: ToolContext) -> ToolResult` abstract method
- [ ] Implement `get_openai_schema() -> dict` that auto-generates OpenAI function schema from Pydantic model via `model_json_schema()`
- [ ] Create `ToolContext` dataclass with: `session_id`, `db`, `settings`, `event_emitter`, `output_dir`, `llm_client`, `run_id`
- [ ] Create `ToolResult` Pydantic model with: `success: bool`, `output: str`, `error: Optional[str]`, `artifacts: Optional[dict]`

**Files to modify/create**:
- `packages/backend/app/tools/__init__.py`
- `packages/backend/app/tools/base.py`

**Acceptance Criteria**:
- [ ] `BaseTool` subclass can define parameters via Pydantic model
- [ ] `get_openai_schema()` produces valid OpenAI function schema
- [ ] No new external dependencies required

---

### Task 3: ToolRegistry

**Description**: Create the `ToolRegistry` class that manages tool registration, schema generation, and safe execution.

**Implementation Details**:
- [ ] Implement `register(tool: BaseTool)` — adds tool to internal dict
- [ ] Implement `get_openai_tools() -> list[dict]` — returns all tool schemas in OpenAI function-calling format
- [ ] Implement `async execute(name: str, arguments: dict, ctx: ToolContext) -> ToolResult` — validates params via Pydantic, calls tool, catches exceptions, returns `ToolResult` on error (never raises)
- [ ] Handle unknown tool names gracefully with error `ToolResult`

**Files to modify/create**:
- `packages/backend/app/tools/registry.py`

**Acceptance Criteria**:
- [ ] `ToolRegistry.execute()` validates input, returns `ToolResult` on success or error
- [ ] Unknown tool name returns `ToolResult(success=False, error="Tool not found")`
- [ ] Pydantic validation rejects bad input types with descriptive error

---

### Task 4: Unit Tests

**Description**: Write tests for the tool foundation layer.

**Implementation Details**:
- [ ] Test: register a tool, verify schema output matches OpenAI format
- [ ] Test: execute tool with valid params → `ToolResult(success=True)`
- [ ] Test: execute tool with invalid params → `ToolResult(success=False, error=...)`
- [ ] Test: execute unknown tool → `ToolResult(success=False, error="Tool not found")`
- [ ] Test: Pydantic validation rejects bad input types

**Files to modify/create**:
- `packages/backend/tests/test_tool_registry.py`

**Acceptance Criteria**:
- [ ] All tests pass with `pytest tests/test_tool_registry.py`
- [ ] Tests use no external API calls

## Technical Specifications

### BaseTool Interface

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Optional
from dataclasses import dataclass

class ToolResult(BaseModel):
    success: bool
    output: str
    error: Optional[str] = None
    artifacts: Optional[dict] = None

@dataclass
class ToolContext:
    session_id: str
    db: AsyncSession
    settings: Settings
    event_emitter: EventEmitter
    output_dir: str
    llm_client: OpenAIClient
    run_id: Optional[str] = None

class BaseTool(ABC):
    name: str
    description: str
    parameters_model: type[BaseModel]

    @abstractmethod
    async def execute(self, params: BaseModel, ctx: ToolContext) -> ToolResult: ...

    def get_openai_schema(self) -> dict:
        """Auto-generate OpenAI function schema from Pydantic model."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_model.model_json_schema(),
            }
        }
```

### ToolRegistry Interface

```python
class ToolRegistry:
    def register(self, tool: BaseTool) -> None: ...
    def get_openai_tools(self) -> list[dict]: ...
    async def execute(self, name: str, arguments: dict, ctx: ToolContext) -> ToolResult: ...
```

## Testing Requirements

- [ ] Unit tests for `BaseTool.get_openai_schema()` schema generation
- [ ] Unit tests for `ToolRegistry.register()`, `get_openai_tools()`, `execute()`
- [ ] Edge case tests for invalid params, unknown tools, tool execution errors

## Notes & Warnings

- `ToolRegistry.execute()` must **never raise** — always return a `ToolResult` with error info
- The OpenAI schema generation relies on `model_json_schema()` from Pydantic v2
- `ToolContext` fields reference existing types (`AsyncSession`, `Settings`, `EventEmitter`, `OpenAIClient`) — import from existing modules
