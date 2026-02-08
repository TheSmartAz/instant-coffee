import asyncio

from app.agents.base import BaseAgent
from app.config import Settings
from app.events.emitter import EventEmitter
from app.events.types import EventType
from app.services.tool_policy import ToolPolicyContext, ToolPolicyService


def test_command_whitelist_blocks_in_enforce_mode(tmp_path) -> None:
    settings = Settings(
        tool_policy_mode="enforce",
        tool_policy_allowed_cmd_prefixes=["npm", "node"],
    )
    service = ToolPolicyService(settings, project_root=tmp_path)
    context = ToolPolicyContext(tool_name="exec_command", arguments={"cmd": "rm -rf /"})

    findings = service.pre_tool_use(context)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.action == "block"
    assert finding.policy == "command_whitelist"


def test_command_whitelist_warns_in_log_only_mode(tmp_path) -> None:
    settings = Settings(
        tool_policy_mode="log_only",
        tool_policy_allowed_cmd_prefixes=["npm", "node"],
    )
    service = ToolPolicyService(settings, project_root=tmp_path)
    context = ToolPolicyContext(tool_name="exec_command", arguments={"cmd": "rm -rf /"})

    findings = service.pre_tool_use(context)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.action == "warn"
    assert finding.policy == "command_whitelist"


def test_path_boundary_blocks_outside_project(tmp_path) -> None:
    settings = Settings(tool_policy_mode="enforce")
    service = ToolPolicyService(settings, project_root=tmp_path)
    context = ToolPolicyContext(tool_name="filesystem_write", arguments={"path": "../../etc/passwd"})

    findings = service.pre_tool_use(context)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.action == "block"
    assert finding.policy == "path_boundary"


def test_sensitive_content_detected_in_pre_and_post(tmp_path) -> None:
    settings = Settings(tool_policy_mode="enforce")
    service = ToolPolicyService(settings, project_root=tmp_path)

    pre_findings = service.pre_tool_use(
        ToolPolicyContext(
            tool_name="dummy_tool",
            arguments={"api_key": "sk-12345678901234567890"},
        )
    )
    assert pre_findings
    assert pre_findings[0].action == "block"
    assert pre_findings[0].policy == "sensitive_content"

    post = service.post_tool_use(
        ToolPolicyContext(tool_name="dummy_tool", arguments={}),
        {
            "success": True,
            "output": "Authorization: Bearer abcdefghijklmnopqrstuv",
        },
    )
    assert post.findings
    assert post.findings[0].action == "block"
    assert post.findings[0].policy == "sensitive_content"


def test_large_output_truncation(tmp_path) -> None:
    settings = Settings(
        tool_policy_mode="log_only",
        tool_policy_large_output_bytes=256,
    )
    service = ToolPolicyService(settings, project_root=tmp_path)

    post = service.post_tool_use(
        ToolPolicyContext(tool_name="dummy_tool", arguments={}),
        {
            "success": True,
            "output": "x" * 2000,
        },
    )

    assert post.result["success"] is True
    assert isinstance(post.result["output"], dict)
    assert post.result["output"]["truncated"] is True
    assert any(item.policy == "large_output_truncate" for item in post.findings)


def test_policy_mode_off_skips_checks(tmp_path) -> None:
    settings = Settings(tool_policy_mode="off")
    service = ToolPolicyService(settings, project_root=tmp_path)
    context = ToolPolicyContext(tool_name="exec_command", arguments={"cmd": "rm -rf /"})

    pre_findings = service.pre_tool_use(context)
    post = service.post_tool_use(context, {"success": True, "output": "x" * 5000})

    assert pre_findings == []
    assert post.findings == []
    assert post.result["success"] is True
    assert isinstance(post.result["output"], str)


def test_base_agent_blocks_tool_call_in_enforce_mode() -> None:
    settings = Settings(
        tool_policy_mode="enforce",
        tool_policy_allowed_cmd_prefixes=["npm", "node"],
    )
    emitter = EventEmitter(session_id="session-1", run_id="run-1")
    agent = BaseAgent(
        db=None,
        session_id="session-1",
        settings=settings,
        event_emitter=emitter,
        agent_id="agent-1",
        task_id="task-1",
    )

    called = {"value": False}

    async def handler(cmd: str):
        called["value"] = True
        return {"success": True, "output": {"ok": cmd}}

    wrapped = agent._wrap_tool_handler("exec_command", handler)
    result = asyncio.run(wrapped(cmd="rm -rf /"))

    assert result["success"] is False
    assert called["value"] is False

    events = emitter.get_events()
    event_types = [event.type.value for event in events]
    assert EventType.TOOL_POLICY_BLOCKED.value in event_types

    blocked = next(event for event in events if event.type.value == EventType.TOOL_POLICY_BLOCKED.value)
    assert blocked.run_id == "run-1"


def test_base_agent_warns_but_allows_in_log_only_mode() -> None:
    settings = Settings(
        tool_policy_mode="log_only",
        tool_policy_allowed_cmd_prefixes=["npm", "node"],
    )
    emitter = EventEmitter(session_id="session-1", run_id="run-1")
    agent = BaseAgent(
        db=None,
        session_id="session-1",
        settings=settings,
        event_emitter=emitter,
        agent_id="agent-1",
        task_id="task-1",
    )

    async def handler(cmd: str):
        return {"success": True, "output": {"ok": cmd}}

    wrapped = agent._wrap_tool_handler("exec_command", handler)
    result = asyncio.run(wrapped(cmd="rm -rf /"))

    assert result["success"] is True

    events = emitter.get_events()
    event_types = [event.type.value for event in events]
    assert EventType.TOOL_POLICY_WARN.value in event_types
    assert EventType.TOOL_RESULT.value in event_types
