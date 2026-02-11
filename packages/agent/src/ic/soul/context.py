"""Context management - conversation history and token tracking."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ic.llm.provider import Message


@dataclass
class _Snapshot:
    """Immutable snapshot of context state for branching/undo."""

    messages: list[Message]
    token_estimate: int
    cacheable_count: int
    label: str = ""


@dataclass
class Context:
    """Manages conversation context with persistence."""

    messages: list[Message] = field(default_factory=list)
    system_prompt: str = ""
    _token_estimate: int = 0
    _cacheable_count: int = 0  # Number of initial messages to mark as cacheable
    _snapshots: list[_Snapshot] = field(default_factory=list)  # Undo stack
    _branches: dict[str, _Snapshot] = field(default_factory=dict)  # Named branches

    def add_system(self, content: str):
        self.system_prompt = content

    def add_user(self, content: str):
        self.messages.append(Message(role="user", content=content))
        self._estimate_tokens(content)

    def add_assistant(
        self,
        content: str | None = None,
        tool_calls: list[dict] | None = None,
        reasoning_content: str | None = None,
    ):
        self.messages.append(
            Message(
                role="assistant",
                content=content,
                tool_calls=tool_calls,
                reasoning_content=reasoning_content,
            )
        )
        if content:
            self._estimate_tokens(content)
        if reasoning_content:
            self._estimate_tokens(reasoning_content)

    def add_tool_result(self, tool_call_id: str, content: str):
        self.messages.append(Message(role="tool", content=content, tool_call_id=tool_call_id))
        self._estimate_tokens(content)

    def get_messages(self) -> list[Message]:
        msgs = []
        if self.system_prompt:
            msgs.append(Message(
                role="system",
                content=self.system_prompt,
                cache_control={"type": "ephemeral"},  # Cache system prompt
            ))
        # Mark the first few injected context messages as cacheable
        # (they don't change between turns)
        for i, m in enumerate(self.messages):
            if i < self._cacheable_count:
                msgs.append(Message(
                    role=m.role,
                    content=m.content,
                    tool_calls=m.tool_calls,
                    tool_call_id=m.tool_call_id,
                    name=m.name,
                    reasoning_content=m.reasoning_content,
                    cache_control={"type": "ephemeral"},
                ))
            else:
                msgs.append(m)

        # Some thinking-enabled providers require assistant tool-call messages to
        # carry reasoning_content on follow-up turns. Old sessions may miss it.
        normalized_msgs: list[Message] = []
        for m in msgs:
            if m.role == "assistant" and m.tool_calls and m.reasoning_content is None:
                normalized_msgs.append(
                    Message(
                        role=m.role,
                        content=m.content,
                        tool_calls=m.tool_calls,
                        tool_call_id=m.tool_call_id,
                        name=m.name,
                        reasoning_content="",
                        cache_control=m.cache_control,
                    )
                )
            else:
                normalized_msgs.append(m)
        msgs = normalized_msgs

        # Merge consecutive user messages — many LLM APIs don't support
        # multiple user messages in a row and may return empty responses.
        msgs = _merge_consecutive_user_messages(msgs)

        # Drop empty assistant messages (no content, no tool_calls) that
        # may have been persisted from earlier sessions.
        msgs = [
            m for m in msgs
            if not (
                m.role == "assistant"
                and not m.content
                and not m.tool_calls
                and not m.reasoning_content
            )
        ]

        return msgs

    @property
    def token_estimate(self) -> int:
        return self._token_estimate

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self.messages if m.role == "user")

    def add_user_with_images(self, text: str, images: list[dict]):
        """Add a user message with image content blocks."""
        content_blocks: list[dict] = [{"type": "text", "text": text}]
        for img in images:
            content_blocks.append({
                "type": "image_url",
                "image_url": {"url": img["url"]},
            })
        self.messages.append(Message(role="user", content=content_blocks))
        self._estimate_tokens(text)
        # ~85 tokens per image
        self._token_estimate += len(images) * 85

    def _estimate_tokens(self, text: str):
        self._token_estimate += len(text) // 3

    # ── Branching / Undo ──────────────────────────────────────

    def _take_snapshot(self, label: str = "") -> _Snapshot:
        return _Snapshot(
            messages=copy.deepcopy(self.messages),
            token_estimate=self._token_estimate,
            cacheable_count=self._cacheable_count,
            label=label,
        )

    def _restore_snapshot(self, snap: _Snapshot):
        self.messages = copy.deepcopy(snap.messages)
        self._token_estimate = snap.token_estimate
        self._cacheable_count = snap.cacheable_count

    def checkpoint(self, label: str = ""):
        """Save a snapshot to the undo stack. Called automatically before each turn."""
        self._snapshots.append(self._take_snapshot(label))

    def undo(self) -> bool:
        """Revert to the most recent checkpoint. Returns False if nothing to undo."""
        if not self._snapshots:
            return False
        self._restore_snapshot(self._snapshots.pop())
        return True

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """Return metadata for all checkpoints in the undo stack."""
        result = []
        for i, snap in enumerate(self._snapshots):
            result.append({
                "index": i,
                "label": snap.label,
                "messages": len(snap.messages),
                "tokens": snap.token_estimate,
            })
        return result

    def revert_to(self, index: int) -> bool:
        """Revert to a specific checkpoint by index.

        Saves current state as a 'pre-revert' branch for safety.
        Returns False if index is out of range.
        """
        if index < 0 or index >= len(self._snapshots):
            return False
        self._branches["pre-revert"] = self._take_snapshot("pre-revert")
        snap = self._snapshots[index]
        self._restore_snapshot(snap)
        self._snapshots = self._snapshots[:index]
        return True

    def fork(self, branch_name: str):
        """Save the current state as a named branch."""
        self._branches[branch_name] = self._take_snapshot(branch_name)

    def switch_branch(self, branch_name: str) -> bool:
        """Restore a named branch. Returns False if branch doesn't exist."""
        snap = self._branches.get(branch_name)
        if snap is None:
            return False
        # Save current state as a snapshot before switching
        self._snapshots.append(self._take_snapshot(f"pre-switch-{branch_name}"))
        self._restore_snapshot(snap)
        return True

    def list_branches(self) -> list[str]:
        """Return names of all saved branches."""
        return list(self._branches.keys())

    def rollback(self, n: int = 1) -> int:
        """Remove the last N user/assistant turn pairs. Returns number of turns removed."""
        removed = 0
        while removed < n and self.messages:
            # Remove messages backwards until we've removed a user message
            found_user = False
            while self.messages:
                msg = self.messages.pop()
                if msg.role == "user":
                    found_user = True
                    break
            if found_user:
                removed += 1
        self._recalc_tokens()
        return removed

    def compact(self, keep_recent: int = 10):
        """Simple compaction fallback: keep system + first 2 + last N messages."""
        if len(self.messages) <= keep_recent + 2:
            return
        first = self.messages[:2]
        recent = self.messages[-keep_recent:]
        dropped = len(self.messages) - len(first) - len(recent)
        summary_text = f"[Context compacted: {dropped} messages summarized]"
        self.messages = first + [Message(role="system", content=summary_text)] + recent
        self._recalc_tokens()

    async def compact_with_llm(
        self,
        provider: Any,
        keep_first: int = 2,
        keep_recent: int = 10,
    ) -> bool:
        """Compact context using LLM summarization.

        Summarizes middle messages into a concise summary, preserving
        the first few and most recent messages. Falls back to simple
        compaction if the LLM call fails.

        Returns True if compaction was performed.
        """
        if len(self.messages) <= keep_first + keep_recent:
            return False

        first = self.messages[:keep_first]
        middle = self.messages[keep_first:-keep_recent]
        recent = self.messages[-keep_recent:]

        # Build text representation of middle messages for summarization
        middle_text = _format_messages_for_summary(middle)
        if not middle_text.strip():
            return False

        summary_prompt = (
            "Summarize the following conversation segment concisely. "
            "Preserve: key decisions, file paths mentioned, code changes made, "
            "tool results, and any requirements discussed. "
            "Omit: verbose tool outputs, repeated content, pleasantries.\n\n"
            f"{middle_text}"
        )

        try:
            summary_parts: list[str] = []
            async for chunk in provider.chat(
                [Message(role="user", content=summary_prompt)],
                tools=None,
                stream=True,
                max_tokens=2048,
            ):
                if chunk["type"] == "text_delta":
                    summary_parts.append(chunk["data"])

            summary = "".join(summary_parts).strip()
            if not summary:
                self.compact(keep_recent)
                return True

            summary_msg = Message(
                role="system",
                content=f"[Conversation summary ({len(middle)} messages compressed)]\n{summary}",
            )
            self.messages = first + [summary_msg] + recent
            self._recalc_tokens()
            return True

        except Exception:
            # Fallback to simple compaction on any error
            self.compact(keep_recent)
            return True

    async def compact_web(
        self,
        provider: Any,
        keep_first: int = 2,
        keep_recent: int = 8,
    ) -> dict:
        """Web-optimized compaction with HTML de-duplication.

        Returns dict with {tokens_saved, turns_removed} or empty dict if no compaction needed.
        """
        if len(self.messages) <= keep_first + keep_recent:
            return {}

        old_estimate = self._token_estimate
        old_count = len(self.messages)

        # Step 1: De-duplicate HTML in tool results (replace >2K char HTML with placeholder)
        for m in self.messages:
            if m.role == "tool" and isinstance(m.content, str) and len(m.content) > 2000:
                # Check if it looks like HTML
                if "<html" in m.content.lower() or "<!doctype" in m.content.lower():
                    import re
                    title_match = re.search(r"<title>(.*?)</title>", m.content, re.IGNORECASE)
                    title = title_match.group(1) if title_match else "untitled"
                    m.content = f"[HTML: {title}, {len(m.content)} chars]"

        # Step 2: Split messages into first/middle/recent
        first = self.messages[:keep_first]
        middle = self.messages[keep_first:-keep_recent]
        recent = self.messages[-keep_recent:]

        if not middle:
            return {}

        # Step 3: Summarize middle messages
        middle_text = _format_messages_for_summary(middle)
        if not middle_text.strip():
            self._recalc_tokens()
            return {"tokens_saved": old_estimate - self._token_estimate, "turns_removed": 0}

        summary_prompt = (
            "Summarize this conversation segment concisely. "
            "Preserve: key decisions, file paths, code changes, design choices "
            "(colors, fonts, layout), requirements, and component inventory. "
            "Omit: verbose tool outputs, repeated content, pleasantries.\n\n"
            f"{middle_text}"
        )

        try:
            summary_parts = []
            async for chunk in provider.chat(
                [Message(role="user", content=summary_prompt)],
                tools=None,
                stream=True,
                max_tokens=2048,
            ):
                if chunk["type"] == "text_delta":
                    summary_parts.append(chunk["data"])

            summary = "".join(summary_parts).strip()
            if not summary:
                self.compact(keep_recent)
                self._recalc_tokens()
                return {
                    "tokens_saved": old_estimate - self._token_estimate,
                    "turns_removed": old_count - len(self.messages),
                }

            summary_msg = Message(
                role="system",
                content=f"[Conversation summary ({len(middle)} messages compressed)]\n{summary}",
            )
            self.messages = first + [summary_msg] + recent
            self._recalc_tokens()
            return {
                "tokens_saved": old_estimate - self._token_estimate,
                "turns_removed": old_count - len(self.messages),
            }
        except Exception:
            self.compact(keep_recent)
            self._recalc_tokens()
            return {
                "tokens_saved": old_estimate - self._token_estimate,
                "turns_removed": old_count - len(self.messages),
            }

    def _recalc_tokens(self):
        self._token_estimate = 0
        for m in self.messages:
            if isinstance(m.content, str):
                self._estimate_tokens(m.content)
            elif isinstance(m.content, list):
                for block in m.content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            self._estimate_tokens(block.get("text", ""))
                        elif block.get("type") == "image_url":
                            self._token_estimate += 85

    def save(self, path: Path):
        data = []
        for m in self.messages:
            data.append(m.to_dict())
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for item in data:
                serialized = json.dumps(item, ensure_ascii=False)
                serialized = serialized.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
                f.write(serialized + "\n")

    @classmethod
    def load(cls, path: Path, system_prompt: str = "") -> Context:
        ctx = cls(system_prompt=system_prompt)
        if not path.exists():
            return ctx
        with open(path) as f:
            pending = ""
            for line in f:
                line = line.rstrip("\r\n")
                if not line and not pending:
                    continue
                candidate = pending + line if pending else line
                try:
                    d = json.loads(candidate)
                except json.JSONDecodeError:
                    if pending:
                        try:
                            recovered = json.loads(line)
                        except json.JSONDecodeError:
                            pending = candidate
                        else:
                            ctx.messages.append(Message(**recovered))
                            pending = ""
                    else:
                        pending = line
                    continue
                ctx.messages.append(Message(**d))
                pending = ""
        if pending:
            try:
                d = json.loads(pending)
            except json.JSONDecodeError:
                pass
            else:
                ctx.messages.append(Message(**d))
        ctx._recalc_tokens()
        return ctx


