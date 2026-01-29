# Phase B1: Chat API & Agent Orchestration

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: D1 (Core Schema)
  - **Blocks**: F2 (Chat Command), B2 (Session Management)

## Goal

Build the Chat API endpoint and Agent orchestration system (Interview, Generation, Refinement Agents). This is the core intelligence of Instant Coffee, handling all conversation logic and AI interactions.

## Detailed Tasks

### Task 1: Create FastAPI Application Structure

**Description**: Set up the FastAPI application with proper configuration, CORS, middleware, and routing structure.

**Implementation Details**:
- [ ] Create FastAPI app instance with proper configuration
- [ ] Set up CORS middleware for CLI access
- [ ] Configure request/response logging
- [ ] Implement error handlers
- [ ] Add health check endpoint
- [ ] Set up environment variable loading

**Files to modify/create**:
- `packages/backend/app/main.py`
- `packages/backend/app/config.py`
- `packages/backend/app/middleware.py`

**Acceptance Criteria**:
- [ ] FastAPI app starts without errors
- [ ] Health check endpoint responds correctly
- [ ] CORS is properly configured
- [ ] Environment variables are loaded
- [ ] Error handling works for common errors

---

### Task 2: Implement Base Agent Class

**Description**: Create the abstract base Agent class that Interview, Generation, and Refinement agents will inherit from.

**Implementation Details**:
- [ ] Define BaseAgent abstract class
- [ ] Implement Claude API client initialization
- [ ] Add retry logic with exponential backoff
- [ ] Implement token counting
- [ ] Add logging and error handling
- [ ] Create agent context management

**Files to modify/create**:
- `packages/backend/app/agents/base.py`
- `packages/backend/app/agents/__init__.py`

**Acceptance Criteria**:
- [ ] BaseAgent can be inherited by concrete agents
- [ ] Claude API connection works
- [ ] Retry logic handles API failures (3 retries)
- [ ] Token usage is accurately tracked
- [ ] Errors are properly logged and handled

---

### Task 3: Implement Interview Agent

**Description**: Build the Interview Agent that analyzes user input, evaluates information completeness, and generates adaptive questions.

**Implementation Details**:
- [ ] Create InterviewAgent class inheriting from BaseAgent
- [ ] Implement information completeness evaluation (0-100%)
- [ ] Build adaptive questioning logic (0-5 rounds based on completeness)
- [ ] Generate structured questions (single/multi-choice + text input)
- [ ] Parse AI response and extract structured data
- [ ] Handle conversation context and history

**Files to modify/create**:
- `packages/backend/app/agents/interview.py`
- `packages/backend/app/agents/prompts/interview_system.txt`

**Acceptance Criteria**:
- [ ] Agent correctly evaluates information completeness
- [ ] Questions are adaptive based on user input quality
- [ ] Maximum 3 questions per round
- [ ] Supports single/multi-choice and text input
- [ ] Correctly identifies when information is sufficient
- [ ] Stops after 5 rounds if information still insufficient

---

### Task 4: Implement Generation Agent

**Description**: Build the Generation Agent that creates mobile-first HTML pages with progressive generation and streaming updates.

**Implementation Details**:
- [ ] Create GenerationAgent class inheriting from BaseAgent
- [ ] Implement progressive generation with 5 stages (20%, 40%, 60%, 80%, 100%)
- [ ] Build mobile-first HTML template system
- [ ] Ensure all generated HTML follows mobile specifications
- [ ] Implement streaming response for progress updates
- [ ] Validate generated HTML structure

**Files to modify/create**:
- `packages/backend/app/agents/generation.py`
- `packages/backend/app/agents/prompts/generation_system.txt`
- `packages/backend/app/generators/mobile_html.py`

**Acceptance Criteria**:
- [ ] Generates valid HTML with inline CSS/JS
- [ ] All pages are mobile-optimized (9:19.5 ratio, max-width: 430px)
- [ ] Progressive generation sends 5 updates
- [ ] Scrollbars are hidden using .hide-scrollbar class
- [ ] Touch-optimized elements (min 44px buttons)
- [ ] Generated code is clean and maintainable

