# Phase B6: GenerationAgent Implementation

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B2 (Tools System), B3 (BaseAgent Enhancement), B4 (Agent Prompts)
  - **Blocks**: None

## Goal

Implement the GenerationAgent with real LLM calls, tool support for file operations, and HTML extraction with versioning support.

## Detailed Tasks

### Task 1: Implement GenerationAgent Class Structure

**Description**: Set up the GenerationAgent with HTML tracking.

**Implementation Details**:
- [ ] Modify `packages/backend/app/agents/generation.py`
- [ ] Define GenerationProgress dataclass
- [ ] Define GenerationResult dataclass
- [ ] Set agent_type = "generation"
- [ ] Initialize _current_html tracking

**Files to modify**:
- `packages/backend/app/agents/generation.py`

**Acceptance Criteria**:
- [ ] GenerationResult includes html, preview_url, filepath, token_usage
- [ ] Agent initializes correctly
- [ ] HTML tracking variable exists

### Task 2: Implement generate() Method

**Description**: Main method for generating HTML pages.

**Implementation Details**:
- [ ] Implement `generate()` async method
- [ ] Build message list with requirements and history
- [ ] Get filesystem tools from get_filesystem_tools()
- [ ] Create tool_handlers with filesystem_write
- [ ] Call `_call_llm_with_tools()`
- [ ] Extract HTML from response
- [ ] Save HTML to filesystem
- [ ] Return GenerationResult

**Acceptance Criteria**:
- [ ] System prompt is from get_generation_prompt()
- [ ] Tools are available to LLM
- [ ] HTML is extracted correctly
- [ ] File is saved with versioning

### Task 3: Implement _extract_html()

**Description**: Extract HTML from LLM response using multiple strategies.

**Implementation Details**:
- [ ] Strategy 1: Find <HTML_OUTPUT>...</HTML_OUTPUT> markers
- [ ] Strategy 2: Find <!DOCTYPE html>...</html>
- [ ] Strategy 3: Find <html>...</html> with fuzzy matching
- [ ] Return empty string if no HTML found
- [ ] Log warning when extraction fails

**Acceptance Criteria**:
- [ ] Special marker extraction works (highest priority)
- [ ] DOCTYPE extraction works as fallback
- [ ] Fuzzy html tag matching as final fallback
- [ ] Empty string returned when no HTML found

### Task 4: Implement _save_html()

**Description**: Save HTML to filesystem with session organization.

**Implementation Details**:
- [ ] Use FilesystemService for saving
- [ ] Create session-specific directory
- [ ] Save as index.html (current preview)
- [ ] Return absolute file path
- [ ] Generate file:// URI for preview

**Acceptance Criteria**:
- [ ] File is saved in correct location
- [ ] Path is absolute
- [ ] Preview URL is valid file:// URI

### Task 5: Implement _write_file_handler()

**Description**: Tool handler for filesystem_write with versioning.

**Implementation Details**:
- [ ] Create async handler function
- [ ] Save as index.html (current, overwrites)
- [ ] Save as v{timestamp}_{filename} (version history)
- [ ] Return success response with paths
- [ ] Validate path is within output_dir

**Acceptance Criteria**:
- [ ] Current preview is always index.html
- [ ] Version files have unique timestamps
- [ ] Handler returns structured response
- [ ] Path validation prevents traversal

### Task 6: Implement _build_messages()

**Description**: Construct message list for generation.

**Implementation Details**:
- [ ] Start with system prompt
- [ ] Include conversation history
- [ ] Format requirements clearly
- [ ] Include current HTML if modifying (not initial generation)

**Acceptance Criteria**:
- [ ] System prompt from get_generation_prompt()
- [ ] Requirements are clearly formatted
- [ ] History messages have correct role/content
- [ ] Current HTML is included for modifications

### Task 7: Implement generate_with_progress() (Optional)

**Description**: Alternative method with explicit progress callback.

**Implementation Details**:
- [ ] Accept on_progress callback parameter
- [ ] Use streaming LLM call
- [ ] Emit progress events during generation
- [ ] Calculate progress based on response length

**Acceptance Criteria**:
- [ ] Progress callback is called periodically
- [ ] Progress value increases from 10 to 90
- [ ] Final result is same as generate()

## Technical Specifications

### GenerationResult Dataclass

```python
@dataclass
class GenerationResult:
    html: str
    preview_url: str
    filepath: str
    token_usage: Optional[dict] = None
```

### generate() Method Signature

```python
class GenerationAgent(BaseAgent):
    agent_type = "generation"

    async def generate(
        self,
        *,
        requirements: str,
        output_dir: str,
        history: Optional[Sequence[dict]] = None,
        current_html: Optional[str] = None,
        stream: bool = True,
    ) -> GenerationResult:
        """
        Generate a mobile-optimized HTML page.

        Args:
            requirements: Generation requirements (from Interview)
            output_dir: Output directory path
            history: Conversation history
            current_html: Current HTML (for incremental generation)
            stream: Whether to use streaming output

        Returns:
            GenerationResult with generated HTML and metadata
        """
```

### HTML Extraction Strategies

```python
def _extract_html(self, content: str) -> str:
    """
    Extract HTML from LLM response.

    Priority order:
    1. <HTML_OUTPUT>...</HTML_OUTPUT> markers (most reliable)
    2. <!DOCTYPE html>...</html> standard format
    3. <html>...</html> fuzzy match (fallback)

    Returns:
        Extracted HTML or empty string if not found.
    """
```

### Filesystem Tool Handler Response

```python
{
    "success": True,
    "preview_path": "/path/to/session/index.html",
    "version_path": "v1234567890_index.html",
    "version": 1234567890
}
```

## Testing Requirements

- [ ] Unit test for _extract_html() with all strategies
- [ ] Unit test for _save_html() path handling
- [ ] Unit test for _build_messages() with/without history
- [ ] Unit test for _write_file_handler() response format
- [ ] Integration test with mocked LLM client
- [ ] Integration test with real filesystem operations
- [ ] Integration test for complete generation flow

## Notes & Warnings

1. **HTML Extraction**: The <HTML_OUTPUT> marker is most reliable; train prompts to use it
2. **File Paths**: Always use absolute paths for preview URLs
3. **Versioning**: Version timestamps should be Unix timestamps for sorting
4. **Tool Availability**: Ensure tools are properly registered before calling
5. **Stream Option**: Streaming may not include usage; consider non-streaming for accurate tracking
6. **Path Security**: Validate all paths in handlers to prevent directory traversal
