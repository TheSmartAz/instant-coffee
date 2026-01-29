# Phase D1: Core Database Schema

## Metadata

- **Category**: Database
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Low
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: B1 (Chat API), B2 (Session Management), B3 (Token Tracking)

## Goal

Design and implement the SQLite database schema including sessions, messages, versions, and token_usage tables. This provides the data foundation for all backend operations.

## Detailed Tasks

### Task 1: Create Database Connection Module

**Description**: Set up SQLite database connection with SQLAlchemy ORM, establish database file location, and implement connection pooling.

**Implementation Details**:
- [ ] Create database connection class with SQLAlchemy
- [ ] Define database file path (`~/.instant-coffee/instant-coffee.db`)
- [ ] Implement auto-creation of database directory
- [ ] Add connection pooling configuration
- [ ] Create base declarative model class

**Files to modify/create**:
- `packages/backend/app/db/__init__.py`
- `packages/backend/app/db/database.py`
- `packages/backend/app/db/base.py`

**Acceptance Criteria**:
- [ ] Database file is created in correct location on first run
- [ ] Connection can be established successfully
- [ ] Connection handles concurrent access properly
- [ ] Directory is auto-created if it doesn't exist

---

### Task 2: Define Data Models

**Description**: Create SQLAlchemy ORM models for all four tables: sessions, messages, versions, token_usage.

**Implementation Details**:
- [ ] Create Session model with id, title, timestamps, current_version
- [ ] Create Message model with foreign key to sessions
- [ ] Create Version model with foreign key to sessions
- [ ] Create TokenUsage model with foreign key to sessions
- [ ] Add proper relationships between models
- [ ] Implement __repr__ methods for debugging

**Files to modify/create**:
- `packages/backend/app/db/models.py`

**Acceptance Criteria**:
- [ ] All models have correct field types and constraints
- [ ] Foreign key relationships are properly defined
- [ ] Models can be instantiated and queried
- [ ] Relationships work bidirectionally

---

### Task 3: Create Database Migration System

**Description**: Implement a simple migration system to create tables and handle future schema changes.

**Implementation Details**:
- [ ] Create init_db() function to create all tables
- [ ] Add migration version tracking
- [ ] Implement drop_db() for testing
- [ ] Add reset_db() for development
- [ ] Create indexes for performance

**Files to modify/create**:
- `packages/backend/app/db/migrations.py`

**Acceptance Criteria**:
- [ ] Tables are created with correct schema
- [ ] Indexes are created on foreign keys and timestamp fields
- [ ] Migration can be run multiple times safely (idempotent)
- [ ] Drop and reset functions work correctly

---

### Task 4: Implement Database Utilities

**Description**: Create utility functions for common database operations.

**Implementation Details**:
- [ ] Create get_db() context manager for sessions
- [ ] Implement transaction handling utilities
- [ ] Add query helper functions
- [ ] Create database health check function
- [ ] Add connection testing utility

**Files to modify/create**:
- `packages/backend/app/db/utils.py`

**Acceptance Criteria**:
- [ ] Context manager properly handles session lifecycle
- [ ] Transactions are properly committed or rolled back
- [ ] Health check can verify database connectivity
- [ ] Utilities handle errors gracefully

---

### Task 5: Write Database Tests

**Description**: Create comprehensive tests for database models and operations.

**Implementation Details**:
- [ ] Test session creation and retrieval
- [ ] Test message insertion and querying
- [ ] Test version management
- [ ] Test token_usage recording
- [ ] Test foreign key constraints
- [ ] Test cascade delete behavior

**Files to modify/create**:
- `packages/backend/tests/test_db.py`

**Acceptance Criteria**:
- [ ] All CRUD operations work correctly
- [ ] Foreign key constraints are enforced
- [ ] Timestamps are automatically set
- [ ] Query relationships work properly

## Technical Specifications

### Database Schema

```sql
-- 会话表
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    current_version INTEGER DEFAULT 0
);

-- 消息表
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- 版本表
CREATE TABLE versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    html TEXT NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    UNIQUE(session_id, version)
);

-- Token 使用表
CREATE TABLE token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    agent_type TEXT NOT NULL,  -- 'interview', 'generation', 'refinement'
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- 索引
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_timestamp ON messages(timestamp);
CREATE INDEX idx_versions_session ON versions(session_id);
CREATE INDEX idx_token_usage_session ON token_usage(session_id);
CREATE INDEX idx_token_usage_timestamp ON token_usage(timestamp);
CREATE INDEX idx_sessions_updated ON sessions(updated_at);
```

### SQLAlchemy Models Structure

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class Session(Base):
    __tablename__ = 'sessions'

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    current_version = Column(Integer, default=0)

    # Relationships
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    versions = relationship("Version", back_populates="session", cascade="all, delete-orphan")
    token_usage = relationship("TokenUsage", back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("Session", back_populates="messages")

class Version(Base):
    __tablename__ = 'versions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False)
    version = Column(Integer, nullable=False)
    html = Column(Text, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("Session", back_populates="versions")

class TokenUsage(Base):
    __tablename__ = 'token_usage'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    agent_type = Column(String, nullable=False)
    model = Column(String, nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    cost_usd = Column(Float, nullable=False)

    # Relationships
    session = relationship("Session", back_populates="token_usage")
```

## Testing Requirements

- [ ] Unit tests for each model's CRUD operations
- [ ] Test foreign key constraint enforcement
- [ ] Test cascade delete behavior
- [ ] Test default values and auto-timestamps
- [ ] Test unique constraints (session_id + version)
- [ ] Integration tests for complex queries
- [ ] Performance tests for large datasets

## Notes & Warnings

- **Session ID Generation**: Use UUID4 for session IDs to ensure uniqueness
- **Cascade Deletes**: All related records (messages, versions, token_usage) will be deleted when a session is deleted
- **Database Location**: Ensure `~/.instant-coffee/` directory has proper permissions
- **SQLite Limitations**: Be aware that SQLite doesn't support concurrent writes - handle with connection pooling
- **Timestamps**: All timestamps should be UTC to avoid timezone issues
- **Version Numbers**: Start from 0 for initial generation, increment for each modification
