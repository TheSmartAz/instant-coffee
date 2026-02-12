"""Engine - the core agentic loop with multi-agent support."""

from __future__ import annotations

import asyncio
import httpx
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from openai import APITimeoutError, BadRequestError

from ic.config import Config, AgentConfig, MODEL_PRICING
from ic.llm.provider import LLMProvider, Message, create_provider
from ic.llm.stream import StreamEvent, StreamEventType, StreamHandler
from ic.soul.context import Context
from ic.soul.context_injector import ContextInjector, ContextConfig
from ic.soul.toolset import Toolset
from ic.ui.io import UserIO
from ic.log import LLMCallLogger, log_tool_execution, log_turn


# Maximum characters for tool results in context (per tool type)
_TOOL_RESULT_LIMITS: dict[str, int] = {
    "shell": 15000,
    "grep_files": 8000,
    "read_file": 20000,
    "glob_files": 5000,
}
_DEFAULT_RESULT_LIMIT = 12000


def _truncate_tool_call_args(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Truncate large tool call arguments before storing in context.

    write_file calls carry the full file content in their arguments, which
    can be 50KB+.  Keeping all of that in context wastes tokens and can
    cause the model to return empty responses.  We replace the content
    with a short placeholder so the model knows the file was written but
    doesn't re-read the full content.
    """
    _MAX_ARG_LEN = 2000  # chars — enough for most tool args

    def _invalid_args_payload(name: str, args_text: str) -> str:
        payload: dict[str, Any] = {
            "_invalid_json_args": True,
            "note": "tool arguments were malformed and replaced in context",
            "original_length": len(args_text),
        }
        if name in {"write_file", "edit_file", "multi_edit_file"}:
            file_path_match = re.search(r'"file_path"\s*:\s*"([^"]+)"', args_text)
            if file_path_match:
                payload["file_path"] = file_path_match.group(1)
        return json.dumps(payload, ensure_ascii=False)

    truncated = []
    for tc in tool_calls:
        args_str = tc.get("arguments", "{}")
        name = tc.get("name", "")

        parsed_args: Any | None
        if isinstance(args_str, str):
            try:
                parsed_args = json.loads(args_str)
            except (json.JSONDecodeError, TypeError):
                parsed_args = None
        else:
            parsed_args = args_str

        # Never keep invalid JSON arguments in context; API proxies can reject
        # the next request if assistant tool_calls contain malformed JSON text.
        if parsed_args is None:
            safe_tc = dict(tc)
            safe_tc["arguments"] = _invalid_args_payload(name, args_str if isinstance(args_str, str) else "")
            truncated.append(safe_tc)
            continue

        if isinstance(args_str, str) and len(args_str) <= _MAX_ARG_LEN:
            truncated.append(tc)
            continue

        # Try to parse and selectively truncate
        try:
            args = parsed_args

            if name == "write_file" and isinstance(args, dict) and "content" in args:
                content = args["content"] if isinstance(args.get("content"), str) else str(args.get("content", ""))
                lines = content.count("\n") + 1
                chars = len(content)
                # Replace content with a summary
                args["content"] = (
                    f"[file content: {lines} lines, {chars} chars — "
                    f"truncated from context to save tokens]"
                )
                tc = dict(tc)
                tc["arguments"] = json.dumps(args, ensure_ascii=False)
            elif isinstance(args_str, str) and len(args_str) > _MAX_ARG_LEN:
                # Generic truncation for other tools with huge args.
                tc = dict(tc)
                if isinstance(args, dict):
                    tc["arguments"] = json.dumps(
                        {
                            "_truncated_args": True,
                            "original_length": len(args_str),
                            "keys": sorted(args.keys())[:20],
                        },
                        ensure_ascii=False,
                    )
                else:
                    tc["arguments"] = json.dumps(
                        {
                            "_truncated_args": True,
                            "original_length": len(args_str),
                            "value_type": type(args).__name__,
                        },
                        ensure_ascii=False,
                    )
        except (json.JSONDecodeError, TypeError):
            tc = dict(tc)
            tc["arguments"] = _invalid_args_payload(name, args_str if isinstance(args_str, str) else "")

        truncated.append(tc)
    return truncated


def truncate_tool_result(tool_name: str, output: str) -> str:
    """Truncate tool output using per-tool strategies to save context tokens.

    Strategies:
    - shell: keep first 30 + last 80 lines (errors are usually at the end)
    - grep_files: keep first 50 matches, report total count
    - read_file: keep first N chars with line-boundary cut
    - glob_files: keep first 200 paths
    - default: head + tail character split
    """
    limit = _TOOL_RESULT_LIMITS.get(tool_name, _DEFAULT_RESULT_LIMIT)
    if len(output) <= limit:
        return output

    lines = output.splitlines()

    if tool_name == "shell":
        # Keep first 30 + last 80 lines (errors/exit codes at end)
        if len(lines) > 110:
            head = lines[:30]
            tail = lines[-80:]
            skipped = len(lines) - 110
            return "\n".join(head) + f"\n\n... [{skipped} lines omitted] ...\n\n" + "\n".join(tail)

    elif tool_name == "grep_files":
        # Keep first 50 match lines, report total
        if len(lines) > 50:
            kept = lines[:50]
            return "\n".join(kept) + f"\n\n... [{len(lines) - 50} more matches, {len(lines)} total]"

    elif tool_name == "glob_files":
        # Keep first 200 paths
        if len(lines) > 200:
            return "\n".join(lines[:200]) + f"\n\n... [{len(lines) - 200} more files, {len(lines)} total]"

    # Default: head + tail character split
    half = limit // 2
    return output[:half] + f"\n\n... [{len(output) - limit} chars omitted] ...\n\n" + output[-half:]


@dataclass
class CostTracker:
    """Tracks token usage and estimated cost across a conversation."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost_usd: float = 0.0
    model: str = ""

    def add(self, usage: dict[str, int], model: str = ""):
        """Add usage from a single LLM call."""
        pt = usage.get("prompt_tokens", 0)
        ct = usage.get("completion_tokens", 0)
        self.prompt_tokens += pt
        self.completion_tokens += ct
        m = model or self.model
        pricing = MODEL_PRICING.get(m)
        if pricing and (pt or ct):
            input_cost, output_cost = pricing
            self.total_cost_usd += (pt * input_cost + ct * output_cost) / 1_000_000

    def estimate_from_text(self, text: str, role: str = "output", model: str = ""):
        """Fallback: estimate tokens from text when provider returns no usage."""
        estimated = len(text) // 3
        if role == "input":
            self.prompt_tokens += estimated
        else:
            self.completion_tokens += estimated
        m = model or self.model
        pricing = MODEL_PRICING.get(m)
        if pricing and estimated:
            idx = 0 if role == "input" else 1
            self.total_cost_usd += estimated * pricing[idx] / 1_000_000

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
        }


