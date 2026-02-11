from __future__ import annotations

import json
from pathlib import Path

from ic.llm.provider import Message
from ic.soul.context import Context


def test_message_to_dict_includes_reasoning_content():
    msg = Message(
        role="assistant",
        content="",
        tool_calls=[{
            "id": "call_1",
            "type": "function",
            "function": {"name": "echo", "arguments": "{\"text\":\"hi\"}"},
        }],
        reasoning_content="thinking trace",
    )
    payload = msg.to_dict()
    assert payload["reasoning_content"] == "thinking trace"


def test_context_save_load_preserves_reasoning_content(tmp_path: Path):
    ctx = Context(system_prompt="sys")
    ctx.add_assistant(
        content="",
        tool_calls=[{
            "id": "call_1",
            "type": "function",
            "function": {"name": "echo", "arguments": "{\"text\":\"hi\"}"},
        }],
        reasoning_content="tool decision rationale",
    )
    path = tmp_path / "context.jsonl"
    ctx.save(path)

    loaded = Context.load(path, system_prompt="sys")
    assert len(loaded.messages) == 1
    assert loaded.messages[0].reasoning_content == "tool decision rationale"


def test_context_get_messages_backfills_missing_reasoning_for_tool_calls(tmp_path: Path):
    raw = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": "call_1",
            "type": "function",
            "function": {"name": "echo", "arguments": "{\"text\":\"hi\"}"},
        }],
    }
    path = tmp_path / "context.jsonl"
    path.write_text(json.dumps(raw, ensure_ascii=False) + "\n", encoding="utf-8")

    loaded = Context.load(path, system_prompt="sys")
    messages = loaded.get_messages()
    # first message is system prompt, second is assistant tool-call
    assistant = messages[1]
    assert assistant.role == "assistant"
    assert assistant.tool_calls
    assert assistant.reasoning_content == ""