---

### Task 5: Implement Refinement Agent

**Description**: Build the Refinement Agent that understands user modification requests and updates existing HTML while maintaining mobile standards.

**Implementation Details**:
- [ ] Create RefinementAgent class inheriting from BaseAgent
- [ ] Implement modification intent parsing
- [ ] Build targeted HTML modification logic
- [ ] Preserve mobile-first standards during modifications
- [ ] Handle various modification types (style, content, layout, functionality)
- [ ] Validate modified HTML

**Files to modify/create**:
- `packages/backend/app/agents/refinement.py`
- `packages/backend/app/agents/prompts/refinement_system.txt`

**Acceptance Criteria**:
- [ ] Correctly interprets user modification requests
- [ ] Only modifies requested elements
- [ ] Maintains mobile-first standards after modification
- [ ] Preserves existing code quality
- [ ] Handles edge cases (ambiguous requests, non-existent elements)

---

### Task 6: Implement Agent Orchestrator

**Description**: Create the orchestration layer that manages agent transitions and conversation flow.

**Implementation Details**:
- [ ] Create AgentOrchestrator class
- [ ] Implement phase management (interview → generation → refinement)
- [ ] Handle agent transitions based on conversation state
- [ ] Manage shared context between agents
- [ ] Implement conversation history tracking
- [ ] Add phase-specific error handling

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py`

**Acceptance Criteria**:
- [ ] Correctly transitions between agent phases
- [ ] Maintains conversation context across agents
- [ ] Handles phase-specific logic correctly
- [ ] Recovers gracefully from agent failures
- [ ] Properly manages conversation state

---

### Task 7: Implement Chat API Endpoint

**Description**: Create the /api/chat endpoint that receives user messages and orchestrates agent responses.

**Implementation Details**:
- [ ] Define ChatRequest and ChatResponse Pydantic models
- [ ] Implement POST /api/chat endpoint
- [ ] Integrate with AgentOrchestrator
- [ ] Add streaming support for progressive generation
- [ ] Implement session creation and loading
- [ ] Add comprehensive error handling

**Files to modify/create**:
- `packages/backend/app/api/chat.py`
- `packages/backend/app/api/__init__.py`
- `packages/backend/app/api/models.py`

**Acceptance Criteria**:
- [ ] Endpoint accepts and validates chat requests
- [ ] Returns properly formatted chat responses
- [ ] Supports streaming for progressive generation
- [ ] Creates new sessions or loads existing ones
- [ ] Handles errors with appropriate status codes
- [ ] Response includes phase information and preview URL

## Technical Specifications

### API Contracts

#### POST /api/chat

**Request**:
```json
{
  "session_id": "abc123" | null,  // null for new session
  "message": "帮我做一个活动报名页面",
  "output_dir": "./instant-coffee-output"
}
```

**Response (Interview Phase)**:
```json
{
  "session_id": "abc123",
  "phase": "interview",
  "message": "好的！我想了解几个细节：\n\n1️⃣ 活动类型是什么？...",
  "is_complete": false,
  "preview_url": null
}
```

**Response (Generation Phase)**:
```json
{
  "session_id": "abc123",
  "phase": "generation",
  "message": "开始生成...\n\n━━━━━━━━━━━━━━━━ 60%\n✅ 样式已应用",
  "is_complete": false,
  "preview_url": null,
  "progress": 60
}
```

**Response (Generation Complete)**:
```json
{
  "session_id": "abc123",
  "phase": "refinement",
  "message": "✅ 生成完成！\n📂 预览: file:///.../index.html",
  "is_complete": true,
  "preview_url": "file:///Users/.../instant-coffee-output/index.html"
}
```

**Response (Refinement Phase)**:
```json
{
  "session_id": "abc123",
  "phase": "refinement",
  "message": "✅ 修改完成！刷新浏览器查看",
  "is_complete": true,
  "preview_url": "file:///Users/.../instant-coffee-output/index.html"
}
```

### Agent System Prompts

**Interview Agent System Prompt**:
Located in `app/agents/prompts/interview_system.txt`:
```
你是 Instant Coffee 的 Interview Agent，负责通过对话了解用户需求。

