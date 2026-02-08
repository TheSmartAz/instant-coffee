# Phase D1: Graph State Schema Extension

## Metadata

- **Category**: Database
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Low
- **Parallel Development**: ✅ Can start immediately
- **Dependencies**:
  - **Blocked by**: None (foundational)
  - **Blocks**: None (schema extension only)

## Goal

Extend session metadata to support LangGraph state persistence and build artifact tracking.

## Detailed Tasks

### Task 1: Extend Session Model for Graph State

**Description**: Add fields to Session model for LangGraph state storage

**Implementation Details**:
- [ ] Modify `packages/backend/app/db/models.py`
- [ ] Add graph_state JSON column (stores serialized state)
- [ ] Add build_status column (default 'pending')
- [ ] Add build_artifacts JSON column
- [ ] Add aesthetic_scores JSON column

**Files to modify**:
- `packages/backend/app/db/models.py`

**Acceptance Criteria**:
- [ ] Session model includes all new columns
- [ ] Migrations can add columns to existing tables
- [ ] Backward compatibility maintained

---

### Task 2: Create Session Metadata Schema

**Description**: Define Pydantic schema for session metadata extension

**Implementation Details**:
- [ ] Create/update `packages/backend/app/schemas/session_metadata.py`
- [ ] Define SessionMetadata with graph_state field
- [ ] Add BuildInfo, AestheticScore fields
- [ ] Implement CRUD operations for metadata

**Files to modify**:
- `packages/backend/app/schemas/session_metadata.py`

**Acceptance Criteria**:
- [ ] Schema validates graph_state JSON structure
- [ ] Build status enum values: pending/building/success/failed
- [ ] Metadata can be updated incrementally

---

### Task 3: Create Migrations

**Description**: Write Alembic migrations for schema changes

**Implementation Details**:
- [ ] Generate migration script
- [ ] Add graph_state column (JSON type)
- [ ] Add build_status column (String, default 'pending')
- [ ] Add build_artifacts column (JSON type)
- [ ] Add aesthetic_scores column (JSON type, nullable)

**Files to modify**:
- `packages/backend/app/db/migrations.py`

**Acceptance Criteria**:
- [ ] Migration runs without errors
- [ ] Existing sessions preserved
- [ ] New columns have correct defaults

---

### Task 4: Create State Persistence Service

**Description**: Implement service to save/restore graph state

**Implementation Details**:
- [ ] Create `packages/backend/app/services/state_store.py`
- [ ] Implement save_state(session_id, state) -> bool
- [ ] Implement load_state(session_id) -> Optional[dict]
- [ ] Implement clear_state(session_id) -> bool
- [ ] Add atomic update with session context

**Files to create**:
- `packages/backend/app/services/state_store.py`

**Acceptance Criteria**:
- [ ] State serialized to JSON for storage
- [ ] State can be restored for continuation
- [ ] Large states handled efficiently

## Technical Specifications

### Extended Session Model

```python
from sqlalchemy import Column, String, JSON, DateTime
from app.db.models import Base

class Session(Base):
    __tablename__ = 'sessions'

    # ... existing columns ...

    # Graph State extension
    graph_state = Column(JSON, nullable=True)
    build_status = Column(String(20), default='pending')
    build_artifacts = Column(JSON, nullable=True)
    aesthetic_scores = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

### SessionMetadata Schema

```python
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class SessionMetadata(BaseModel):
    session_id: str
    graph_state: Optional[Dict[str, Any]] = None
    build_status: str = "pending"
    build_artifacts: Optional[Dict[str, Any]] = None
    aesthetic_scores: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None

class BuildInfo(BaseModel):
    status: str  # pending / building / success / failed
    pages: List[str] = []
    dist_path: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class StatePersistenceService:
    async def save_state(self, session_id: str, state: dict) -> bool:
        """保存图状态到数据库"""
        pass

    async def load_state(self, session_id: str) -> Optional[dict]:
        """从数据库加载图状态"""
        pass

    async def update_build_status(self, session_id: str, status: BuildInfo) -> bool:
        """更新构建状态"""
        pass
```

### Migration Script

```python
# Revision ID: v07_d1
from alembic import op

def upgrade():
    op.add_column('sessions', sa.Column('graph_state', sa.JSON(), nullable=True))
    op.add_column('sessions', sa.Column('build_status', sa.String(20), default='pending'))
    op.add_column('sessions', sa.Column('build_artifacts', sa.JSON(), nullable=True))
    op.add_column('sessions', sa.Column('aesthetic_scores', sa.JSON(), nullable=True))

def downgrade():
    op.drop_column('sessions', 'graph_state')
    op.drop_column('sessions', 'build_status')
    op.drop_column('sessions', 'build_artifacts')
    op.drop_column('sessions', 'aesthetic_scores')
```

## Testing Requirements

- [ ] Unit test: Session model serialization
- [ ] Unit test: Metadata schema validation
- [ ] Integration test: State save/load roundtrip
- [ ] Integration test: Migration on existing database
- [ ] Performance test: Large state storage

## Notes & Warnings

- JSON storage handles nested structures
- Consider indexing build_status for queries
- State should be pruned periodically (keep last N versions)
- backup/restore should include graph_state
