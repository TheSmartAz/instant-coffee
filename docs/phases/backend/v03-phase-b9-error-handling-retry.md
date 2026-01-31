# Phase B9: Error Handling & Retry

## Metadata

- **Category**: Backend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: B1 (LLM Client)
  - **Blocks**: None

## Goal

Implement comprehensive error handling with retry logic, rate limit handling, and structured error responses for all LLM API calls.

## Detailed Tasks

### Task 1: Implement Retry Decorator

**Description**: Create a reusable retry mechanism with exponential backoff.

**Implementation Details**:
- [ ] Create `packages/backend/app/llm/retry.py` or add to utils
- [ ] Implement `with_retry()` async function
- [ ] Support configurable max_retries and base_delay
- [ ] Implement exponential backoff (1s, 2s, 4s, ...)
- [ ] Log retry attempts

**Files to create**:
- `packages/backend/app/llm/retry.py` (optional)

**Acceptance Criteria**:
- [ ] Retries up to max_retries times
- [ ] Delay doubles each attempt
- [ ] Final exception is raised if all retries fail

### Task 2: Enhance OpenAIClient Error Handling

**Description**: Improve error classification and handling in OpenAIClient.

**Implementation Details**:
- [ ] Update _handle_error() to use OpenAI exception types
- [ ] Catch rate limit errors (429) specifically
- [ ] Catch authentication errors (401)
- [ ] Catch timeout errors
- [ ] Catch context length exceeded errors
- [ ] Return specific exception types

**Files to modify**:
- `packages/backend/app/llm/openai_client.py`

**Acceptance Criteria**:
- [ ] OpenAI exceptions are properly classified
- [ ] Specific exception types are returned
- [ ] Error messages are clear and actionable

### Task 3: Apply Retry to LLM Calls

**Description**: Wrap LLM client methods with retry logic.

**Implementation Details**:
- [ ] Wrap chat_completion() with retry
- [ ] Wrap chat_completion_stream() with retry
- [ ] Wrap chat_with_tools() with retry
- [ ] Configure max_retries=3, base_delay=1.0

**Acceptance Criteria**:
- [ ] Transient errors trigger retry
- [ ] Non-retryable errors fail immediately
- [ ] Retry attempts are logged

### Task 4: Add Tool Error Handling

**Description**: Ensure tool errors are handled gracefully.

**Implementation Details**:
- [ ] Wrap tool handlers in try/catch
- [ ] Return structured error responses
- [ ] Always emit tool_result event (even on error)
- [ ] Allow LLM to decide on retry

**Acceptance Criteria**:
- [ ] Tool errors don't crash the agent
- [ ] Error responses are structured
- [ ] LLM receives error information

### Task 5: Add Timeout Handling

**Description**: Handle request timeouts gracefully.

**Implementation Details**:
- [ ] Set appropriate timeout on API calls
- [ ] Catch timeout exceptions
- [ ] Return clear timeout error message
- [ ] Log timeout occurrences

**Acceptance Criteria**:
- [ ] Timeouts are caught and handled
- [ ] Error message indicates timeout
- [ ] Retry may be attempted on timeout

## Technical Specifications

### Retry Function

```python
async def with_retry(
    func: callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    **kwargs,
) -> Any:
    """
    Execute function with exponential backoff retry.

    Args:
        func: Async function to execute
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)

    Returns:
        Function result

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries} attempts failed: {e}")

    raise last_exception
```

### Error Types

```python
class OpenAIClientError(Exception):
    """Base error for OpenAI client"""
    pass

class RateLimitError(OpenAIClientError):
    """Rate limit exceeded (429)"""
    pass

class AuthenticationError(OpenAIClientError):
    """Invalid API key (401)"""
    pass

class TimeoutError(OpenAIClientError):
    """Request timeout"""
    pass

class ContextLengthError(OpenAIClientError):
    """Context length exceeded"""
    pass
```

### Retry Configuration

```python
# Recommended settings
MAX_RETRIES = 3
BASE_DELAY = 1.0  # 1s, 2s, 4s
RETRYABLE_ERRORS = (
    RateLimitError,
    TimeoutError,
    APIError,  # Only for transient API errors
)
```

## Testing Requirements

- [ ] Unit test for retry with successful retry
- [ ] Unit test for retry with all attempts failed
- [ ] Unit test for exponential backoff timing
- [ ] Unit test for error classification
- [ ] Integration test for rate limit handling
- [ ] Integration test for timeout handling

## Notes & Warnings

1. **Rate Limits**: Respect API rate limits; don't retry immediately on 429
2. **Cost**: Retries consume API quota; log retry attempts
3. **Idempotency**: Ensure retried operations are idempotent where possible
4. **User Feedback**: Consider showing retry status to user for long operations
5. **Configuration**: Make retry settings configurable for different environments
