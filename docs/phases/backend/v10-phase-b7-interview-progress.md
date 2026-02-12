# Phase v10-B7: Interview Progress Indicator

## Metadata

- **Category**: Backend
- **Priority**: P1
- **Estimated Complexity**: Low
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v10-B6 (AskUser Timeout)
  - **Blocks**: v10-F3 (Frontend Progress UI)

## Goal

Add round tracking metadata to interview questions for frontend progress display.

## Detailed Tasks

### Task 1: Extend AskUserInput

**Description**: Add progress metadata to question tool.

**Implementation Details**:
- [ ] Add round_number field to AskUserInput
- [ ] Add estimated_total_rounds field

**Files to modify**:
- `packages/agent/src/ic/tools/ask_user.py`

**Acceptance Criteria**:
- [ ] LLM can set progress metadata

---

### Task 2: Backend event with progress

**Description**: Include progress in question events.

**Implementation Details**:
- [ ] Update question_asked event to include progress
- [ ] Ensure frontend receives round info

**Files to modify**:
- `packages/backend/app/events/models.py`
- `packages/backend/app/engine/web_user_io.py`

**Acceptance Criteria**:
- [ ] Frontend receives round_number and total

## Technical Specifications

### AskUserInput Extension

```python
class AskUserInput(BaseModel):
    questions: list[QuestionItem]
    round_number: Optional[int] = None      # Current round
    estimated_total_rounds: Optional[int] = None  # Expected total
```

### Event Extension

```python
class QuestionAskedEvent(BaseEvent):
    # ... existing fields
    round_number: Optional[int] = None
    estimated_total_rounds: Optional[int] = None
```

## Testing Requirements

- [ ] Test progress metadata in events
- [ ] Test frontend receives data

## Notes & Warnings

- Frontend part is v10-F3
- Make fields optional for backward compatibility
