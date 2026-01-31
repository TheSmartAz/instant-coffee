from app.agents import (
    GenerationAgent,
    InterviewAgent,
    RefinementAgent,
    get_generation_prompt,
    get_interview_prompt,
    get_refinement_prompt,
)
from app.config import Settings


def test_interview_agent_has_system_prompt():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    agent = InterviewAgent(None, "session-1", settings)
    assert agent.system_prompt == get_interview_prompt()


def test_generation_agent_has_system_prompt():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    agent = GenerationAgent(None, "session-1", settings)
    assert agent.system_prompt == get_generation_prompt()


def test_refinement_agent_has_system_prompt():
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    agent = RefinementAgent(None, "session-1", settings)
    assert agent.system_prompt == get_refinement_prompt()
