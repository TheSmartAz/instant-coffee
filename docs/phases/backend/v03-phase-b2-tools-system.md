# Phase B2: Tools System

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: B5-B7 (Agent Implementations), B8 (Tool Event Integration)

## Goal

Define the Tool schema and create predefined tools (filesystem_write, filesystem_read, validate_html) that can be used by LLM agents through function calling.

## Detailed Tasks

### Task 1: Create Tool Schema

**Description**: Define the Tool class and supporting data structures.

**Implementation Details**:
- [ ] Create `packages/backend/app/llm/tools.py`
- [ ] Define `Tool` class with name, description, parameters
- [ ] Implement `to_openai_format()` method for OpenAI function calling
- [ ] Define parameter dataclasses (WriteFileParams, ReadFileParams, etc.)

**Files to create**:
- `packages/backend/app/llm/tools.py`

**Acceptance Criteria**:
- [ ] Tool can be converted to OpenAI format
- [ ] Parameters are properly typed
- [ ] Schema validation works correctly

### Task 2: Define ToolResult Class

**Description**: Create a structured result class for tool execution.

**Implementation Details**:
- [ ] Define `ToolResult` dataclass
- [ ] Include success, output, and error fields
- [ ] Implement `to_dict()` method for JSON serialization
- [ ] Ensure proper handling of None values

**Acceptance Criteria**:
- [ ] ToolResult serializes to JSON correctly
- [ ] Success/failure is clearly indicated
- [ ] Error messages are preserved

### Task 3: Implement filesystem_write Tool

**Description**: Tool for writing content to files.

**Implementation Details**:
- [ ] Define FILESYSTEM_WRITE_TOOL with schema
- [ ] Include path, content, encoding parameters
- [ ] Set encoding to "utf-8" or "gbk"
- [ ] Mark path and content as required

**Acceptance Criteria**:
- [ ] Tool description is clear for LLM
- [ ] Parameters match expected usage
- [ ] OpenAI format is valid

### Task 4: Implement filesystem_read Tool

**Description**: Tool for reading content from files.

**Implementation Details**:
- [ ] Define FILESYSTEM_READ_TOOL with schema
- [ ] Include path, encoding parameters
- [ ] Set encoding to "utf-8" or "gbk"
- [ ] Mark path as required

**Acceptance Criteria**:
- [ ] Tool description is clear for LLM
- [ ] Parameters match expected usage
- [ ] OpenAI format is valid

### Task 5: Implement validate_html Tool

**Description**: Tool for validating HTML against mobile standards.

**Implementation Details**:
- [ ] Define VALIDATE_HTML_TOOL with schema
- [ ] Include html parameter (required)
- [ ] Document mobile-first validation criteria

**Acceptance Criteria**:
- [ ] Tool describes mobile validation clearly
- [ ] HTML parameter is properly defined

### Task 6: Create Tool Registry Functions

**Description**: Helper functions to retrieve available tools.

**Implementation Details**:
- [ ] Implement `get_filesystem_tools()` returning filesystem tools
- [ ] Implement `get_all_tools()` returning all available tools
- [ ] Export all symbols in `__all__`

**Acceptance Criteria**:
- [ ] Functions return lists of Tool objects
- [ ] All exports are properly declared

## Technical Specifications

### Tool Class Definition

```python
class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters

    def to_openai_format(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
```

### Tool Schema Example

```python
FILESYSTEM_WRITE_TOOL = Tool(
    name="filesystem_write",
    description="Write content to a file. Use this to save generated HTML or other files.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The file path to write to",
            },
            "content": {
                "type": "string",
                "description": "The content to write",
            },
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)",
                "enum": ["utf-8", "gbk"],
                "default": "utf-8",
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    },
)
```

### ToolResult Definition

```python
@dataclass
class ToolResult:
    success: bool
    output: Any = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"success": self.success}
        if self.output is not None:
            result["output"] = self.output
        if self.error is not None:
            result["error"] = self.error
        return result
```

## Testing Requirements

- [ ] Unit test for Tool.to_openai_format()
- [ ] Unit test for ToolResult.to_dict()
- [ ] Unit test for get_filesystem_tools()
- [ ] Unit test for get_all_tools()
- [ ] Validation test for tool schemas against OpenAI spec

## Notes & Warnings

1. **Security**: Tool handlers must validate paths to prevent directory traversal
2. **File Types**: Restrict file types to safe extensions (.html, .css, .js)
3. **Parameter Validation**: Always validate parameters in handlers, not just in schema
4. **Error Messages**: Return clear error messages to LLM for decision-making
5. **Tool Descriptions**: Write clear, concise descriptions that help the LLM understand when to use each tool
