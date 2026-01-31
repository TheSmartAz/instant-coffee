from app.llm.tools import (
    FILESYSTEM_READ_TOOL,
    FILESYSTEM_WRITE_TOOL,
    VALIDATE_HTML_TOOL,
    Tool,
    ToolResult,
    get_all_tools,
    get_filesystem_tools,
)


def test_tool_to_openai_format():
    tool = Tool(
        name="test_tool",
        description="do stuff",
        parameters={"type": "object", "properties": {}, "required": []},
    )
    payload = tool.to_openai_format()
    assert payload["type"] == "function"
    assert payload["function"]["name"] == "test_tool"
    assert payload["function"]["description"] == "do stuff"


def test_tool_result_to_dict():
    result = ToolResult(success=True, output={"ok": True})
    assert result.to_dict() == {"success": True, "output": {"ok": True}}

    error_result = ToolResult(success=False, error="boom")
    assert error_result.to_dict() == {"success": False, "error": "boom"}


def test_get_filesystem_tools():
    tools = get_filesystem_tools()
    names = {tool.name for tool in tools}
    assert names == {"filesystem_write", "filesystem_read"}


def test_get_all_tools():
    tools = get_all_tools()
    names = {tool.name for tool in tools}
    assert names == {"filesystem_write", "filesystem_read", "validate_html"}


def test_tool_constants_are_tool_instances():
    assert isinstance(FILESYSTEM_WRITE_TOOL, Tool)
    assert isinstance(FILESYSTEM_READ_TOOL, Tool)
    assert isinstance(VALIDATE_HTML_TOOL, Tool)