@dataclass
class TurnResult:
    """Result of a single agent turn."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    cost: dict[str, Any] = field(default_factory=dict)  # {prompt_tokens, completion_tokens, total_cost_usd}


class Engine:
    """Core agentic engine with streaming and sub-agent support."""

    def __init__(
        self,
        config: Config,
        agent_config: AgentConfig | None = None,
        workspace: str | None = None,
        user_io: UserIO | None = None,
        on_text_delta: Callable[[str], Awaitable[None] | None] | None = None,
        on_llm_retry: Callable[[int, int, str], Awaitable[None] | None] | None = None,
        on_tool_call: Callable[[str, dict], Awaitable[None] | None] | None = None,
        on_tool_result: Callable[[str, str], Awaitable[None] | None] | None = None,
        on_tool_progress: Callable[[str, str, int | None], Awaitable[None] | None] | None = None,
        on_sub_agent_start: Callable[[str], Awaitable[None] | None] | None = None,
        on_sub_agent_end: Callable[[str], Awaitable[None] | None] | None = None,
        on_cost_update: Callable[[dict], Awaitable[None] | None] | None = None,
        on_before_shell_execute: Callable[[str], Awaitable[bool] | bool] | None = None,
        context_config: ContextConfig | None = None,
        on_context_compacted: Callable[[dict], Awaitable[None] | None] | None = None,
        on_plan_update: Callable[[dict], Awaitable[None] | None] | None = None,
        project_state_provider: Callable[[], dict | None] | None = None,
    ):
        self.config = config
        self.agent_config = agent_config or config.agents.get("main", AgentConfig())
        self.context = Context(system_prompt=self.agent_config.system_prompt)
        self.toolset = Toolset()
        self.workspace = workspace
        self.user_io = user_io
        self._provider: LLMProvider | None = None
        self._running = False
        self._cancelled = False
        self._current_task: asyncio.Task | None = None  # For cancellation
        self._total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        self._cost_tracker = CostTracker(model=self.agent_config.model)

        # Per-turn cache for read-only tool results
        self._tool_cache: dict[str, str] = {}  # key: "tool_name|sorted_args" → output

        # Per-turn file change tracking
        self._file_changes: list[dict[str, str]] = []

        # Context injection
        self._context_injector = ContextInjector(context_config)
        self._context_injected = False

        # Callbacks
        self.on_text_delta = on_text_delta
        self.on_llm_retry = on_llm_retry
        self.on_tool_call = on_tool_call
        self.on_tool_result = on_tool_result
        self.on_tool_progress = on_tool_progress  # New: progress callback
        self.on_sub_agent_start = on_sub_agent_start
        self.on_sub_agent_end = on_sub_agent_end
        self.on_cost_update = on_cost_update
        self.on_before_shell_execute = on_before_shell_execute
        self.on_context_compacted = on_context_compacted
        self.on_plan_update = on_plan_update
        self._project_state_provider = project_state_provider

        # Sub-agent tool factory: called after sub_engine.setup() to inject
        # custom tools (e.g. DB-backed WriteFile/EditFile).  Signature:
        #   (sub_engine: Engine) -> list[BaseTool]
        self.sub_agent_tool_factory: Callable[[Any], list[Any]] | None = None

    @property
    def file_changes(self) -> list[dict[str, str]]:
        """Return the list of file changes recorded during the current turn."""
        return list(self._file_changes)

    def record_file_change(self, path: str, action: str, summary: str = "") -> None:
        """Record a file change during the current turn."""
        self._file_changes.append({
            "path": path,
            "action": action,
            "summary": summary,
        })

    def setup(self):
        """Initialize provider and load tools."""
        from pathlib import Path
        from ic.soul.skills import SkillLoader

        model_config = self.config.get_model(self.agent_config.model)
        self._provider = create_provider(model_config)

        # Create a separate provider for context compaction (cheaper model)
        compact_model = self.config.model_pointers.resolve("compact", self.agent_config.model)
        compact_config = self.config.get_model(compact_model)
        self._compact_provider = create_provider(compact_config)

        # Initialize skill loader (scans ~/.ic/skills/ and workspace/.ic/skills/)
        skills_dirs = [self.config.data_dir / "skills"]
        ws = Path(self.workspace) if self.workspace else None
        if ws:
            skills_dirs.append(ws / ".ic" / "skills")
        skill_loader = None
        for sd in skills_dirs:
            if sd.exists():
                skill_loader = SkillLoader(sd)
                break
        if skill_loader is None:
            skill_loader = SkillLoader(None)

        self.toolset.load_from_paths(
            self.agent_config.tools,
            engine=self,
            workspace=ws,
            user_io=self.user_io,
            on_before_execute=self.on_before_shell_execute,
            skill_loader=skill_loader,
        )

        # Update ExecuteSkill description with available skills
        skill_tool = self.toolset.get("execute_skill")
        if skill_tool and hasattr(skill_tool, "_update_description"):
            skill_tool._update_description()

    @staticmethod
    def _format_exception(exc: BaseException) -> str:
        """Format exceptions with class name for clearer retry diagnostics."""
        name = type(exc).__name__
        message = str(exc).strip()
        if message:
            return f"{name}: {message}"
        text = repr(exc).strip()
        if text:
            return text
        return f"{name}: <no detail>"

    def _workspace_root(self):
        from pathlib import Path
        if not self.workspace:
            return None
        return Path(self.workspace)

    @staticmethod
    def _looks_like_generation_intent(text: str) -> bool:
        if not text:
            return False
        haystack = text.lower()
        keywords = (
            "generate", "build", "create", "implement", "webpage",
            "web page", "website", "landing page", "html", "index.html",
        )
        return any(token in haystack for token in keywords)

    @staticmethod
    def _looks_like_confirmation_prompt(text: str) -> bool:
        """Detect if the agent is asking the user to confirm before generating."""
        if not text:
            return False
        haystack = text.lower()
        markers = (
            "shall i start",
            "shall i generate",
            "shall i proceed",
            "ready to generate",
            "want me to generate",
            "want me to proceed",
            "want me to start",
            "should i generate",
            "should i proceed",
            "should i start",
            "let me know",
            "would you like me to",
        )
        return any(marker in haystack for marker in markers)

    def _turn_has_generation_signal(
        self,
        user_input: str,
        turn_result: TurnResult,
        step_text: str,
    ) -> bool:
        if self._looks_like_generation_intent(user_input):
            return True
        if self._looks_like_generation_intent(step_text):
            return True

        approval_markers = ("ready to generate", "yes, generate", "yes generate")
        for tool_result in turn_result.tool_results:
            output = str(tool_result.get("output", "")).lower()
            if any(marker in output for marker in approval_markers):
                return True

        for change in self._file_changes:
            if change.get("path", "").endswith("PRODUCT.md"):
                return True
        return False

    def _index_written_this_turn(self) -> bool:
        from pathlib import Path
        for change in self._file_changes:
            try:
                if Path(change.get("path", "")).name == "index.html":
                    return True
            except Exception:
                continue
        return False

    def _should_attempt_generation_recovery(
        self,
        user_input: str,
        turn_result: TurnResult,
        step_result: dict[str, Any],
    ) -> bool:
        if step_result.get("tool_calls"):
            return False

        finish_reason = step_result.get("finish_reason", "")
        if finish_reason not in {"partial", "empty_exhausted", "stop"}:
            return False

        workspace = self._workspace_root()
        if workspace is None:
            return False

        product_doc = workspace / "PRODUCT.md"
        index_file = workspace / "index.html"
        if not product_doc.exists() or index_file.exists():
            return False

        if self._index_written_this_turn():
            return False

        # If the agent is asking the user to confirm before generating,
        # don't force generation recovery — let the user respond.
        step_text = step_result.get("text", "")
        if self._looks_like_confirmation_prompt(step_text):
            return False

        return self._turn_has_generation_signal(
            user_input=user_input,
            turn_result=turn_result,
            step_text=step_text,
        )

    async def _inject_context(self):
        """Inject project context (product doc, files) into the conversation."""
        from pathlib import Path

        if not self.workspace:
            return

        workspace = Path(self.workspace)
        if not workspace.exists():
            return

        injected = await self._context_injector.inject_all(workspace)
        for msg in injected.messages:
            self.context.add_user(msg.content)
        # Mark all injected messages as cacheable (they don't change between turns)
        self.context._cacheable_count = len(injected.messages)

    async def run_turn(self, user_input: str, images: list[dict] | None = None) -> TurnResult:
        """Run a full agentic turn: user input → LLM → tools → repeat until done."""
        # Inject context on first turn (before adding user message)
        if not self._context_injected:
            await self._inject_context()
            self._context_injected = True

        if images:
            self.context.add_user_with_images(user_input, images)
        else:
            self.context.add_user(user_input)
        # Auto-checkpoint before each turn for undo support
        self.context.checkpoint(label=f"turn-{len(self.context._snapshots)}")
        self._running = True
        self._cancelled = False
        self._tool_cache.clear()  # Fresh cache for each turn
        self._file_changes.clear()  # Reset file change tracking
        turn_result = TurnResult()
        step = 0
        _empty_retries = 0  # Track consecutive empty responses for retry
        _generation_retries = 0
        _max_generation_retries = 2

        while self._running and step < self.agent_config.max_turns:
            step += 1

            try:
                # Wrap _step in a Task so stop() can cancel it
                self._current_task = asyncio.current_task()
                step_result = await self._step()
            except asyncio.CancelledError:
                turn_result.finish_reason = "cancelled"
                break
            finally:
                self._current_task = None

            if self._cancelled:
                turn_result.finish_reason = "cancelled"
                break

            # Detect empty response (no text AND no tool calls) and retry
            if (
                not step_result.get("text")
                and not step_result.get("tool_calls")
                and _empty_retries < 2
            ):
                _empty_retries += 1
                import logging
                logging.getLogger("ic.engine").warning(
                    "empty_response_retry attempt=%d", _empty_retries,
                )
                await asyncio.sleep(1)
                continue  # Retry the step without incrementing turn count

            # Empty retries exhausted — the model is stuck
            if (
                not step_result.get("text")
                and not step_result.get("tool_calls")
                and _empty_retries >= 2
            ):
                import logging
                logging.getLogger("ic.engine").error(
                    "empty_response_exhausted after %d retries — ending turn", _empty_retries,
                )
                # Emit a visible message so the user knows what happened
                stuck_msg = (
                    "\n\n*(The model returned empty responses — "
                    "it may have hit a context limit or encountered an issue. "
                    "Try sending a follow-up message to continue.)*"
                )
                if self.on_text_delta:
                    await self._call(self.on_text_delta, stuck_msg)
                turn_result.text += stuck_msg
                turn_result.finish_reason = "empty_exhausted"
                break

            _empty_retries = 0  # Reset on successful response

            turn_result.text += step_result.get("text", "")
            turn_result.tool_calls.extend(step_result.get("tool_calls", []))
            turn_result.tool_results.extend(step_result.get("tool_results", []))

            # Accumulate usage and cost
            usage = step_result.get("usage", {})
            for k in self._total_usage:
                self._total_usage[k] += usage.get(k, 0)
            turn_result.usage = dict(self._total_usage)

            # Track cost
            if usage.get("prompt_tokens") or usage.get("completion_tokens"):
                self._cost_tracker.add(usage, self.agent_config.model)
            elif step_result.get("text"):
                # Fallback: estimate from text when provider returns no usage
                self._cost_tracker.estimate_from_text(
                    step_result["text"], "output", self.agent_config.model
                )
            turn_result.cost = self._cost_tracker.to_dict()

            if self.on_cost_update:
                await self._call(self.on_cost_update, turn_result.cost)

            # Log turn step
            log_turn(step, len(step_result.get("text", "")),
                     len(step_result.get("tool_calls", [])), turn_result.cost)

            # If no tool calls, the turn is complete
            if not step_result.get("tool_calls"):
                finish_reason = step_result.get("finish_reason", "stop")
                if self._should_attempt_generation_recovery(
                    user_input=user_input,
                    turn_result=turn_result,
                    step_result=step_result,
                ):
                    if _generation_retries < _max_generation_retries:
                        _generation_retries += 1
                        import logging
                        logging.getLogger("ic.engine").warning(
                            "generation_recovery_retry attempt=%d finish_reason=%s",
                            _generation_retries,
                            finish_reason,
                        )
                        recovery_prompt = (
                            "Generation recovery: the previous response ended before "
                            "creating index.html. Continue now and call write_file to "
                            "create index.html in the workspace root based on PRODUCT.md. "
                            "Do not ask more questions."
                        )
                        self.context.add_user(recovery_prompt)
                        if self.on_text_delta:
                            retry_msg = (
                                "\n\n*(Generation stalled before `index.html` was created. "
                                "Retrying automatically.)*"
                            )
                            await self._call(self.on_text_delta, retry_msg)
                        continue

                    import logging
                    logging.getLogger("ic.engine").error(
                        "generation_recovery_exhausted retries=%d",
                        _generation_retries,
                    )
                    fail_msg = (
                        "\n\n*(Generation ended before creating `index.html` after "
                        "automatic retries. Try rerunning with a faster model or a higher "
                        "model timeout.)*"
                    )
                    if self.on_text_delta:
                        await self._call(self.on_text_delta, fail_msg)
                    turn_result.text += fail_msg
                    turn_result.finish_reason = "missing_artifact"
                    break

                turn_result.finish_reason = finish_reason
                break

            # Context compaction if needed
            if self.context.token_estimate > 80_000 or self.context.turn_count > 25:
                compact_result = await self.context.compact_web(self._compact_provider)
                if compact_result:
                    # Re-inject critical context with project state
                    if self.workspace:
                        from pathlib import Path
                        project_state = None
                        if self._project_state_provider:
                            try:
                                project_state = self._project_state_provider()
                            except Exception:
                                pass
                        reinjected = await self._context_injector.reinject_after_compaction(
                            Path(self.workspace),
                            project_state=project_state,
                        )
                        for msg in reinjected:
                            self.context.add_user(msg.content if isinstance(msg.content, str) else str(msg.content))

                    if self.on_context_compacted:
                        await self._call(self.on_context_compacted, compact_result)

        self._running = False
        return turn_result

    async def _step(self) -> dict[str, Any]:
        """Execute a single LLM call + tool execution step."""
        assert self._provider is not None

        messages = self.context.get_messages()
        tools_schema = self.toolset.to_openai_schemas() or None

        max_retries = 3
        # Preserve partial text across retries so we don't lose streamed content
        best_text_parts: list[str] = []
        llm_logger = LLMCallLogger(model=self.agent_config.model)

        for attempt in range(max_retries):
            # Collect streaming response (reset on each attempt)
            text_parts: list[str] = []
            reasoning_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            usage = {}
            finish_reason = ""
            done_reasoning_content: str | None = None
            llm_logger.attempt = attempt
            llm_logger.start_time = __import__("time").monotonic()

            try:
                async for chunk in self._provider.chat(messages, tools=tools_schema):
                    if self._cancelled:
                        break

                    ctype = chunk["type"]

                    if ctype == "text_delta":
                        delta = chunk["data"]
                        text_parts.append(delta)
                        if self.on_text_delta:
                            await self._call(self.on_text_delta, delta)

                    elif ctype == "reasoning_delta":
                        reasoning_parts.append(chunk["data"])

                    elif ctype == "text":
                        pass  # Already accumulated via deltas

                    elif ctype == "tool_call":
                        tool_calls.append(chunk["data"])

                    elif ctype == "done":
                        usage = chunk["data"].get("usage", {})
                        finish_reason = chunk["data"].get("finish_reason", "")
                        done_reasoning_content = chunk["data"].get("reasoning_content")

                if self._cancelled:
                    finish_reason = "cancelled"
                    llm_logger.success(usage, "cancelled", len(tool_calls))
                    break
                llm_logger.success(usage, finish_reason, len(tool_calls))
                break  # Stream completed successfully
            except (ConnectionError, OSError, httpx.TimeoutException, APITimeoutError) as exc:
                # Keep the longest partial text we've received
                if len("".join(text_parts)) > len("".join(best_text_parts)):
                    best_text_parts = text_parts
                err_text = self._format_exception(exc)
                if attempt < max_retries - 1:
                    llm_logger.error(err_text, len("".join(text_parts)))
                    if self.on_llm_retry:
                        await self._call(
                            self.on_llm_retry,
                            attempt + 2,
                            max_retries,
                            err_text,
                        )
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)
                    continue
                # Final attempt failed — return partial result instead of raising
                llm_logger.error(f"final: {err_text}", len("".join(best_text_parts)))
                text_parts = best_text_parts
                finish_reason = "partial"
                break
            except BadRequestError as exc:
                # API proxy rejected the response (e.g. malformed tool call JSON).
                # Retry — the model may produce valid JSON on the next attempt.
                err_msg = str(exc).lower()
                is_bad_tool_args = (
                    "invalid function arguments" in err_msg
                    or "invalid json" in err_msg
                    or "tool_call" in err_msg
                )
                if is_bad_tool_args and attempt < max_retries - 1:
                    err_text = self._format_exception(exc)
                    import logging
                    logging.getLogger("ic.engine").warning(
                        "bad_tool_args_retry attempt=%d err=%s", attempt, err_text,
                    )
                    if self.on_llm_retry:
                        await self._call(
                            self.on_llm_retry,
                            attempt + 2,
                            max_retries,
                            err_text,
                        )
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)
                    continue
                # Not a tool-args issue or retries exhausted — return partial or raise
                if best_text_parts:
                    text_parts = best_text_parts
                    finish_reason = "partial"
                    break
                raise
            except Exception as exc:
                # Retry on httpx/httpcore transient errors
                if len("".join(text_parts)) > len("".join(best_text_parts)):
                    best_text_parts = text_parts
                exc_name = type(exc).__name__
                if attempt < max_retries - 1 and (
                    "RemoteProtocolError" in exc_name
                    or "ReadError" in exc_name
                    or "ConnectError" in exc_name
                ):
                    err_text = self._format_exception(exc)
                    if self.on_llm_retry:
                        await self._call(
                            self.on_llm_retry,
                            attempt + 2,
                            max_retries,
                            err_text,
                        )
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)
                    continue
                # Non-retryable error — return partial if we have any
                if best_text_parts:
                    text_parts = best_text_parts
                    finish_reason = "partial"
                    break
                raise

        full_text = "".join(text_parts)
        reasoning_content = done_reasoning_content or "".join(reasoning_parts) or None

        # Build assistant message for context
        assistant_tool_calls = None
        if tool_calls:
            # Truncate large arguments (e.g. write_file content) to save context tokens
            _tc_for_truncation = [
                {"name": tc["name"], "id": tc["id"], "arguments": tc["arguments"]}
                for tc in tool_calls
            ]
            _truncated = _truncate_tool_call_args(_tc_for_truncation)
            assistant_tool_calls = [
                {
                    "id": t["id"],
                    "type": "function",
                    "function": {"name": t["name"], "arguments": t["arguments"]},
                }
                for t in _truncated
            ]

        # Skip empty assistant messages — they pollute context and confuse
        # subsequent LLM calls.  Only add when there's actual content.
        if full_text or assistant_tool_calls or reasoning_content:
            self.context.add_assistant(
                content=full_text or None,
                tool_calls=assistant_tool_calls,
                reasoning_content=reasoning_content,
            )
        else:
            import logging
            logging.getLogger("ic.engine").warning(
                "LLM returned empty response (no text, no tool calls) — "
                "skipping assistant message to keep context clean"
            )

        # Execute tools (concurrent-safe tools run in parallel)
        tool_results = []
        if tool_calls:
            tool_results = await self._execute_tools(tool_calls)

        return {
            "text": full_text,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "usage": usage,
            "finish_reason": finish_reason,
        }

    async def _execute_tools(self, tool_calls: list[dict[str, Any]]) -> list[dict]:
        """Execute tool calls, running concurrent-safe tools in parallel.

        Groups consecutive concurrent-safe tools and runs them with asyncio.gather.
        Unsafe tools are executed sequentially between parallel batches.
        Results are added to context in the original order.
        """
        results: list[dict] = [None] * len(tool_calls)  # type: ignore[list-item]

        # Classify each tool call
        safe_indices: list[int] = []
        for i, tc in enumerate(tool_calls):
            tool = self.toolset.get(tc["name"])
            if tool and tool.is_concurrent_safe:
                safe_indices.append(i)

        # Fire on_tool_call callbacks for all tools
        for tc in tool_calls:
            if self.on_tool_call:
                await self._call(self.on_tool_call, tc["name"], tc)

        # Execute concurrent-safe tools in parallel
        if safe_indices:
            async def _run_safe(idx: int) -> tuple[int, str]:
                tc = tool_calls[idx]
                t0 = __import__("time").monotonic()
                output = await self._execute_tool(tc["name"], tc["arguments"])
                log_tool_execution(tc["name"], __import__("time").monotonic() - t0,
                                   len(output), output.startswith("Error"))
                return idx, output

            safe_results = await asyncio.gather(
                *[_run_safe(i) for i in safe_indices],
                return_exceptions=True,
            )
            for item in safe_results:
                if isinstance(item, Exception):
                    continue
                idx, output = item
                tc = tool_calls[idx]
                results[idx] = {"tool_call_id": tc["id"], "output": output}

        # Execute unsafe tools sequentially
        for i, tc in enumerate(tool_calls):
            if i in safe_indices:
                continue
            t0 = __import__("time").monotonic()
            output = await self._execute_tool(tc["name"], tc["arguments"])
            log_tool_execution(tc["name"], __import__("time").monotonic() - t0,
                               len(output), output.startswith("Error"))
            results[i] = {"tool_call_id": tc["id"], "output": output}

        # Add all results to context in order and fire callbacks
        for i, tc in enumerate(tool_calls):
            r = results[i]
            if r is None:
                r = {"tool_call_id": tc["id"], "output": "Error: tool execution failed"}
                results[i] = r
            # Truncate before adding to context to save tokens
            r["output"] = truncate_tool_result(tc["name"], r["output"])
            self.context.add_tool_result(r["tool_call_id"], r["output"])
            if self.on_tool_result:
                await self._call(self.on_tool_result, tc["name"], r["output"])

        return results

    async def _execute_tool(self, name: str, arguments: str) -> str:
        """Execute a tool by name with JSON arguments.

        Supports streaming progress if the tool implements execute_stream().
        Enforces per-tool timeout via asyncio.wait_for.
        Caches results for read-only (concurrent-safe) tools.
        """
        import time as _time
        _t0 = _time.monotonic()
        tool = self.toolset.get(name)
        if not tool:
            return f"Error: Unknown tool '{name}'"

        # Cache check for read-only tools
        cache_key = ""
        if tool.is_concurrent_safe:
            cache_key = f"{name}|{arguments}"
            if cache_key in self._tool_cache:
                return self._tool_cache[cache_key]
        else:
            # Write tool: invalidate cache (file state may have changed)
            self._tool_cache.clear()

        # Set up progress callback for this tool
        if self.on_tool_progress:
            tool.set_progress_callback(
                lambda event, tool_name=name: self._call(
                    self.on_tool_progress, tool_name, event.message, event.percent
                )
            )

        # Check for cancellation
        if self._cancelled:
            return f"Error: Tool '{name}' was cancelled"

        timeout = getattr(tool, "timeout_seconds", 60.0)

        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments

            # Validate arguments against tool parameter definitions
            from ic.tools.base import validate_tool_args
            validation_error = validate_tool_args(tool.parameters, args)
            if validation_error:
                return validation_error

            # Execute — skip timeout wrapper for tools that block indefinitely
            if timeout is None:
                result = await self._run_tool_inner(tool, name, args)
            else:
                result = await asyncio.wait_for(
                    self._run_tool_inner(tool, name, args),
                    timeout=timeout,
                )

            # Cache result for read-only tools
            if cache_key and not result.startswith("Error"):
                self._tool_cache[cache_key] = result

            return result

        except asyncio.TimeoutError:
            return f"Error: Tool '{name}' timed out after {timeout}s"
        except json.JSONDecodeError as e:
            # Attempt JSON repair before giving up
            repaired = self._repair_json(arguments, name)
            if repaired is not None:
                try:
                    result = await tool.execute(**repaired)
                    return result.to_content()
                except Exception as retry_err:
                    return f"Error executing {name} (after JSON repair): {retry_err}"
            return f"Error: Invalid JSON arguments: {e}"
        except Exception as e:
            return f"Error executing {name}: {e}"

    async def _run_tool_inner(self, tool: Any, name: str, args: dict) -> str:
        """Inner tool execution logic, separated for timeout wrapping.

        Supports automatic retries for tools with max_retries > 0.
        Only retries on transient errors (network, timeout, OSError).
        """
        max_retries = getattr(tool, "max_retries", 0)
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # Try streaming execution first
                if hasattr(tool, 'execute_stream'):
                    async for event in tool.execute_stream(**args):
                        if self._cancelled:
                            return f"Error: Tool '{name}' was cancelled"

                        from ic.tools.base import ToolCompleteEvent, ToolErrorEvent
                        if isinstance(event, ToolCompleteEvent):
                            return event.output
                        elif isinstance(event, ToolErrorEvent):
                            return f"Error: {event.error}"

                    return ""

                # Fall back to simple execute()
                result = await tool.execute(**args)
                return result.to_content()

            except (ConnectionError, OSError, TimeoutError) as exc:
                last_error = exc
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except Exception as exc:
                exc_name = type(exc).__name__
                if attempt < max_retries and any(
                    s in exc_name for s in ("Timeout", "Connect", "Protocol", "ReadError")
                ):
                    last_error = exc
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        return f"Error: Tool '{name}' failed after {max_retries + 1} attempts: {last_error}"

    @staticmethod
    def _repair_json(raw: str, tool_name: str) -> dict[str, Any] | None:
        """Try to fix common LLM JSON serialisation failures.

        Returns a parsed dict on success, or ``None`` if repair is not possible.
        """
        if not isinstance(raw, str):
            return None

        text = raw.strip()

        # --- Strategy 1: generic structural fixes ---
        # Remove trailing commas before } or ]
        fixed = re.sub(r",\s*([}\]])", r"\1", text)
        # Close unterminated strings: odd number of unescaped quotes
        unescaped_quotes = re.findall(r'(?<!\\)"', fixed)
        if len(unescaped_quotes) % 2 != 0:
            fixed += '"'
        # Balance braces / brackets
        open_b = fixed.count("{") - fixed.count("}")
        open_s = fixed.count("[") - fixed.count("]")
        if open_b > 0:
            fixed += "}" * open_b
        if open_s > 0:
            fixed += "]" * open_s

        try:
            parsed = json.loads(fixed)
            # Validate that write_file results actually have file_path
            if tool_name == "write_file" and isinstance(parsed, dict):
                if "file_path" not in parsed:
                    # Strategy 1 produced a dict without file_path; fall through
                    raise json.JSONDecodeError("missing file_path", fixed, 0)
            return parsed
        except json.JSONDecodeError:
            pass

        # --- Strategy 2: regex extraction for write_file / edit_file ---
        if tool_name in ("write_file", "edit_file"):
            fp_match = re.search(
                r'"file_path"\s*:\s*"([^"]+)"', text
            )
            # Content is often the last (and largest) value; grab everything
            # between the first occurrence of "content": " and the final "
            ct_match = re.search(
                r'"content"\s*:\s*"(.*)',
                text,
                re.DOTALL,
            )
            if fp_match and ct_match:
                content_raw = ct_match.group(1)
                # Strip a trailing ", } etc. that the LLM may have managed
                content_raw = re.sub(r'"\s*\}?\s*$', "", content_raw)
                return {
                    "file_path": fp_match.group(1),
                    "content": content_raw,
                }
            # file_path found but content completely missing or truncated
            if fp_match:
                return {
                    "file_path": fp_match.group(1),
                    "content": "",
                }

        return None

    async def run_sub_agent(
        self,
        task: str,
        model_name: str | None = None,
        max_turns: int = 30,
    ) -> str:
        """Run a sub-agent for a specific task. Returns the final text output."""
        sub_model = model_name or self.config.model_pointers.resolve("sub", self.agent_config.model)
        sub_config = AgentConfig(
            name=f"sub-{uuid.uuid4().hex[:8]}",
            system_prompt=(
                "You are a focused sub-agent. Complete the assigned task efficiently.\n"
                "You have access to file, shell, and think tools.\n"
                "When done, provide a clear summary of what you accomplished."
            ),
            model=sub_model,
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
            on_llm_retry=self.on_llm_retry,
            on_tool_call=self.on_tool_call,
            on_tool_result=self.on_tool_result,
        )
        sub_engine.setup()

        # Inject custom tools (e.g. DB-backed file tools) via factory
        if self.sub_agent_tool_factory:
            try:
                extra_tools = self.sub_agent_tool_factory(sub_engine)
                for tool in extra_tools:
                    sub_engine.toolset.add(tool)
            except Exception:
                import logging
                logging.getLogger("ic.engine").warning(
                    "sub_agent_tool_factory failed", exc_info=True,
                )

        result = await sub_engine.run_turn(task)

        # Merge sub-agent cost and file changes into parent
        self._cost_tracker.prompt_tokens += sub_engine._cost_tracker.prompt_tokens
        self._cost_tracker.completion_tokens += sub_engine._cost_tracker.completion_tokens
        self._cost_tracker.total_cost_usd += sub_engine._cost_tracker.total_cost_usd
        self._file_changes.extend(sub_engine._file_changes)

        if self.on_sub_agent_end:
            await self._call(self.on_sub_agent_end, result.text)

        return result.text or "(Sub-agent completed with no text output)"

    async def run_sub_agents_parallel(
        self,
        tasks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Run multiple sub-agents concurrently via asyncio.gather.

        Each task dict has: {task: str, model?: str, max_turns?: int}
        Returns a list of {task, result, error} dicts in the same order.
        """
        async def _run_one(t: dict) -> dict[str, Any]:
            try:
                text = await self.run_sub_agent(
                    task=t["task"],
                    model_name=t.get("model"),
                    max_turns=int(t.get("max_turns", 30)),
                )
                return {"task": t["task"], "result": text, "error": None}
            except Exception as exc:
                return {"task": t["task"], "result": None, "error": str(exc)}

        results = await asyncio.gather(
            *[_run_one(t) for t in tasks],
            return_exceptions=False,  # errors handled inside _run_one
        )
        return list(results)

    async def _call(self, fn: Callable, *args: Any):
        """Call a callback, handling both sync and async.

        Isolates callback failures so a broken callback never crashes the engine.
        """
        try:
            result = fn(*args)
            if hasattr(result, "__await__"):
                await result
        except Exception:
            import logging
            logging.getLogger("ic.engine").warning(
                "callback_error",
                extra={"data": {"callback": getattr(fn, "__name__", str(fn))}},
                exc_info=True,
            )

    def stop(self):
        """Stop the engine. Cancels any in-flight LLM call or tool execution."""
        self._running = False
        self._cancelled = True
        # Close the active LLM stream to unblock network I/O immediately
        if self._provider:
            asyncio.ensure_future(self._provider.cancel_stream())

    # ── State Persistence ─────────────────────────────────────

    def save_state(self, path: "Path"):
        """Save engine state (cost, usage, snapshots, branches) to JSON."""
        from pathlib import Path as _P
        from ic.soul.context import _Snapshot

        def _serialize_snapshot(snap: _Snapshot) -> dict:
            return {
                "messages": [m.to_dict() for m in snap.messages],
                "token_estimate": snap.token_estimate,
                "cacheable_count": snap.cacheable_count,
                "label": snap.label,
            }

        state = {
            "version": 1,
            "cost_tracker": {
                "prompt_tokens": self._cost_tracker.prompt_tokens,
                "completion_tokens": self._cost_tracker.completion_tokens,
                "total_cost_usd": self._cost_tracker.total_cost_usd,
                "model": self._cost_tracker.model,
            },
            "total_usage": dict(self._total_usage),
            "snapshots": [_serialize_snapshot(s) for s in self.context._snapshots],
            "branches": {
                name: _serialize_snapshot(s)
                for name, s in self.context._branches.items()
            },
        }
        _P(path).parent.mkdir(parents=True, exist_ok=True)
        _P(path).write_text(json.dumps(state, ensure_ascii=False, default=str))

    def load_state(self, path: "Path"):
        """Restore engine state from JSON. Call after context is loaded."""
        from pathlib import Path as _P
        from ic.llm.provider import Message
        from ic.soul.context import _Snapshot

        p = _P(path)
        if not p.exists():
            return

        state = json.loads(p.read_text())
        if state.get("version") != 1:
            return

        # Restore cost tracker
        ct = state.get("cost_tracker", {})
        self._cost_tracker.prompt_tokens = ct.get("prompt_tokens", 0)
        self._cost_tracker.completion_tokens = ct.get("completion_tokens", 0)
        self._cost_tracker.total_cost_usd = ct.get("total_cost_usd", 0.0)
        if ct.get("model"):
            self._cost_tracker.model = ct["model"]

        # Restore total usage
        tu = state.get("total_usage", {})
        self._total_usage["prompt_tokens"] = tu.get("prompt_tokens", 0)
        self._total_usage["completion_tokens"] = tu.get("completion_tokens", 0)

        def _deserialize_snapshot(data: dict) -> _Snapshot:
            msgs = [Message(**m) for m in data.get("messages", [])]
            return _Snapshot(
                messages=msgs,
                token_estimate=data.get("token_estimate", 0),
                cacheable_count=data.get("cacheable_count", 0),
                label=data.get("label", ""),
            )

        # Restore snapshots and branches
        self.context._snapshots = [
            _deserialize_snapshot(s) for s in state.get("snapshots", [])
        ]
        self.context._branches = {
            name: _deserialize_snapshot(s)
            for name, s in state.get("branches", {}).items()
        }
