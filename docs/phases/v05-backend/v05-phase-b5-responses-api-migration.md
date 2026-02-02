# Phase v05-B5: Responses API 迁移 - LLM 调用统一

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: v05-B6

## Goal

将所有 LLM 调用从 chat.completions 迁移到 DMXAPI Responses API，支持流式、非流式和 tool calling 的统一处理。

## Detailed Tasks

### Task 1: OpenAIClient Responses 通道

**Description**: 在 OpenAIClient 中添加 Responses API 支持

**Implementation Details**:
- [ ] 新增 `responses_create()` 方法 (非流式)
- [ ] 新增 `responses_stream()` 方法 (流式)
- [ ] 新增 `responses_with_tools()` 方法 (tool calling)
- [ ] 添加 OPENAI_API_MODE 配置项
- [ ] 兼容 DMXAPI base_url/api_key 读取
- [ ] 支持 Responses 专用参数 (reasoning.effort, max_output_tokens)

**Files to modify/create**:
- `packages/backend/app/llm/openai_client.py`
- `packages/backend/app/config.py`

**Acceptance Criteria**:
- [ ] responses_create 返回完整 LLMResponse
- [ ] responses_stream 正确 yield delta
- [ ] responses_with_tools 解析 tool-call 事件
- [ ] 配置正确加载

---

### Task 2: Responses 事件解析

**Description**: 解析 Responses API 事件格式

**Implementation Details**:
- [ ] 解析 `response.output_text.delta` 事件
- [ ] 解析 tool-call 事件
- [ ] 解析 usage 统计
- [ ] 将 Responses usage 映射到 TokenUsage
  - input_tokens → prompt_tokens
  - output_tokens → completion_tokens
- [ ] 原始 usage 写入 TokenUsage.raw

**Files to modify/create**:
- `packages/backend/app/llm/openai_client.py`

**Acceptance Criteria**:
- [ ] Delta 事件正确解析并 yield
- [ ] Tool-call 事件正确识别
- [ ] Usage 统计正确映射
- [ ] Raw usage 完整保存

---

### Task 3: Agent 调用迁移

**Description**: 将所有 Agent 调用切换到 Responses

**Implementation Details**:
- [ ] 修改 BaseAgent 调用接口
- [ ] InterviewAgent 切换到 responses_stream
- [ ] GenerationAgent 切换到 responses_create
- [ ] RefinementAgent 切换到 responses_stream
- [ ] ProductDocAgent 切换到 responses_create
- [ ] SitemapAgent 切换到 responses_create
- [ ] 保留 chat_completion 入口作为兼容层

**Files to modify/create**:
- `packages/backend/app/agents/base.py`
- `packages/backend/app/agents/interview.py`
- `packages/backend/app/agents/generation.py`
- `packages/backend/app/agents/refinement.py`
- `packages/backend/app/agents/product_doc.py`
- `packages/backend/app/agents/sitemap.py`

**Acceptance Criteria**:
- [ ] 所有 Agent 使用 Responses 调用
- [ ] 流式输出正常工作
- [ ] Tool calling 正常工作
- [ ] 兼容层仍可用

---

### Task 4: Tool Calling 事件处理

**Description**: 实现 Responses 模式下的 tool calling 流程

**Implementation Details**:
- [ ] 解析 tool-call output items
- [ ] 执行本地工具
- [ ] 构建工具结果续接 responses.create
- [ ] 支持并行多工具调用
- [ ] 保证事件顺序可追踪
- [ ] 生成 ToolCall/ToolResult SSE 事件

**Files to modify/create**:
- `packages/backend/app/llm/openai_client.py`
- `packages/backend/app/agents/base.py`

**Acceptance Criteria**:
- [ ] Tool-call 事件正确解析
- [ ] 工具执行成功
- [ ] 续接请求正确构造
- [ ] SSE 事件格式保持不变

---

### Task 5: SSE 事件兼容

**Description**: 确保 SSE 对前端输出格式不变

**Implementation Details**:
- [ ] response.output_text.delta → 继续输出 `delta` 事件
- [ ] tool-call → 输出 ToolCall 事件
- [ ] tool-result → 输出 ToolResult 事件
- [ ] 保持现有 SSE 事件结构
- [ ] 前端无需修改即可正确显示

**Files to modify/create**:
- `packages/backend/app/api/chat.py`

**Acceptance Criteria**:
- [ ] Delta 事件格式与之前一致
- [ ] ToolCall/ToolResult 格式一致
- [ ] 前端正确消费所有事件

---

### Task 6: Responses 测试覆盖

**Description**: 添加 Responses API 的测试用例

**Implementation Details**:
- [ ] 测试 responses_create 基本调用
- [ ] 测试 responses_stream 流式输出
- [ ] 测试 responses_with_tools 工具调用
- [ ] 测试 usage 映射正确性
- [ ] 测试并行工具调用
- [ ] 测试错误处理

**Files to modify/create**:
- `packages/backend/tests/test_openai_client.py` (新建)
- `packages/backend/tests/test_responses_api.py` (新建)

**Acceptance Criteria**:
- [ ] 所有测试通过
- [ ] 覆盖率 > 80%

## Technical Specifications

### OpenAIClient 接口

```python
class OpenAIClient:
    def responses_create(
        self,
        messages: List[Message],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs
    ) -> LLMResponse:
        """非流式 Responses 调用"""

    async def responses_stream(
        self,
        messages: List[Message],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs
    ) -> AsyncIterator[str]:
        """流式 Responses 调用，yield delta"""

    async def responses_with_tools(
        self,
        messages: List[Message],
        tools: List[Tool],
        model: str,
        **kwargs
    ) -> tuple[str, List[ToolCall]]:
        """带工具调用的 Responses，返回 (文本, 工具调用列表)"""

    # 兼容层 (保留但不推荐)
    def chat_completion(self, ...) -> LLMResponse:
        """兼容 chat.completions 入口"""

    async def chat_completion_stream(self, ...) -> AsyncIterator[str]:
        """兼容流式入口"""
```

### Usage 映射

```python
# Responses API usage
{
    "input_tokens": 1000,
    "output_tokens": 500,
    "total_tokens": 1500
}

# 映射到 TokenUsage
TokenUsage(
    prompt_tokens=1000,
    completion_tokens=500,
    total_tokens=1500,
    raw={
        "input_tokens": 1000,
        "output_tokens": 500,
        "total_tokens": 1500
    }
)
```

### SSE 事件格式 (保持不变)

```python
# Delta 事件
{
    "type": "delta",
    "content": "text fragment"
}

# ToolCall 事件
{
    "type": "tool_call",
    "tool": "function_name",
    "args": {...}
}

# ToolResult 事件
{
    "type": "tool_result",
    "tool": "function_name",
    "result": {...}
}
```

## Testing Requirements

- [ ] 单元测试: responses_create 基本功能
- [ ] 单元测试: responses_stream 流式输出
- [ ] 单元测试: responses_with_tools 工具调用
- [ ] 单元测试: usage 映射正确性
- [ ] 集成测试: Agent 调用迁移后正常工作
- [ ] 端到端测试: 完整对话流程

## Notes & Warnings

1. **SSE 兼容**: 前端依赖现有事件格式，不能随意变更
2. **工具调用续接**: responses.create 需要正确构造对话历史
3. **并行工具**: 需要合并多个工具输出并保证顺序
4. **配置兼容**: 支持 DMXAPI 的特殊配置需求
5. **回退机制**: 考虑 Responses 失败时的 chat.completions 回退 (可选)
