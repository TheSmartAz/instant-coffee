# Phase v10-B1: Exact Token Calculation with tiktoken

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: v10-B2 (Structured HTML Generation), v10-B5 (Structured Compaction)

## Goal

Replace approximate token calculation with precise tiktoken-based counting for accurate context management.

## Detailed Tasks

### Task 1: Install tiktoken dependency

**Description**: Add tiktoken to agent requirements.

**Implementation Details**:
- [ ] Add `tiktoken` to packages/agent/requirements.txt or pyproject.toml

**Files to modify/create**:
- `packages/agent/pyproject.toml` or `requirements.txt`

**Acceptance Criteria**:
- [ ] tiktoken is installable via pip

---

### Task 2: Create TokenCounter class

**Description**: Implement precise token counting with caching.

**Implementation Details**:
- [ ] Create TokenCounter class in packages/agent/src/ic/soul/context.py
- [ ] Support model-specific encodings (cl100k_base for GPT-4, o3, etc.)
- [ ] Cache encoding instance to avoid repeated initialization

**Implementation**:
```python
import tiktoken

class TokenCounter:
    _cache: dict[str, tiktoken.Encoding] = {}

    @classmethod
    def get_encoding(cls, model: str = "gpt-4") -> tiktoken.Encoding:
        if model not in cls._cache:
            cls._cache[model] = tiktoken.get_encoding("cl100k_base")
        return cls._cache[model]

    @classmethod
    def count(cls, text: str, model: str = "gpt-4") -> int:
        encoding = cls.get_encoding(model)
        return len(encoding.encode(text))
```

**Files to modify/create**:
- `packages/agent/src/ic/soul/context.py`

**Acceptance Criteria**:
- [ ] Token count accuracy < 5% error vs actual
- [ ] Performance acceptable with caching

---

### Task 3: Replace estimate_tokens calls

**Description**: Replace all `len(text) // 3` approximations with TokenCounter.

**Implementation Details**:
- [ ] Find all uses of estimate_tokens in the codebase
- [ ] Replace with TokenCounter.count()
- [ ] Ensure compatibility with existing compaction triggers

**Files to modify/create**:
- `packages/agent/src/ic/soul/context.py`
- `packages/agent/src/ic/soul/engine.py` (if applicable)

**Acceptance Criteria**:
- [ ] All token counts use tiktoken
- [ ] Compaction triggers at correct thresholds

## Technical Specifications

### API

```python
class TokenCounter:
    @staticmethod
    def count(text: str, model: str = "gpt-4") -> int:
        """Count tokens using tiktoken"""

    @staticmethod
    def estimate(text: str) -> int:
        """Alias for backward compatibility"""
```

## Testing Requirements

- [ ] Unit tests for token counting accuracy
- [ ] Compare against known token counts
- [ ] Performance benchmarks

## Notes & Warnings

- Cache encoding instances to prevent performance issues
- Different models may need different encodings in future
