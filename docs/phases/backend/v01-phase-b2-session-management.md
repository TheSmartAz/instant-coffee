# Phase B2: Session & History Management

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: D1 (Core Schema), B1 (Chat API)
  - **Blocks**: F3 (History Commands)

## Goal

Implement session management, version control, and history tracking services. This handles creating, saving, loading, and rolling back sessions with their conversation history and generated page versions.

## Detailed Tasks

### Task 1: Create Session Service

**Description**: Build the SessionService class that handles all session CRUD operations.

**Implementation Details**:
- [ ] Create SessionService class
- [ ] Implement create_session() with UUID generation
- [ ] Implement get_session() with caching
- [ ] Implement update_session() with timestamp management
- [ ] Implement list_sessions() with pagination and sorting
- [ ] Add session title auto-generation from first user message

**Files to modify/create**:
- `packages/backend/app/services/session.py`
- `packages/backend/app/services/__init__.py`

**Acceptance Criteria**:
- [ ] Sessions are created with unique UUIDs
- [ ] Session titles are auto-generated intelligently
- [ ] Sessions can be retrieved by ID
- [ ] List returns sessions sorted by updated_at (DESC)
- [ ] Updates properly modify updated_at timestamp

---

### Task 2: Create Message Service

**Description**: Build the MessageService for managing conversation messages within sessions.

**Implementation Details**:
- [ ] Create MessageService class
- [ ] Implement add_message() for user and assistant messages
- [ ] Implement get_messages() to retrieve session history
- [ ] Add message pagination support
- [ ] Implement message count per session

**Files to modify/create**:
- `packages/backend/app/services/message.py`

**Acceptance Criteria**:
- [ ] Messages are correctly associated with sessions
- [ ] Role validation ensures only 'user' or 'assistant'
- [ ] Messages are retrieved in chronological order
- [ ] Pagination works correctly

---

### Task 3: Create Version Control Service

**Description**: Build the VersionService for managing HTML page versions with rollback capability.

**Implementation Details**:
- [ ] Create VersionService class
- [ ] Implement create_version() with auto-incrementing version numbers
- [ ] Implement get_version() to retrieve specific versions
- [ ] Implement get_versions() to list all versions for a session
- [ ] Implement rollback() to revert to previous version
- [ ] Add version description generation

**Files to modify/create**:
- `packages/backend/app/services/version.py`

**Acceptance Criteria**:
- [ ] Versions are auto-numbered starting from 0
- [ ] HTML content is properly stored and retrieved
- [ ] Rollback sets current_version correctly
- [ ] Version descriptions are meaningful
- [ ] Can retrieve any historical version

---

### Task 4: Create Filesystem Service

**Description**: Build the FilesystemService for saving generated HTML to disk.

**Implementation Details**:
- [ ] Create FilesystemService class
- [ ] Implement save_html() to write HTML to output directory
- [ ] Implement create_output_directory() with proper permissions
- [ ] Generate meaningful filenames (session-based or custom)
- [ ] Handle file overwriting for version updates
- [ ] Return absolute file paths for preview URLs

**Files to modify/create**:
- `packages/backend/app/services/filesystem.py`

**Acceptance Criteria**:
- [ ] HTML files are saved to correct output directory
- [ ] Directories are created if they don't exist
- [ ] File paths are absolute and valid
- [ ] Handles write permissions errors gracefully

---

### Task 5: Create API Endpoints for Session Management

**Description**: Build REST API endpoints for session operations used by CLI.

**Implementation Details**:
- [ ] Implement GET /api/sessions (list all sessions)
- [ ] Implement GET /api/sessions/{id} (get session details)
- [ ] Implement GET /api/sessions/{id}/messages (get conversation history)
- [ ] Implement GET /api/sessions/{id}/versions (list versions)
- [ ] Implement POST /api/sessions/{id}/rollback (rollback to version)

**Files to modify/create**:
- `packages/backend/app/api/sessions.py`

**Acceptance Criteria**:
- [ ] All endpoints return proper status codes
- [ ] Responses include complete session data
- [ ] Error handling for non-existent sessions
- [ ] Pagination works for list endpoints

## Technical Specifications

### API Endpoints

#### GET /api/sessions
```json
Response:
{
  "sessions": [
    {
      "id": "abc123",
      "title": "活动报名页面",
      "created_at": "2025-01-30T14:15:00Z",
      "updated_at": "2025-01-30T14:23:00Z",
      "current_version": 1,
      "message_count": 8,
      "version_count": 2
    }
  ],
  "total": 23
}
```

#### GET /api/sessions/{id}/versions
```json
Response:
{
  "versions": [
    {
      "version": 1,
      "description": "调整了按钮大小",
      "created_at": "2025-01-30T14:23:00Z"
    },
    {
      "version": 0,
      "description": "初始生成",
      "created_at": "2025-01-30T14:15:00Z"
    }
  ],
  "current_version": 1
}
```

#### POST /api/sessions/{id}/rollback
```json
Request:
{
  "version": 0
}

Response:
{
  "success": true,
  "current_version": 0,
  "preview_url": "file:///.../index.html"
}
```

### Service Layer Architecture

```python
class SessionService:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, title: str = None) -> Session:
        """Create new session with UUID"""

    def get_session(self, session_id: str) -> Session | None:
        """Retrieve session by ID"""

    def update_session(self, session_id: str, **kwargs) -> Session:
        """Update session attributes"""

    def list_sessions(self, limit: int = 20, offset: int = 0) -> List[Session]:
        """List sessions sorted by updated_at DESC"""

class VersionService:
    def create_version(self, session_id: str, html: str, description: str) -> Version:
        """Create new version and update session.current_version"""

    def get_version(self, session_id: str, version: int) -> Version | None:
        """Retrieve specific version"""

    def rollback(self, session_id: str, version: int) -> bool:
        """Rollback to previous version"""
```

## Testing Requirements

- [ ] Unit tests for SessionService CRUD operations
- [ ] Test auto-title generation from messages
- [ ] Test version auto-incrementing
- [ ] Test rollback functionality
- [ ] Test filesystem save operations
- [ ] Integration tests for session lifecycle
- [ ] Test concurrent session access

## Notes & Warnings

- **Session IDs**: Use UUID4 for uniqueness
- **Version Numbers**: Always increment, never reuse version numbers
- **Rollback**: Only updates current_version, doesn't delete future versions
- **File Paths**: Always return absolute paths for CLI compatibility
- **Concurrent Access**: SQLite limitations - use connection pooling
- **Auto-Title**: Extract from first user message (max 50 chars)
