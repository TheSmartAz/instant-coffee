# Phase B4: Export Service

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Low
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: D1 (Core Schema), B2 (Session Management)
  - **Blocks**: F3 (Export Command)

## Goal

Implement export functionality to save generated HTML to user-specified locations with proper file structure and optional metadata.

## Detailed Tasks

### Task 1: Create Export Service

**Description**: Build the ExportService for exporting sessions to filesystem.

**Implementation Details**:
- [ ] Create ExportService class
- [ ] Implement export_session() with destination path
- [ ] Support exporting specific version or current version
- [ ] Generate clean filenames (index.html)
- [ ] Create directory structure if needed
- [ ] Handle file overwrite confirmation

**Files to modify/create**:
- `packages/backend/app/services/export.py`

**Acceptance Criteria**:
- [ ] HTML is exported to specified directory
- [ ] Supports exporting any version
- [ ] Creates directories if they don't exist
- [ ] Returns absolute path of exported file
- [ ] Handles permission errors gracefully

---

### Task 2: Create Export API Endpoint

**Description**: Build REST API endpoint for export operations.

**Implementation Details**:
- [ ] Implement POST /api/export
- [ ] Accept session_id, version, output_dir parameters
- [ ] Validate output directory path
- [ ] Return export status and file path

**Files to modify/create**:
- `packages/backend/app/api/export.py`

**Acceptance Criteria**:
- [ ] Endpoint validates all parameters
- [ ] Returns success status and file path
- [ ] Handles errors (invalid session, permission issues)
- [ ] Works for all versions

## Technical Specifications

### API Endpoint

#### POST /api/export
```json
Request:
{
  "session_id": "abc123",
  "version": 1,  // optional, defaults to current_version
  "output_dir": "./my-page"
}

Response:
{
  "success": true,
  "file_path": "/Users/username/my-page/index.html",
  "session_id": "abc123",
  "version": 1
}
```

### Export Service Implementation

```python
class ExportService:
    def export_session(
        self,
        session_id: str,
        output_dir: str,
        version: int = None
    ) -> Dict[str, Any]:
        """
        Export session HTML to specified directory

        Args:
            session_id: Session to export
            output_dir: Destination directory
            version: Version to export (None = current)

        Returns:
            Dict with success status and file path
        """
        # Get session
        # Get version (current or specified)
        # Create output directory
        # Write HTML to index.html
        # Return absolute file path
```

## Testing Requirements

- [ ] Test exporting current version
- [ ] Test exporting specific historical version
- [ ] Test directory creation
- [ ] Test file overwriting
- [ ] Test permission errors
- [ ] Test invalid session/version handling

## Notes & Warnings

- **File Overwrite**: Always overwrite existing index.html without confirmation (CLI will handle)
- **Absolute Paths**: Always return absolute file paths
- **Permissions**: Check write permissions before attempting export
- **Single File**: Only export index.html (no external resources yet)
