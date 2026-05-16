import asyncio

from app.engine.db_tools import DBEditFile, DBMultiEditFile, DBWriteFile
from app.engine.event_bridge import EventBridge
from app.events.emitter import EventEmitter
from app.events.types import EventType


def test_plan_mode_write_file_does_not_touch_filesystem(tmp_path) -> None:
    tool = DBWriteFile(workspace=tmp_path, execution_mode="plan")

    result = asyncio.run(tool.execute(file_path="index.html", content="<h1>blocked</h1>"))

    assert result.is_error is True
    assert "Plan only mode" in (result.error or "")
    assert not (tmp_path / "index.html").exists()


def test_plan_mode_edit_file_does_not_mutate_existing_file(tmp_path) -> None:
    target = tmp_path / "index.html"
    target.write_text("<h1>old</h1>", encoding="utf-8")
    tool = DBEditFile(workspace=tmp_path, execution_mode="plan")

    result = asyncio.run(
        tool.execute(file_path="index.html", old_string="old", new_string="new")
    )

    assert result.is_error is True
    assert target.read_text(encoding="utf-8") == "<h1>old</h1>"


def test_plan_mode_multi_edit_file_does_not_mutate_existing_file(tmp_path) -> None:
    target = tmp_path / "index.html"
    target.write_text("<h1>old</h1>", encoding="utf-8")
    tool = DBMultiEditFile(workspace=tmp_path, execution_mode="plan")

    result = asyncio.run(
        tool.execute(
            file_path="index.html",
            edits=[{"old_string": "old", "new_string": "new"}],
        )
    )

    assert result.is_error is True
    assert target.read_text(encoding="utf-8") == "<h1>old</h1>"


def test_plan_mode_write_block_emits_policy_event(tmp_path) -> None:
    emitter = EventEmitter(session_id="session-1", run_id="run-1")
    tool = DBWriteFile(workspace=tmp_path, emitter=emitter, execution_mode="plan")

    asyncio.run(tool.execute(file_path="PRODUCT.md", content="blocked"))

    events = emitter.get_events()
    assert [event.type for event in events] == [EventType.TOOL_POLICY_BLOCKED]
    assert events[0].payload["execution_mode"] == "plan"
    assert events[0].run_id == "run-1"


def test_agent_mode_write_file_still_writes(tmp_path) -> None:
    tool = DBWriteFile(workspace=tmp_path, execution_mode="agent")

    result = asyncio.run(tool.execute(file_path="index.html", content="<h1>ok</h1>"))

    assert result.is_error is False
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == "<h1>ok</h1>"


def test_plan_mode_shell_bridge_blocks_without_approval_event() -> None:
    emitter = EventEmitter(session_id="session-1", run_id="run-1")
    bridge = EventBridge(emitter, "session-1", execution_mode="plan")

    allowed = asyncio.run(bridge.on_before_shell_execute("rm -rf ./dist"))

    assert allowed is False
    events = emitter.get_events()
    assert len(events) == 1
    assert events[0].type == EventType.TOOL_RESULT
    assert events[0].tool_name == "shell"


def test_agent_mode_shell_bridge_emits_and_resolves_approval() -> None:
    async def run() -> list:
        emitter = EventEmitter(session_id="session-1", run_id="run-1")
        bridge = EventBridge(emitter, "session-1", execution_mode="agent")
        pending = asyncio.create_task(bridge.on_before_shell_execute("rm -rf ./dist --force"))
        await asyncio.sleep(0)
        events = emitter.get_events()
        approval = next(event for event in events if event.type == EventType.SHELL_APPROVAL)
        assert bridge.resolve_shell_approval(approval.approval_id, True) is True
        assert await pending is True
        return emitter.get_events()

    events = asyncio.run(run())

    assert [event.type for event in events] == [
        EventType.SHELL_APPROVAL,
        EventType.SHELL_APPROVAL_RESOLVED,
    ]
    assert events[0].execution_mode == "agent"
    assert events[1].approved is True
    assert events[1].status == "approved"


def test_agent_mode_shell_bridge_resolves_approval_from_worker_thread() -> None:
    async def run() -> list:
        emitter = EventEmitter(session_id="session-1", run_id="run-1")
        bridge = EventBridge(emitter, "session-1", execution_mode="agent")
        pending = asyncio.create_task(bridge.on_before_shell_execute("rm -rf ./dist --force"))
        await asyncio.sleep(0)
        events = emitter.get_events()
        approval = next(event for event in events if event.type == EventType.SHELL_APPROVAL)

        resolved = await asyncio.to_thread(
            bridge.resolve_shell_approval,
            approval.approval_id,
            True,
        )

        assert resolved is True
        assert await pending is True
        return emitter.get_events()

    events = asyncio.run(run())

    assert [event.type for event in events] == [
        EventType.SHELL_APPROVAL,
        EventType.SHELL_APPROVAL_RESOLVED,
    ]
    assert events[1].approved is True
    assert events[1].status == "approved"
