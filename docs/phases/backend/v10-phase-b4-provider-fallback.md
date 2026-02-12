# Phase v10-B4: Provider Fallback Chain

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: None (independent feature)

## Goal

Implement automatic model fallback when primary provider fails (timeout, rate limit).

## Detailed Tasks

### Task 1: Extend AgentConfig

**Description**: Add model_fallback field to configuration.

**Implementation Details**:
- [ ] Add `model_fallback: list[str]` to AgentConfig
- [ ] Add documentation

**Files to modify**:
- `packages/agent/src/ic/config.py`

**Acceptance Criteria**:
- [ ] Config accepts fallback models

---

### Task 2: Implement fallback in engine

**Description**: Modify _step() to try fallback models on failure.

**Implementation Details**:
- [ ] Modify packages/agent/src/ic/soul/engine.py
- [ ] Try primary model first
- [ ] On TimeoutError or RateLimitError, try fallback models
- [ ] Return error only if all models fail

**Implementation**:
```python
async def _step(self, messages: list[dict]) -> StepResult:
    models = [self.config.model] + self.config.model_fallback

    for model in models:
        try:
            response = await self._call_llm(messages, model)
            return StepResult(success=True, response=response)
        except (TimeoutError, RateLimitError) as e:
            self.logger.warning(f"Model {model} failed: {e}")
            continue

    return StepResult(success=False, error="All models failed")
```

**Files to modify**:
- `packages/agent/src/ic/soul/engine.py`

**Acceptance Criteria**:
- [ ] Primary timeout triggers fallback
- [ ] Rate limit triggers fallback
- [ ] All failures return clear error

## Technical Specifications

### Config Schema

```python
class AgentConfig(BaseModel):
    # ... existing fields
    model_fallback: list[str] = []  # e.g., ["gpt-4o-mini", "claude-3-haiku"]
```

### Error Handling

| Error Type | Action |
|------------|--------|
| TimeoutError | Try next model |
| RateLimitError | Try next model |
| AuthenticationError | Stop (don't try fallback) |
| Other Error | Stop (don't try fallback) |

## Testing Requirements

- [ ] Test fallback on timeout
- [ ] Test fallback on rate limit
- [ ] Test no fallback on auth error

## Notes & Warnings

- Only transient errors should trigger fallback
- Track which model was used for token counting