def _format_messages_for_summary(messages: list[Message]) -> str:
    """Format messages into readable text for LLM summarization."""
    parts: list[str] = []
    for m in messages:
        role = m.role.upper()
        if m.role == "tool":
            content = m.content if isinstance(m.content, str) else str(m.content)
            # Truncate long tool outputs
            if len(content) > 500:
                content = content[:250] + "\n...[truncated]...\n" + content[-250:]
            parts.append(f"[TOOL RESULT]: {content}")
        elif m.role == "assistant" and m.tool_calls:
            names = [tc.get("function", {}).get("name", "?") for tc in (m.tool_calls or [])]
            text = m.content or ""
            parts.append(f"ASSISTANT: {text}\n  (called tools: {', '.join(names)})")
        else:
            if isinstance(m.content, list):
                text_parts = []
                for block in m.content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "image_url":
                            text_parts.append("[IMAGE]")
                content = " ".join(text_parts)
            else:
                content = m.content if isinstance(m.content, str) else str(m.content or "")
            parts.append(f"{role}: {content}")
    return "\n\n".join(parts)


def _merge_consecutive_user_messages(msgs: list[Message]) -> list[Message]:
    """Merge consecutive user messages into a single message.

    Many OpenAI-compatible APIs (especially non-OpenAI models) don't handle
    multiple consecutive user messages well and may return empty responses.
    This merges them with a double-newline separator.
    """
    if not msgs:
        return msgs

    result: list[Message] = []
    for m in msgs:
        if (
            m.role == "user"
            and result
            and result[-1].role == "user"
            and isinstance(m.content, str)
            and isinstance(result[-1].content, str)
        ):
            result[-1] = Message(
                role="user",
                content=result[-1].content + "\n\n" + m.content,
                cache_control=result[-1].cache_control,
            )
        else:
            result.append(m)
    return result
