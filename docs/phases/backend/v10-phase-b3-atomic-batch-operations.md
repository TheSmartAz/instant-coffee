# Phase v10-B3: Atomic Multi-file Operations

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v10-B2 (Structured HTML Tool)
  - **Blocks**: None (independent feature)

## Goal

Implement atomic batch file operations with transaction rollback on failure.

## Detailed Tasks

### Task 1: Create BatchFileWrite tool

**Description**: New tool for atomic multi-file operations.

**Implementation Details**:
- [ ] Create packages/backend/app/engine/batch_tools.py
- [ ] Define BatchFileWriteInput model
- [ ] Define FileOperation model
- [ ] Implement transaction mechanism

**Files to create**:
- `packages/backend/app/engine/batch_tools.py`

**Acceptance Criteria**:
- [ ] All operations succeed → all committed
- [ ] Any operation fails → rollback all

---

### Task 2: Implement transaction mechanism

**Description**: Add rollback capability for failed operations.

**Implementation Details**:
- [ ] Collect all operations
- [ ] Validate all operations can execute
- [ ] Execute sequentially
- [ ] On failure, rollback completed operations
- [ ] Return results

**Files to modify**:
- `packages/backend/app/engine/batch_tools.py`

**Acceptance Criteria**:
- [ ] Rollback works correctly
- [ ] Error messages are clear

---

### Task 3: Agent-side batch tool

**Description**: Create agent-accessible version of batch operations.

**Implementation Details**:
- [ ] Add batch tools to packages/agent/src/ic/tools/
- [ ] Ensure consistency with backend

**Files to create**:
- `packages/agent/src/ic/tools/batch_operations.py`

**Acceptance Criteria**:
- [ ] Agent can use batch operations

## Technical Specifications

### Input Model

```python
class BatchFileWriteInput(BaseModel):
    operations: list[FileOperation]

class FileOperation(BaseModel):
    operation: Literal["write", "edit", "delete"]
    path: str
    content: Optional[str] = None
    old_content: Optional[str] = None  # For edit
    # ... other params
```

### Output Model

```python
class BatchFileWriteOutput(BaseModel):
    success: bool
    results: list[OperationResult]
    error: Optional[str] = None

class OperationResult(BaseModel):
    operation: str
    path: str
    success: bool
    error: Optional[str] = None
```

### Transaction Flow

```
1. Collect operations
2. Validate all operations
3. Execute sequentially
4. If any fails:
   a. Rollback completed operations
   b. Return error
5. Return success
```

## Testing Requirements

- [ ] Test successful batch
- [ ] Test rollback on failure
- [ ] Test concurrent sub-agent writes

## Notes & Warnings

- Ensure idempotency for edit operations
- Consider file locking for concurrent access
