"""Context management - conversation history and token tracking."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ic.llm.provider import Message


@dataclass
class Context:
    """Manages conversation context with persistence."""

    messages: list[Message] = field(default_factory=list)
    system_prompt: str = ""
    _token_estimate: int = 0

    def add_system(self, content: str):
        self.system_prompt = content

    def add_user(self, content: str):
        self.messages.append(Message(role="user", content=content))
        self._estimate_tokens(content)

    def add_assistant(self, content: str | None = None, tool_calls: list[dict] | None = None):
        self.messages.append(Message(role="assistant", content=content, tool_calls=tool_calls))
        if content:
            self._estimate_tokens(content)

    def add_tool_result(self, tool_call_id: str, content: str):
        self.messages.append(Message(role="tool", content=content, tool_call_id=tool_call_id))
        self._estimate_tokens(content)

    def get_messages(self) -> list[Message]:
        msgs = []
        if self.system_prompt:
            msgs.append(Message(role="system", content=self.system_prompt))
        msgs.extend(self.messages)
        return msgs

    @property
    def token_estimate(self) -> int:
        return self._token_estimate

    def _estimate_tokens(self, text: str):
        self._token_estimate += len(text) // 3

    def compact(self, keep_recent: int = 10):
        """Simple compaction: keep system + first 2 + last N messages."""
        if len(self.messages) <= keep_recent + 2:
            return
        first = self.messages[:2]
        recent = self.messages[-keep_recent:]
        summary_text = f"[Context compacted: {len(self.messages) - len(first) - len(recent)} messages summarized]"
        self.messages = first + [Message(role="system", content=summary_text)] + recent
        self._recalc_tokens()

    def _recalc_tokens(self):
        self._token_estimate = 0
        for m in self.messages:
            if isinstance(m.content, str):
                self._estimate_tokens(m.content)

    def save(self, path: Path):
        data = []
        for m in self.messages:
            data.append(m.to_dict())
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path: Path, system_prompt: str = "") -> Context:
        ctx = cls(system_prompt=system_prompt)
        if not path.exists():
            return ctx
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                ctx.messages.append(Message(**d))
        ctx._recalc_tokens()
        return ctx
