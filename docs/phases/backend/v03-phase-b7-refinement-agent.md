# Phase B7: RefinementAgent Implementation

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B2 (Tools System), B3 (BaseAgent Enhancement), B4 (Agent Prompts)
  - **Blocks**: None

## Goal

Implement the RefinementAgent with real LLM calls for modifying existing HTML pages based on user feedback, with versioning support.

## Detailed Tasks

### Task 1: Implement RefinementAgent Class Structure

**Description**: Set up the RefinementAgent.

**Implementation Details**:
- [ ] Modify `packages/backend/app/agents/refinement.py`
- [ ] Define RefinementResult dataclass
- [ ] Set agent_type = "refinement"

**Files to modify**:
- `packages/backend/app/agents/refinement.py`

**Acceptance Criteria**:
- [ ] RefinementResult includes html, preview_url, filepath, token_usage
- [ ] Agent initializes correctly

### Task 2: Implement refine() Method

**Description**: Main method for modifying HTML pages.

**Implementation Details**:
- [ ] Implement `refine()` async method
- [ ] Build message list with user input, current HTML, history
- [ ] Get filesystem tools from get_filesystem_tools()
- [ ] Create tool_handlers with filesystem_write
- [ ] Call `_call_llm_with_tools()`
- [ ] Extract HTML from response
- [ ] Save HTML to filesystem
- [ ] Return RefinementResult

**Acceptance Criteria**:
- [ ] System prompt is from get_refinement_prompt()
- [ ] Current HTML is included in messages
- [ ] User modification request is clear
- [ ] Modified HTML is saved correctly

### Task 3: Implement _extract_html()

**Description**: Extract HTML from LLM response (reuse GenerationAgent logic).

**Implementation Details**:
- [ ] Copy extraction logic from GenerationAgent
- [ ] Strategy 1: <HTML_OUTPUT> markers
- [ ] Strategy 2: <!DOCTYPE html>
- [ ] Strategy 3: <html> fuzzy match

**Acceptance Criteria**:
- [ ] Same extraction behavior as GenerationAgent
- [ ] Empty string on failure

### Task 4: Implement _save_html()

**Description**: Save modified HTML with versioning.

**Implementation Details**:
- [ ] Use FilesystemService for saving
- [ ] Save as index.html (current preview, overwrites)
- [ ] Save as v{timestamp}_refinement.html (version history)
- [ ] Return absolute file path
- [ ] Generate file:// URI for preview

**Acceptance Criteria**:
- [ ] Index.html is always the current version
- [ ] Refinement versions are tracked separately
- [ ] Preview URL is valid

### Task 5: Implement _write_file_handler()

**Description**: Tool handler for saving during refinement.

**Implementation Details**:
- [ ] Create async handler function
- [ ] Save as index.html (current)
- [ ] Save as v{timestamp}_{original_filename}
- [ ] Return success response with paths
- [ ] Validate path security

**Acceptance Criteria**:
- [ ] Returns structured success response
- [ ] Version files are unique
- [ ] Path validation prevents traversal

### Task 6: Implement _build_messages()

**Description**: Construct message list for refinement.

**Implementation Details**:
- [ ] Start with system prompt
- [ ] Include conversation history
- [ ] Include current HTML in message
- [ ] Include user modification request

**Acceptance Criteria**:
- [ ] System prompt from get_refinement_prompt()
- [ ] Current HTML is included (essential for context)
- [ ] User request is clearly separated

## Technical Specifications

### RefinementResult Dataclass

```python
@dataclass
class RefinementResult:
    html: str
    preview_url: str
    filepath: str
    token_usage: Optional[dict] = None
```

### refine() Method Signature

```python
class RefinementAgent(BaseAgent):
    agent_type = "refinement"

    async def refine(
        self,
        *,
        user_input: str,
        current_html: str,
        output_dir: str,
        history: Optional[list] = None,
    ) -> RefinementResult:
        """
        Modify a page based on user feedback.

        Args:
            user_input: User's modification description
            current_html: Current HTML content
            output_dir: Output directory path
            history: Conversation history

        Returns:
            RefinementResult with modified HTML and metadata
        """
```

### Message Structure

```python
[
    {"role": "system", "content": REFINEMENT_SYSTEM_PROMPT},
    # ... history messages ...
    {
        "role": "user",
        "content": "Current HTML:\n{current_html}\n\nUser modification request:\n{user_input}"
    }
]
```

### Version Naming Convention

```
index.html                    # Current preview (always overwritten)
v1234567890_refinement.html   # Version history (unique)
```

## Testing Requirements

- [ ] Unit test for _extract_html() with all strategies
- [ ] Unit test for _save_html() versioning
- [ ] Unit test for _build_messages() format
- [ ] Unit test for _write_file_handler() response
- [ ] Integration test with mocked LLM client
- [ ] Integration test for complete refinement flow
- [ ] Integration test that HTML is actually modified

## Notes & Warnings

1. **HTML Context**: Current HTML MUST be included in messages for context
2. **Version Naming**: Use `_refinement` suffix to distinguish from generation versions
3. **Minimal Changes**: Prompt should emphasize minimal changes to existing HTML
4. **Path Validation**: Same security considerations as GenerationAgent
5. **Tool Usage**: LLM may choose not to use tools; handle gracefully
6. **Preview Update**: index.html should always reflect the latest version
