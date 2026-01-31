import asyncio
import time
from pathlib import Path

import pytest

from app.agents import RefinementAgent
from app.config import Settings
from app.llm.openai_client import LLMResponse, TokenUsage


def _make_agent() -> RefinementAgent:
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    return RefinementAgent(None, "session-1", settings)


def test_extract_html_strategies():
    agent = _make_agent()
    marker_content = (
        "<HTML_OUTPUT>\n<!DOCTYPE html>\n<html><body>Marker</body></html>\n</HTML_OUTPUT>"
    )
    assert agent._extract_html(marker_content).startswith("<!DOCTYPE html>")

    doctype_content = "prefix <!DOCTYPE html><html><body>Doc</body></html> suffix"
    assert agent._extract_html(doctype_content).startswith("<!DOCTYPE html>")

    html_only = "prefix <html><body>Only</body></html> suffix"
    assert agent._extract_html(html_only).startswith("<html>")

    assert agent._extract_html("no html here") == ""


def test_build_messages_format():
    agent = _make_agent()
    history = [
        {"role": "user", "content": "Earlier request"},
        {"role": "assistant", "content": "Earlier response"},
    ]
    messages = agent._build_messages(
        user_input="Change title",
        current_html="<html><body>Old</body></html>",
        history=history,
    )
    assert messages[0]["role"] == "system"
    assert messages[1]["content"] == "Earlier request"
    assert messages[2]["content"] == "Earlier response"
    final = messages[-1]["content"]
    assert "Current HTML:\n<html><body>Old</body></html>" in final
    assert "User modification request:\nChange title" in final


def test_save_html_versioning(tmp_path, monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(time, "time", lambda: 1234567890)
    path, preview_url = agent._save_html(html="content", output_dir=str(tmp_path))
    assert path.exists()
    assert path.name == "index.html"
    version_path = tmp_path / "session-1" / "v1234567890000_refinement.html"
    assert version_path.exists()
    assert preview_url == path.as_uri()


def test_write_file_handler_writes_and_versions(tmp_path, monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(time, "time", lambda: 2222)
    handler = agent._write_file_handler(str(tmp_path))
    result = asyncio.run(handler(path="index.html", content="hello", encoding="utf-8"))
    assert result.success is True
    output = result.output
    assert Path(output["path"]).exists()
    assert Path(output["version_path"]).name == "v2222000_index.html"
    assert Path(output["version_path"]).read_text(encoding="utf-8") == "hello"


def test_write_file_handler_rejects_traversal(tmp_path):
    agent = _make_agent()
    handler = agent._write_file_handler(str(tmp_path))
    with pytest.raises(ValueError):
        asyncio.run(handler(path="../oops.html", content="nope"))


def test_refine_integration_with_mocked_llm(tmp_path, monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(time, "time", lambda: 4242)

    async def fake_call_llm_with_tools(*args, **kwargs):
        return LLMResponse(
            content=(
                "<HTML_OUTPUT>\n<!DOCTYPE html>"
                "<html><body>Modified</body></html>\n</HTML_OUTPUT>"
            ),
            token_usage=TokenUsage(
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                cost_usd=0.01,
            ),
        )

    monkeypatch.setattr(agent, "_call_llm_with_tools", fake_call_llm_with_tools)
    result = asyncio.run(
        agent.refine(
            user_input="Update body",
            current_html="<html><body>Old</body></html>",
            output_dir=str(tmp_path),
        )
    )
    assert "Modified" in result.html
    assert result.html != "<html><body>Old</body></html>"
    assert Path(result.filepath).exists()
    assert (tmp_path / "session-1" / "v4242000_refinement.html").exists()
    assert result.token_usage == {
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
        "cost_usd": 0.01,
    }
