# Phase B5: InterviewAgent Implementation

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B3 (BaseAgent Enhancement), B4 (Agent Prompts)
  - **Blocks**: None

## Goal

Implement the InterviewAgent with real LLM calls for intelligent user questioning and information gathering, with state management across conversation rounds.

## Detailed Tasks

### Task 1: Implement InterviewAgent Class Structure

**Description**: Set up the InterviewAgent with state management.

**Implementation Details**:
- [ ] Modify `packages/backend/app/agents/interview.py`
- [ ] Define InterviewState dataclass
- [ ] Set agent_type = "interview"
- [ ] Initialize state in __init__
- [ ] Implement reset_state() method

**Files to modify**:
- `packages/backend/app/agents/interview.py`

**Acceptance Criteria**:
- [ ] InterviewState tracks collected_info, rounds_used, confidence
- [ ] State can be reset for new sessions
- [ ] Agent initializes correctly

### Task 2: Implement process() Method

**Description**: Main method for processing user input.

**Implementation Details**:
- [ ] Implement `process()` async method
- [ ] Build message list with history
- [ ] Call `_call_llm()` with interview messages
- [ ] Parse LLM response as JSON
- [ ] Update state with collected info
- [ ] Enforce max_rounds limit
- [ ] Return AgentResult with all fields

**Acceptance Criteria**:
- [ ] System prompt is included in messages
- [ ] History is properly formatted
- [ ] State is updated after each round
- [ ] Max rounds (5) is enforced
- [ ] AgentResult contains all required fields

### Task 3: Implement _build_messages()

**Description**: Construct message list for LLM call.

**Implementation Details**:
- [ ] Build messages list starting with system prompt
- [ ] Append conversation history
- [ ] Add current state context (collected info, rounds used)
- [ ] Append current user input

**Acceptance Criteria**:
- [ ] System prompt from get_interview_prompt()
- [ ] History messages have correct format
- [ ] State context helps LLM understand progress
- [ ] User input is clearly labeled

### Task 4: Implement _parse_response()

**Description**: Parse LLM response into structured data.

**Implementation Details**:
- [ ] Try JSON parsing first
- [ ] Fallback to treating entire response as message
- [ ] Extract message, is_complete, confidence, collected_info
- [ ] Set sensible defaults for missing fields

**Acceptance Criteria**:
- [ ] Valid JSON returns complete parsed data
- [ ] Invalid JSON returns text as message
- [ ] Default values prevent crashes

### Task 5: Implement Helper Methods

**Description**: Convenience methods for using the agent.

**Implementation Details**:
- [ ] Implement `should_generate()` to check completion
- [ ] Implement `get_collected_info()` to retrieve gathered data

**Acceptance Criteria**:
- [ ] should_generate returns True when complete or confident
- [ ] get_collected_info returns dict or empty dict

## Technical Specifications

### InterviewState Dataclass

```python
@dataclass
class InterviewState:
    collected_info: dict = None
    rounds_used: int = 0
    max_rounds: int = 5
    confidence: float = 0.0
    is_complete: bool = False
```

### process() Method Signature

```python
class InterviewAgent(BaseAgent):
    agent_type = "interview"

    async def process(
        self,
        user_message: str,
        history: Optional[Sequence[dict]] = None,
    ) -> AgentResult:
        """
        Process user input and decide whether to question or end interview.

        Args:
            user_message: User's input text
            history: Conversation history

        Returns:
            AgentResult with:
            - message: Question to ask user or completion message
            - is_complete: Whether to proceed to generation
            - confidence: Information completeness (0-1)
            - context: JSON string of collected info
            - rounds_used: Number of interview rounds
        """
```

### Message Structure

```python
[
    {"role": "system", "content": INTERVIEW_SYSTEM_PROMPT},
    # ... history messages ...
    {"role": "user", "content": "Collected info: {...}\nRounds: 0/5\nUser input: ..."}
]
```

### Expected LLM Response Format

```json
{
  "message": "What style would you prefer for your portfolio?",
  "is_complete": false,
  "confidence": 0.6,
  "collected_info": {
    "page_type": "portfolio",
    "purpose": "showcase work"
  },
  "missing_info": ["style", "color_scheme", "sections"]
}
```

## Testing Requirements

- [ ] Unit test for state initialization and reset
- [ ] Unit test for _build_messages() with various histories
- [ ] Unit test for _parse_response() with valid JSON
- [ ] Unit test for _parse_response() with invalid JSON
- [ ] Unit test for max_rounds enforcement
- [ ] Integration test with mocked LLM client
- [ ] Integration test for complete interview flow

## Notes & Warnings

1. **State Persistence**: State is in-memory only; consider DB persistence for long sessions
2. **JSON Parsing**: LLM may return malformed JSON; always have fallback
3. **Round Counting**: Round counting includes the initial user input
4. **Confidence Threshold**: Consider 0.8 as reasonable threshold for auto-generation
5. **Context Management**: Include state context in messages to help LLM track progress
