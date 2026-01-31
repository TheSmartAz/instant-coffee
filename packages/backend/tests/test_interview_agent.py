import asyncio
import json

from app.agents.interview import InterviewAgent
from app.config import Settings
from app.llm.openai_client import LLMResponse


class DummyInterviewAgent(InterviewAgent):
    def __init__(self, *args, responses=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._responses = list(responses or [])

    async def _call_llm(self, *args, **kwargs):
        if not self._responses:
            raise AssertionError("No mocked responses available")
        return LLMResponse(content=self._responses.pop(0))


def test_interview_state_initialization_and_reset():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    agent = InterviewAgent(None, "session-1", settings)
    assert agent.state.rounds_used == 0
    assert agent.state.collected_info == {}
    assert agent.state.confidence == 0.0

    agent.state.rounds_used = 3
    agent.state.collected_info["page_type"] = "portfolio"
    agent.reset_state()
    assert agent.state.rounds_used == 0
    assert agent.state.collected_info == {}
    assert agent.state.confidence == 0.0


def test_build_messages_includes_history_and_state():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    agent = InterviewAgent(None, "session-1", settings)
    agent.state.collected_info = {"page_type": "portfolio"}
    agent.state.rounds_used = 2
    agent.state.confidence = 0.5
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]

    messages = agent._build_messages(user_message="Need a page", history=history)

    assert messages[0]["role"] == "system"
    assert messages[1]["content"] == "hi"
    assert messages[2]["content"] == "hello"
    last_content = messages[-1]["content"]
    assert "Collected info" in last_content
    assert "Rounds: 2/5" in last_content
    assert "User input: Need a page" in last_content


def test_parse_response_with_valid_json():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    agent = InterviewAgent(None, "session-1", settings)
    payload = {
        "message": "What style do you want?",
        "is_complete": False,
        "confidence": 0.6,
        "collected_info": {"purpose": "portfolio"},
    }
    parsed = agent._parse_response(json.dumps(payload))
    assert parsed["message"] == "What style do you want?"
    assert parsed["is_complete"] is False
    assert parsed["confidence"] == 0.6
    assert parsed["collected_info"] == {"purpose": "portfolio"}


def test_parse_response_with_invalid_json():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    agent = InterviewAgent(None, "session-1", settings)
    parsed = agent._parse_response("Not JSON at all")
    assert parsed["message"] == "Not JSON at all"
    assert parsed["is_complete"] is False
    assert parsed["confidence"] == 0.0
    assert parsed["collected_info"] == {}


def test_max_rounds_enforced_without_llm_call():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    agent = DummyInterviewAgent(None, "session-1", settings, responses=[])
    agent.state.rounds_used = agent.state.max_rounds

    result = asyncio.run(agent.process("hi", history=[]))
    assert result.is_complete is True
    assert result.rounds_used == agent.state.max_rounds


def test_interview_flow_with_mocked_llm():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    responses = [
        json.dumps(
            {
                "message": "What style do you want?",
                "is_complete": False,
                "confidence": 0.4,
                "collected_info": {"page_type": "portfolio"},
            }
        ),
        json.dumps(
            {
                "message": "Great, I have enough info.",
                "is_complete": True,
                "confidence": 0.9,
                "collected_info": {"style": "minimal"},
            }
        ),
    ]
    agent = DummyInterviewAgent(None, "session-1", settings, responses=responses)

    first = asyncio.run(agent.process("I need a portfolio", history=[]))
    assert first.is_complete is False
    assert agent.state.rounds_used == 1
    assert agent.state.collected_info["page_type"] == "portfolio"

    second = asyncio.run(agent.process("Minimal style", history=[]))
    assert second.is_complete is True
    assert agent.should_generate() is True
    assert agent.get_collected_info()["style"] == "minimal"


def test_max_rounds_forces_completion():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    responses = [
        json.dumps(
            {
                "message": "Another question?",
                "is_complete": False,
                "confidence": 0.2,
                "collected_info": {"audience": "general"},
            }
        )
    ]
    agent = DummyInterviewAgent(None, "session-1", settings, responses=responses)
    agent.state.rounds_used = agent.state.max_rounds - 1

    result = asyncio.run(agent.process("Need help", history=[]))
    assert result.is_complete is True
    assert result.message == "Thanks! I have enough to proceed with generation."
