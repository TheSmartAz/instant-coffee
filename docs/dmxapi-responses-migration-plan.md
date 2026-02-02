# DMXAPI Responses 全量切换计划

> 目标：全量切换到 DMXAPI 的 `responses.create`（流式 + 非流式），包括 tool calling。
> 结论：后端统一走 Responses，前端保持 SSE 消费不变。

## 范围
- **包含**：所有 LLM 调用（chat、generation、refinement、interview、planner、tool calling）。
- **不包含**：前端 SSE 协议格式、消息存储模型、UI 行为（仅确保兼容）。

## 约束与前提
- DMXAPI 完全兼容 OpenAI Responses API（含 streaming 事件与 tool calling 事件）。
- 需要兼容现有工具链与事件流（ToolCall/ToolResult/Agent progress）。

## 现状简述
- 当前基于 `chat.completions`（stream + non-stream）。
- tool calling 依赖 `tool_calls` + `role=tool` 结果回传。
- SSE 由 `/api/chat/stream` 输出 `delta`，前端按 token 拼接显示。

## 目标状态
- 所有 LLM 调用统一走 `responses.create`。
- 流式输出改为解析 `response.output_text.delta` 事件，仍向前端输出 `delta`。
- tool calling 改为解析 Responses 的 tool-call output items / events。
- Token usage 计费逻辑保持（但字段映射变更）。

## 实施计划

### 1) 配置与适配层
- [ ] 新增 LLM API 模式开关（例如 `OPENAI_API_MODE=responses`），默认值可直接设为 `responses`。
- [ ] 允许传入 Responses 专用参数（`reasoning.effort`、`max_output_tokens` 等）。
- [ ] 确保 `base_url` / `api_key` 读取逻辑兼容 DMXAPI。

### 2) OpenAIClient 增加 Responses 通道
- [ ] 新增 `responses_create()`（非流式），返回统一的 `LLMResponse`。
- [ ] 新增 `responses_stream()`（流式），解析事件并 yield 文本 delta。
- [ ] 解析 Responses 的 usage 字段到 `TokenUsage`。
- [ ] 保留老的 `chat_completion(_stream)` 入口，但在全量切换后不再使用。

### 3) Tool calling 改造（关键）
- [ ] 新增 `responses_with_tools()`：
  - 解析 Responses output items 中的 tool call。
  - 触发本地 tool handler。
  - 将 tool 输出作为新的 `input` item 继续 `responses.create` 直到完成。
- [ ] 流式场景下，消费 tool‑call 事件：
  - 在收到 tool call 输入完成事件时触发工具。
  - 仍然发射现有 ToolCall/ToolResult 事件给 SSE。
- [ ] 处理并发/多工具调用：允许并行执行，需合并输出并确保事件顺序可追踪。

### 4) Agent / Orchestrator 接入
- [ ] `BaseAgent._call_llm` 改为使用 Responses（流式 / 非流式）。
- [ ] `BaseAgent._call_llm_with_tools` 改为使用 Responses tool calling。
- [ ] 保持 AgentProgress/Tool events 事件形态不变。

### 5) SSE 输出保持兼容
- [ ] `response.output_text.delta` → 继续向前端输出 `delta`。
- [ ] 最终完整文本在 `message` 字段发出，保持前端无改动。

### 6) 测试与回归
- [ ] 单元测试：新增 Responses streaming 与 tool calling 解析测试。
- [ ] 回归测试：现有 chat stream / tool events / interview flow / generation flow。
- [ ] 验证：Token usage 统计与成本计算仍正确。

## 影响文件（预估）
- `packages/backend/app/llm/openai_client.py`
- `packages/backend/app/agents/base.py`
- `packages/backend/app/agents/*`（若需要传递 reasoning / max_output_tokens）
- `packages/backend/app/config.py` / settings
- `packages/backend/app/api/chat.py`（SSE payload 结构维持）
- `packages/backend/tests/*`（新增 Responses 相关测试）

## 交付标准
- 所有 LLM 调用走 Responses，聊天与代码生成均可正常输出。
- 流式仍可实时增量显示。
- tool calling 在 Responses 模式下事件与结果稳定。
- 前端无需变更即可正常工作。

## 风险与缓解
- **风险**：tool calling 的事件模型与现有解析差异较大。
  - **缓解**：先实现非流式 tool calling，再补齐流式事件解析。
- **风险**：usage 字段结构差异导致计费不准。
  - **缓解**：在测试中对比 token 统计输出。

## 验收清单
- [ ] Chat SSE 流式输出正常
- [ ] Interview widget 正常交互（submit/skip/generate）
- [ ] Tool events 能显示在 EventList
- [ ] Page/Doc 生成与预览流程不受影响
- [ ] Token usage 统计正常
