# Phase v10-B5: Structured Compaction

## Metadata

- **Category**: Backend
- **Priority**: P1
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v10-B1 (Token Calculation)
  - **Blocks**: None (optimization feature)

## Goal

Replace simple truncation with structured compression that preserves key project state.

## Detailed Tasks

### Task 1: Define ProjectState model

**Description**: Define what information to preserve during compaction.

**Implementation Details**:
- [ ] Create ProjectState Pydantic model
- [ ] Define fields: product_doc_summary, file_change_history, design_decisions, pending_requirements, page_summaries

**Files to modify**:
- `packages/agent/src/ic/soul/context.py`

**Acceptance Criteria**:
- [ ] All key state is captured

---

### Task 2: Implement structured compression

**Description**: Replace compact_with_llm with structured approach.

**Implementation Details**:
- [ ] Extract current project state
- [ ] Use LLM to compress while preserving structure
- [ ] Use FAST-tier model for compression

**Files to modify**:
- `packages/agent/src/ic/soul/context.py`

**Acceptance Criteria**:
- [ ] Compaction preserves key state
- [ ] LLM can continue working after compaction

## Technical Specifications

### ProjectState Model

```python
class ProjectState(BaseModel):
    """Compressed project state"""
    product_doc_summary: str
    file_change_history: list[FileChange]
    design_decisions: list[str]
    pending_requirements: list[str]
    page_summaries: dict[str, str]

class FileChange(BaseModel):
    path: str
    change_type: str  # created/modified/deleted
    timestamp: datetime
```

### Compression Prompt

```
请压缩对话历史，保留以下结构化信息：
1. Product Doc 当前状态（类型、页面、风格）
2. 文件变更历史（创建/修改了哪些文件）
3. 设计决策（颜色、布局、组件选择）
4. 待处理需求（用户要求但未完成的功能）
5. 页面摘要（每个页面的核心功能）
```

## Testing Requirements

- [ ] Test compaction preserves state
- [ ] Test LLM continues after compaction
- [ ] Test compression uses fast model

## Notes & Warnings

- This is an optimization - Phase 1 must complete first
- Track compaction history for debugging
