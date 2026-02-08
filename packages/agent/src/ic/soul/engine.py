"""Engine - the core agentic loop with multi-agent support."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from ic.config import Config, AgentConfig
from ic.llm.provider import LLMProvider, Message, create_provider
from ic.llm.stream import StreamEvent, StreamEventType, StreamHandler
from ic.soul.context import Context
from ic.soul.toolset import Toolset
from ic.ui.io import UserIO


@dataclass
class TurnResult:
    """Result of a single agent turn."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)


class Engine:
    """Core agentic engine with streaming and sub-agent support."""

    def __init__(
        self,
        config: Config,
        agent_config: AgentConfig | None = None,
        workspace: str | None = None,
        user_io: UserIO | None = None,
        on_text_delta: Callable[[str], Awaitable[None] | None] | None = None,
        on_tool_call: Callable[[str, dict], Awaitable[None] | None] | None = None,
        on_tool_result: Callable[[str, str], Awaitable[None] | None] | None = None,
        on_sub_agent_start: Callable[[str], Awaitable[None] | None] | None = None,
        on_sub_agent_end: Callable[[str], Awaitable[None] | None] | None = None,
    ):
        self.config = config
        self.agent_config = agent_config or config.agents.get("main", AgentConfig())
        self.context = Context(system_prompt=self.agent_config.system_prompt)
        self.toolset = Toolset()
        self.workspace = workspace
        self.user_io = user_io
        self._provider: LLMProvider | None = None
        self._running = False
        self._total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

        # Callbacks
        self.on_text_delta = on_text_delta
        self.on_tool_call = on_tool_call
        self.on_tool_result = on_tool_result
        self.on_sub_agent_start = on_sub_agent_start
        self.on_sub_agent_end = on_sub_agent_end

    def setup(self):
        """Initialize provider and load tools."""
        from pathlib import Path

        model_config = self.config.get_model(self.agent_config.model)
        self._provider = create_provider(model_config)
        ws = Path(self.workspace) if self.workspace else None
        self.toolset.load_from_paths(
            self.agent_config.tools,
            engine=self,
            workspace=ws,
            user_io=self.user_io,
        )

    async def run_turn(self, user_input: str) -> TurnResult:
        """Run a full agentic turn: user input → LLM → tools → repeat until done."""
        self.context.add_user(user_input)
        self._running = True
        turn_result = TurnResult()
        step = 0

        while self._running and step < self.agent_config.max_turns:
            step += 1
            step_result = await self._step()

            turn_result.text += step_result.get("text", "")
            turn_result.tool_calls.extend(step_result.get("tool_calls", []))
            turn_result.tool_results.extend(step_result.get("tool_results", []))

            # Accumulate usage
            usage = step_result.get("usage", {})
            for k in self._total_usage:
                self._total_usage[k] += usage.get(k, 0)
            turn_result.usage = dict(self._total_usage)

            # If no tool calls, the turn is complete
            if not step_result.get("tool_calls"):
                turn_result.finish_reason = step_result.get("finish_reason", "stop")
                break

            # Context compaction if needed
            if self.context.token_estimate > 100_000:
                self.context.compact()

        self._running = False
        return turn_result

    async def _step(self) -> dict[str, Any]:
        """Execute a single LLM call + tool execution step."""
        assert self._provider is not None

        messages = self.context.get_messages()
        tools_schema = self.toolset.to_openai_schemas() or None

        # Collect streaming response
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        usage = {}
        finish_reason = ""

        async for chunk in self._provider.chat(messages, tools=tools_schema):
            ctype = chunk["type"]

            if ctype == "text_delta":
                delta = chunk["data"]
                text_parts.append(delta)
                if self.on_text_delta:
                    await self._call(self.on_text_delta, delta)

            elif ctype == "text":
                pass  # Already accumulated via deltas

            elif ctype == "tool_call":
                tool_calls.append(chunk["data"])

            elif ctype == "done":
                usage = chunk["data"].get("usage", {})
                finish_reason = chunk["data"].get("finish_reason", "")

        full_text = "".join(text_parts)

        # Build assistant message for context
        assistant_tool_calls = None
        if tool_calls:
            assistant_tool_calls = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in tool_calls
            ]
        self.context.add_assistant(
            content=full_text or None,
            tool_calls=assistant_tool_calls,
        )

        # Execute tools
        tool_results = []
        for tc in tool_calls:
            if self.on_tool_call:
                await self._call(self.on_tool_call, tc["name"], tc)

            result = await self._execute_tool(tc["name"], tc["arguments"])
            tool_results.append({"tool_call_id": tc["id"], "output": result})
            self.context.add_tool_result(tc["id"], result)

            if self.on_tool_result:
                await self._call(self.on_tool_result, tc["name"], result)

        return {
            "text": full_text,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "usage": usage,
            "finish_reason": finish_reason,
        }

    async def _execute_tool(self, name: str, arguments: str) -> str:
        """Execute a tool by name with JSON arguments."""
        tool = self.toolset.get(name)
        if not tool:
            return f"Error: Unknown tool '{name}'"
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
            result = await tool.execute(**args)
            return result.to_content()
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON arguments: {e}"
        except Exception as e:
            return f"Error executing {name}: {e}"

    async def run_sub_agent(
        self,
        task: str,
        model_name: str | None = None,
        max_turns: int = 30,
    ) -> str:
        """Run a sub-agent for a specific task. Returns the final text output."""
        sub_config = AgentConfig(
            name=f"sub-{uuid.uuid4().hex[:8]}",
            system_prompt=(
                "You are a focused sub-agent. Complete the assigned task efficiently.\n"
                "You have access to file, shell, and think tools.\n"
                "When done, provide a clear summary of what you accomplished."
            ),
            model=model_name or self.agent_config.model,
            tools=[
                "ic.tools.file:ReadFile",
                "ic.tools.file:WriteFile",
                "ic.tools.file:EditFile",
                "ic.tools.file:GlobFiles",
                "ic.tools.file:GrepFiles",
                "ic.tools.shell:Shell",
                "ic.tools.think:Think",
            ],
            max_turns=max_turns,
        )

        if self.on_sub_agent_start:
            await self._call(self.on_sub_agent_start, task)

        sub_engine = Engine(
            config=self.config,
            agent_config=sub_config,
            workspace=self.workspace,
            user_io=self.user_io,
            on_text_delta=self.on_text_delta,
            on_tool_call=self.on_tool_call,
            on_tool_result=self.on_tool_result,
        )
        sub_engine.setup()

        result = await sub_engine.run_turn(task)

        if self.on_sub_agent_end:
            await self._call(self.on_sub_agent_end, result.text)

        return result.text or "(Sub-agent completed with no text output)"

    async def _call(self, fn: Callable, *args: Any):
        """Call a callback, handling both sync and async."""
        result = fn(*args)
        if hasattr(result, "__await__"):
            await result

    def stop(self):
        self._running = False
