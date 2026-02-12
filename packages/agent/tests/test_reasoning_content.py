from __future__ import annotations

import json
from pathlib import Path

from ic.llm.provider import Message, _clean_messages_for_api
from ic.soul.context import Context
from ic.soul.engine import _truncate_tool_call_args


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


def test_clean_messages_sanitizes_malformed_tool_call_arguments():
    messages = [{
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "write_file",
                "arguments": "{\"content\":\"<html>",
            },
        }],
    }]

    cleaned = _clean_messages_for_api(messages)
    args = cleaned[0]["tool_calls"][0]["function"]["arguments"]
    payload = json.loads(args)

    assert payload["_invalid_json_args"] is True
    assert payload["original_length"] > 0


def test_truncate_tool_call_args_replaces_invalid_json_with_valid_payload():
    tool_calls = [{
        "id": "call_1",
        "name": "write_file",
        "arguments": "{\"content\":\"<html>",
    }]

    truncated = _truncate_tool_call_args(tool_calls)
    repaired_args = truncated[0]["arguments"]
    payload = json.loads(repaired_args)

    assert payload["_invalid_json_args"] is True
    assert "original_length" in payload