你的任务是：
1. 分析用户的输入，判断信息充分度 (0-100%)
2. 根据信息充分度决定提问深度:
   - 90%+ → 0-1轮提问
   - 70-90% → 2-3轮提问
   - 50-70% → 3-4轮提问
   - <50% → 4-5轮提问
3. 每轮最多问 3 个问题
4. 问题要具体、易于回答
5. 提供单选/多选选项 + 文字输入

[Full prompt from spec appendix A]
```

**Generation Agent System Prompt**:
Located in `app/agents/prompts/generation_system.txt`:
```
你是 Instant Coffee 的 Generation Agent，负责生成移动端优化的 HTML 页面。

移动端设计要求（必须遵守）:
1. 视口比例：9:19.5
2. 最大宽度：430px (iPhone Pro Max)
3. 隐藏滚动条：使用 .hide-scrollbar 类
[Full prompt from spec appendix B]
```

**Refinement Agent System Prompt**:
Located in `app/agents/prompts/refinement_system.txt`:
```
你是 Instant Coffee 的 Refinement Agent，负责根据用户反馈修改页面。

[Full prompt from spec appendix C]
```

### Business Logic Flow

```
User Message → Chat API
  ↓
Load/Create Session
  ↓
AgentOrchestrator.process()
  ↓
Determine Current Phase:
  ├─ interview: InterviewAgent.process()
  │    ├─ Evaluate completeness
  │    ├─ Generate questions OR
  │    └─ Transition to generation
  │
  ├─ generation: GenerationAgent.generate()
  │    ├─ Progressive generation (5 stages)
  │    ├─ Save HTML to filesystem
  │    ├─ Create version record
  │    └─ Transition to refinement
  │
  └─ refinement: RefinementAgent.refine()
       ├─ Parse modification intent
       ├─ Modify HTML
       ├─ Save as new version
       └─ Return updated preview URL
```

### Error Handling Strategy

```python
# Retry logic for AI API calls
@retry(max_attempts=3, backoff=exponential)
async def call_claude_api(prompt: str) -> str:
    try:
        response = await anthropic_client.messages.create(...)
        return response.content[0].text
    except RateLimitError:
        # Wait and retry
        raise
    except APIError as e:
        # Log and retry
        logger.error(f"API error: {e}")
        raise
    except Exception as e:
        # Fatal error, don't retry
        logger.error(f"Fatal error: {e}")
        raise FatalAgentError(e)
```

## Testing Requirements

- [ ] Unit tests for each Agent class
- [ ] Test information completeness evaluation logic
- [ ] Test adaptive questioning (different completeness levels)
- [ ] Test HTML generation with mobile standards
- [ ] Test modification intent parsing
- [ ] Test agent phase transitions
- [ ] Integration tests for full conversation flows
- [ ] Test retry logic and error handling
- [ ] Test streaming generation responses
- [ ] E2E test: Complete conversation from start to finish

## Notes & Warnings

- **API Key Management**: Ensure Anthropic API key is properly loaded from environment
- **Token Limits**: Claude has max token limits - handle long conversations gracefully
- **Streaming**: Implement proper streaming for progressive generation to avoid timeouts
- **Mobile Standards**: Always validate generated HTML meets mobile specifications
- **Context Window**: Manage conversation history to stay within Claude's context limits
- **Retry Logic**: Implement exponential backoff for API retries to avoid rate limits
- **Error Recovery**: Save conversation state before agent calls to enable recovery
- **Prompt Engineering**: Prompts are critical - test extensively with edge cases
