# Phase B1: LLM Client Layer

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: B3 (BaseAgent Enhancement), B5-B7 (Agent Implementations)

## Goal

Create a unified LLM client wrapper around the OpenAI SDK that provides consistent methods for chat completion, streaming, and tool calling, with built-in token tracking and cost calculation.

## Detailed Tasks

### Task 1: Create OpenAIClient Class Structure

**Description**: Set up the base OpenAIClient class with initialization and configuration.

**Implementation Details**:
- [ ] Create `packages/backend/app/llm/__init__.py`
- [ ] Create `packages/backend/app/llm/openai_client.py`
- [ ] Initialize AsyncOpenAI client with configurable API key and base URL
- [ ] Define pricing dictionary for common models (gpt-4o, gpt-4o-mini, etc.)
- [ ] Implement `_get_pricing()` for model pricing lookup
- [ ] Implement `_calculate_cost()` for cost calculation

**Files to create**:
- `packages/backend/app/llm/__init__.py`
- `packages/backend/app/llm/openai_client.py`

**Acceptance Criteria**:
- [ ] Client initializes with Settings from config
- [ ] Pricing lookup works for exact and prefix matches
- [ ] Cost calculation returns accurate USD values

### Task 2: Implement chat_completion()

**Description**: Non-streaming chat completion with token usage tracking.

**Implementation Details**:
- [ ] Create `LLMResponse` and `TokenUsage` dataclasses
- [ ] Implement `chat_completion()` method
- [ ] Support model, temperature, max_tokens parameters
- [ ] Parse response.content and response.tool_calls
- [ ] Extract token usage from response.usage
- [ ] Calculate cost based on usage
- [ ] Return LLMResponse with all required fields

**Acceptance Criteria**:
- [ ] Successfully calls OpenAI API
- [ ] Returns structured LLMResponse object
- [ ] TokenUsage is populated correctly
- [ ] Cost is calculated accurately

### Task 3: Implement chat_completion_stream()

**Description**: Streaming chat completion for real-time output.

**Implementation Details**:
- [ ] Implement `chat_completion_stream()` as async generator
- [ ] Support stream_options parameter for include_usage
- [ ] Yield text chunks as they arrive
- [ ] Handle connection errors gracefully

**Acceptance Criteria**:
- [ ] Yields text chunks in real-time
- [ ] Supports stream_options for usage tracking
- [ ] Properly handles stream termination

### Task 4: Implement chat_with_tools()

**Description**: Tool calling with automatic iteration and result collection.

**Implementation Details**:
- [ ] Implement `chat_with_tools()` method
- [ ] Accept tools list and tool_handlers dict
- [ ] Loop until no more tool_calls or max_iterations reached
- [ ] Execute tool handlers and collect results
- [ ] Append tool messages to conversation history
- [ ] Accumulate token usage across all iterations
- [ ] Return final LLMResponse with total usage

**Acceptance Criteria**:
- [ ] Handles multi-turn tool calling correctly
- [ ] Respects max_iterations limit
- [ ] Accumulates token usage across iterations
- [ ] Properly formats tool results for LLM

### Task 5: Define Error Classes

**Description**: Create specific exception types for different error scenarios.

**Implementation Details**:
- [ ] Define `OpenAIClientError` base exception
- [ ] Define `RateLimitError` for 429 errors
- [ ] Define `APIError` for other API errors
- [ ] Implement `_handle_error()` method to classify errors

**Acceptance Criteria**:
- [ ] All errors inherit from OpenAIClientError
- [ ] Rate limit errors are correctly identified
- [ ] API key errors are correctly identified
- [ ] Timeout errors are correctly identified

## Technical Specifications

### Data Classes

```python
@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float

@dataclass
class LLMResponse:
    content: str
    tool_calls: Optional[List[ChatCompletionMessageToolCall]] = None
    token_usage: Optional[TokenUsage] = None
```

### API Methods

```python
class OpenAIClient:
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
        **kwargs,
    ) -> LLMResponse

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream_options: Optional[dict] = None,
        **kwargs,
    ) -> AsyncIterator[str]

    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Tool],
        tool_handlers: Dict[str, callable],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_iterations: int = 10,
        **kwargs,
    ) -> LLMResponse
```

### Pricing Configuration

```python
_pricing = {
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}
```

## Testing Requirements

- [ ] Unit test for cost calculation
- [ ] Unit test for pricing lookup (exact and prefix match)
- [ ] Unit test for error classification
- [ ] Integration test for chat_completion with mock API
- [ ] Integration test for chat_with_tools with mock handlers
- [ ] Integration test for streaming with mock stream

## Notes & Warnings

1. **Stream Usage**: Streaming responses may not include usage data unless `stream_options={"include_usage": true}` is supported by the provider
2. **Cost Calculation**: Prices are estimates and should be updated regularly
3. **Tool Iteration**: Always enforce max_iterations to prevent infinite loops
4. **Async Context**: Ensure the client is properly initialized in async context
5. **API Key Security**: Never log or expose the API key in error messages
