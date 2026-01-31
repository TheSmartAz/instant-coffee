# Instant Coffee - 技术规格说明书 (Spec v0.3)

**项目名称**: Instant Coffee (速溶咖啡)
**版本**: v0.3 - Agent LLM 调用 + Tools 系统
**日期**: 2026-01-31
**文档类型**: Technical Specification Document (TSD)

---

## 文档变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v0.1 | 2025-01-30 | 初始版本，CLI + 后端核心功能 | Interview |
| v0.2 | 2025-01-30 | Web 前端 + 执行流可视化 + Planner | Planning |
| v0.3 | 2025-01-31 | Agent LLM 调用 + Tools 系统 | Implementation |
| v0.3.1 | 2026-01-31 | 修订流式/工具/安全边界等细节 | Review |

---

## 设计决策访谈记录 (2026-01-31 修订)

本节记录了 spec-03 实现前的关键设计决策访谈结果。

### 核心决策

| 问题 | 决策 | 说明 |
|------|------|------|
| 流式输出策略 | 后端持续流式事件，前端可阶段展示 | 后端持续发射事件，前端默认只显示阶段完成信息，可切换实时 |
| Token 成本显示 | 会话结束汇总 | 减少刷屏干扰，会话结束时统一显示（必要时可实时） |
| 上下文管理 | LLM 管理 + 可插拔摘要 | 以 LLM 为主，预留摘要/裁剪策略以应对超长上下文 |
| HTML 提取 | 标记优先 | `<HTML_OUTPUT>` 标记 > `<!DOCTYPE html>` > 模糊匹配 |
| 版本历史 | DB 版本为准 + 文件镜像 | DB 版本管理为主，文件 `v{timestamp}_*.html` 作为可选镜像 |
| Tool 失败处理 | 让 LLM 决定 | 统一返回结构化 `{success, output, error}` 供 LLM 决策 |

### 详细问答

**Q: 流式 HTML 输出是否需要实时显示给用户？**
> A: 后端仍流式发射事件，但前端默认只在阶段完成时显示结果；需要时可以开启实时展示。

**Q: Token 成本是否应该实时显示？**
> A: 会在话结束时汇总显示。实时显示可能引发焦虑，静默记录更合适。

**Q: 消息历史超出上下文限制怎么办？**
> A: 以 LLM 管理为主，同时预留可插拔摘要/裁剪策略用于超长会话。

**Q: HTML 提取失败怎么办？**
> A: 采用三级策略：
> 1. 特殊标记 `<HTML_OUTPUT>...</HTML_OUTPUT>`（最可靠）
> 2. `<!DOCTYPE html>...</html>` 标准标记
> 3. `<html>...</html>` 模糊匹配

**Q: 版本历史如何管理？**
> A: DB 版本为准，文件作为镜像备份：
> - DB: Version 表维护当前/历史版本
> - 文件: `index.html` 当前预览 + `v{timestamp}_*.html` 镜像

**Q: Tool 执行失败如何处理？**
> A: 始终返回结构化 `{success, output, error}` 给 LLM，让它决定是否重试或换方式。

---

## 目录

1. [版本概述](#1-版本概述)
2. [设计决策访谈记录](#设计决策访谈记录-2025-01-31)
3. [架构设计](#3-架构设计)
4. [LLM 客户端实现](#4-llm-客户端实现)
5. [Agent 系统实现](#5-agent-系统实现)
6. [Tools 系统实现](#6-tools-系统实现)
7. [事件集成](#7-事件集成)
8. [Token 追踪](#8-token-追踪)
9. [错误处理](#9-错误处理)
10. [文件变更清单](#10-文件变更清单)
11. [验收标准](#11-验收标准)

---

## 1. 版本概述

### 1.1 版本定位

**Spec v0.3** 在 v0.2 (Web 前端 + Planner) 基础上，实现 **Agent LLM 调用** 和 **Tools 系统**，将占位的 Agent 替换为真实的 AI 调用。

**核心升级**:
- 🤖 **真实 LLM 调用** - Interview/Generation/Refinement Agent 真正调用 AI
- 🔧 **Tools 系统** - 支持 Function Calling，让 AI 能够执行实际操作
- 📊 **Token 追踪** - 完整记录每次 LLM 调用的 Token 消耗
- 🔄 **流式输出** - 后端流式事件，前端可按需实时展示

### 1.2 与 v0.2 的关系

| v0.2 (已完成) | v0.3 (本版本) |
|--------------|--------------|
| Agent 架构 (空壳) | Agent 真实 LLM 调用 |
| 事件系统 (静态) | 事件系统 (含 Tool 事件) |
| 占位返回 | 真实 AI 生成内容 |
| 无 Tool 调用 | 支持 Function Calling |

### 1.3 核心设计原则

**1.3.1 统一的 LLM 调用入口**
```
所有 Agent 通过 BaseAgent._call_llm() 发起调用
    ↓
统一的错误处理和重试
    ↓
统一的 Token 追踪
    ↓
统一的事件发射
```

**1.3.2 Tool 调用透明化**
```
LLM 返回 tool_calls
    ↓
Agent 执行 Tool (emit tool_call event)
    ↓
Tool 返回结果 (emit tool_result event)
    ↓
结果返回给 LLM 继续处理
```

**1.3.3 流式响应优先**
```
LLM 流式输出
    ↓
实时发射 agent_progress 事件
    ↓
前端默认阶段性展示（可切换实时）
    ↓
完整响应后发射 agent_end 事件
```

---

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Instant Coffee                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                      API Layer                             │  │
│  │  /api/chat → Orchestrator → Agents                        │  │
│  │  /api/plan → Planner → Executor (按需)                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     Agent Layer                            │  │
│  │                                                         │   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │   │  │
│  │  │ Interview   │  │ Generation  │  │ Refinement      │  │   │  │
│  │  │   Agent     │  │   Agent     │  │   Agent         │  │   │  │
│  │  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │   │  │
│  │         │                │                  │           │   │  │
│  │         └────────────────┼──────────────────┘           │   │  │
│  │                          ▼                              │   │  │
│  │                   ┌─────────────┐                       │   │  │
│  │                   │  BaseAgent  │                       │   │  │
│  │                   │  +_call_llm │                       │   │  │
│  │                   └──────┬──────┘                       │   │  │
│  └──────────────────────────┼──────────────────────────────┘   │  │
│                             │                                     │
│                             ▼                                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    LLM Layer                              │  │
│  │                                                         │   │  │
│  │  ┌─────────────────────────────────────────────────────┐│   │  │
│  │  │              OpenAIClient                           ││   │  │
│  │  │  - chat_completion()    - 非流式调用               ││   │  │
│  │  │  - chat_completion_stream()  - 流式调用            ││   │  │
│  │  │  - chat_with_tools()    - Tool 调用                ││   │  │
│  │  └─────────────────────────────────────────────────────┘│   │  │
│  │                                                         │   │  │
│  │  ┌─────────────────────────────────────────────────────┐│   │  │
│  │  │              Tools Registry                         ││   │  │
│  │  │  - filesystem_write / filesystem_read               ││   │  │
│  │  │  - validate_html                                    ││   │  │
│  │  └─────────────────────────────────────────────────────┘│   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   Services Layer                          │  │
│  │  - TokenTrackerService  - Token 追踪                     │  │
│  │  - EventEmitter        - 事件发射                        │  │
│  │  - FilesystemService   - 文件操作                        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 文件结构

```
packages/backend/app/
├── llm/                          # 新增: LLM 调用层
│   ├── __init__.py
│   ├── openai_client.py          # OpenAI SDK 封装
│   └── tools.py                  # Tools 定义
│
├── agents/                       # 现有: Agent 层
│   ├── __init__.py
│   ├── base.py                   # 修改: 添加 _call_llm
│   ├── prompts.py                # 新增: Agent System Prompts
│   ├── interview.py              # 修改: 实现真实 LLM 调用
│   ├── generation.py             # 修改: 实现真实 LLM 调用
│   └── refinement.py             # 修改: 实现真实 LLM 调用
│
├── events/                       # 现有: 事件系统
│   ├── models.py                 # 已完成
│   ├── emitter.py                # 已完成
│   └── types.py                  # 已完成
│
├── services/                     # 现有: 服务层
│   ├── token_tracker.py          # 已完成
│   └── filesystem.py             # 已完成
│
└── config.py                     # 现有: 配置 (已支持 OpenAI)
```

### 3.3 数据流

**普通对话流程**:
```
用户输入
    ↓
InterviewAgent.process()
    ↓
BaseAgent._call_llm(messages)
    ↓
发射 agent_start 事件
    ↓
OpenAIClient.chat_completion() / chat_completion_stream()
    ↓
（流式）持续发射 agent_progress
    ↓
TokenTrackerService.record_usage()
    ↓
发射 agent_end 事件
    ↓
返回 AgentResult
```
> 注: 流式调用可能无法直接获得 usage；需要时可启用 `stream_options.include_usage` 或改用非流式调用统计。

**Tool 调用流程**:
```
LLM 返回 tool_calls
    ↓
Agent 遍历 tool_calls
    ↓
发射 tool_call 事件
    ↓
执行 Tool (调用对应的 Tool Handler)
    ↓
发射 tool_result 事件
    ↓
收集所有 Tool 结果
    ↓
将结果返回给 LLM (作为 assistant 消息 + tool_results)
    ↓
继续等待 LLM 响应
    ↓
TokenTrackerService.record_usage() (累计所有 Token)
```

---

## 4. LLM 客户端实现

### 4.1 OpenAIClient 类设计

**文件**: `packages/backend/app/llm/openai_client.py`

```python
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import AsyncGenerator, AsyncIterator, Dict, List, Optional, Union

from openai import AsyncOpenAI
from openai.types import ChatCompletion, ChatCompletionChunk, ChatCompletionMessageToolCall
from openai.types.chat import ChatCompletionToolMessageParam

from ...config import Settings, get_settings
from ...services.token_tracker import TokenTrackerService
from .tools import Tool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token 使用量统计"""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    tool_calls: Optional[List[ChatCompletionMessageToolCall]] = None
    token_usage: Optional[TokenUsage] = None


class OpenAIClientError(Exception):
    """OpenAI 客户端错误"""
    pass


class RateLimitError(OpenAIClientError):
    """速率限制错误"""
    pass


class APIError(OpenAIClientError):
    """API 错误"""
    pass


class OpenAIClient:
    """
    OpenAI API 客户端封装

    提供:
    - 非流式对话
    - 流式对话
    - Tool/Function Calling
    - Token 使用量追踪
    - 统一的错误处理
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        token_tracker: Optional[TokenTrackerService] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.token_tracker = token_tracker

        # 初始化 OpenAI 客户端
        self.client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
        )

        # 模型定价 (USD per 1M tokens)
        self._pricing = {
            "gpt-4o": {"input": 5.0, "output": 15.0},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4-turbo": {"input": 10.0, "output": 30.0},
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        }

    def _get_pricing(self, model: str) -> Dict[str, float]:
        """获取模型定价"""
        # 尝试精确匹配
        if model in self._pricing:
            return self._pricing[model]
        # 模糊匹配 (取前缀)
        for prefix, pricing in self._pricing.items():
            if model.startswith(prefix):
                return pricing
        # 默认定价
        return {"input": 1.0, "output": 3.0}

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """计算 API 调用成本 (USD)"""
        pricing = self._get_pricing(model)
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        非流式对话完成

        Args:
            messages: 消息列表
            model: 模型名称 (默认使用 settings 中的配置)
            temperature: 温度参数
            max_tokens: 最大输出 token
            tools: 可用的工具列表

        Returns:
            LLMResponse 对象
        """
        model = model or self.settings.model
        temperature = temperature if temperature is not None else self.settings.temperature
        max_tokens = max_tokens or self.settings.max_tokens

        try:
            # 构建请求参数
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            }

            if tools:
                params["tools"] = [tool.to_openai_format() for tool in tools]
                params["tool_choice"] = "auto"

            # 发送请求
            response: ChatCompletion = await self.client.chat.completions.create(**params)

            # 解析响应
            choice = response.choices[0]
            message = choice.message

            content = message.content or ""
            tool_calls = message.tool_calls

            # 计算 Token 使用量
            usage = response.usage
            token_usage = TokenUsage(
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cost_usd=self._calculate_cost(
                    model,
                    usage.prompt_tokens,
                    usage.completion_tokens
                ),
            )

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                token_usage=token_usage,
            )

        except Exception as e:
            logger.exception("LLM API 调用失败")
            raise self._handle_error(e)

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream_options: Optional[dict] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        流式对话完成

        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大输出 token

        Yields:
            流式输出的文本片段
        """
        model = model or self.settings.model
        temperature = temperature if temperature is not None else self.settings.temperature
        max_tokens = max_tokens or self.settings.max_tokens

        try:
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
                **kwargs,
            }
            if stream_options:
                params["stream_options"] = stream_options

            stream = await self.client.chat.completions.create(**params)

            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.exception("LLM 流式调用失败")
            raise self._handle_error(e)

    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Tool],
        tool_handlers: Dict[str, callable],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_iterations: int = 10,
        **kwargs,
    ) -> LLMResponse:
        """
        带 Tool 调用的对话

        处理完整的 tool calling 循环:
        1. 发送请求
        2. 如果 LLM 返回 tool_calls，执行并收集结果
        3. 将结果返回给 LLM
        4. 重复直到 LLM 不再需要调用工具

        Args:
            messages: 消息列表 (会被修改，包含 tool 结果)
            tools: 可用的工具
            tool_handlers: 工具名 -> 处理函数 的映射
            model: 模型名称
            temperature: 温度参数
            max_iterations: 最大迭代次数 (防止无限循环)

        Returns:
            最终的 LLMResponse
        """
        model = model or self.settings.model
        temperature = temperature if temperature is not None else self.settings.temperature

        total_input_tokens = 0
        total_output_tokens = 0

        for iteration in range(max_iterations):
            # 发送请求
            response = await self.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                tools=tools,
                **kwargs,
            )

            # 累计 Token
            if response.token_usage:
                total_input_tokens += response.token_usage.input_tokens
                total_output_tokens += response.token_usage.output_tokens

            # 如果没有 tool_calls，完成
            if not response.tool_calls:
                break

            # 执行 tool calls
            tool_messages = []
            for tool_call in response.tool_calls:
                tool_name = tool_call.function.name
                tool_id = tool_call.id
                arguments = tool_call.function.arguments

                # 调用工具处理函数
                try:
                    handler = tool_handlers.get(tool_name)
                    if handler:
                        result = await handler(**json.loads(arguments))
                        success = True
                        output = result
                    else:
                        success = False
                        output = None
                        error = f"Unknown tool: {tool_name}"
                except Exception as e:
                    success = False
                    output = None
                    error = str(e)

                # 构建 tool 结果消息 (始终使用结构化 JSON)
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": json.dumps({
                        "success": success,
                        "output": output,
                        "error": error,
                    }, ensure_ascii=False),
                })

            # 将 tool 结果添加到消息历史
            messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": response.tool_calls,
            })
            messages.extend(tool_messages)

        else:
            logger.warning(f"Tool 调用超过 {max_iterations} 次，强制退出")

        # 返回最终结果
        if total_input_tokens > 0 or total_output_tokens > 0:
            cost = self._calculate_cost(model, total_input_tokens, total_output_tokens)
            token_usage = TokenUsage(
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                total_tokens=total_input_tokens + total_output_tokens,
                cost_usd=cost,
            )
            return LLMResponse(
                content=response.content,
                token_usage=token_usage,
            )

        return response

    def _handle_error(self, error: Exception) -> OpenAIClientError:
        """统一错误处理"""
        error_str = str(error).lower()

        if "rate_limit" in error_str or "429" in error_str:
            return RateLimitError(f"速率限制: {error}")

        if "invalid_api_key" in error_str or "401" in error_str:
            return APIError(f"无效的 API Key: {error}")

        if "timeout" in error_str or "504" in error_str:
            return APIError(f"请求超时: {error}")

        return APIError(f"LLM API 错误: {error}")


__all__ = [
    "OpenAIClient",
    "OpenAIClientError",
    "RateLimitError",
    "APIError",
    "LLMResponse",
    "TokenUsage",
]
```

> 注: 流式调用若需 usage，可在支持的平台传 `stream_options={"include_usage": true}` 并自行累计；否则使用非流式统计。

### 4.2 Tools 定义

**文件**: `packages/backend/app/llm/tools.py`

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pydantic


class BaseModel(pydantic.BaseModel):
    """Pydantic 基础模型"""
    pass


# ============ Tool Schema 定义 ============

@dataclass
class WriteFileParams:
    """写入文件参数"""
    path: str
    content: str
    encoding: str = "utf-8"


@dataclass
class ReadFileParams:
    """读取文件参数"""
    path: str
    encoding: str = "utf-8"


@dataclass
class ValidateHtmlParams:
    """HTML 验证参数"""
    html: str


@dataclass
class ListDirParams:
    """列出目录内容参数"""
    path: str
    pattern: Optional[str] = None


@dataclass
class ExistsParams:
    """检查文件是否存在参数"""
    path: str


# ============ Tool 类 ============

class Tool:
    """
    Tool 定义

    用于描述 AI 可以调用的工具。
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters

    def to_openai_format(self) -> Dict[str, Any]:
        """转换为 OpenAI Tool Format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolResult:
    """
    Tool 执行结果
    """

    def __init__(
        self,
        success: bool,
        output: Any = None,
        error: Optional[str] = None,
    ) -> None:
        self.success = success
        self.output = output
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
        }
        if self.output is not None:
            result["output"] = self.output
        if self.error is not None:
            result["error"] = self.error
        return result


# ============ 预定义 Tools ============

# Filesystem Write Tool
FILESYSTEM_WRITE_TOOL = Tool(
    name="filesystem_write",
    description="Write content to a file. Use this to save generated HTML or other files.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The file path to write to",
            },
            "content": {
                "type": "string",
                "description": "The content to write",
            },
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)",
                "enum": ["utf-8", "gbk"],
                "default": "utf-8",
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    },
)

# Filesystem Read Tool
FILESYSTEM_READ_TOOL = Tool(
    name="filesystem_read",
    description="Read content from a file. Use this to read existing HTML files.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The file path to read from",
            },
            "encoding": {
                "type": "string",
                "description": "File encoding (default: utf-8)",
                "enum": ["utf-8", "gbk"],
                "default": "utf-8",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    },
)

# Validate HTML Tool
VALIDATE_HTML_TOOL = Tool(
    name="validate_html",
    description="Validate HTML content against mobile-first standards.",
    parameters={
        "type": "object",
        "properties": {
            "html": {
                "type": "string",
                "description": "The HTML content to validate",
            },
        },
        "required": ["html"],
        "additionalProperties": False,
    },
)


def get_filesystem_tools() -> List[Tool]:
    """获取文件系统相关 tools"""
    return [FILESYSTEM_WRITE_TOOL, FILESYSTEM_READ_TOOL]


def get_all_tools() -> List[Tool]:
    """获取所有可用的 tools"""
    return [
        FILESYSTEM_WRITE_TOOL,
        FILESYSTEM_READ_TOOL,
        VALIDATE_HTML_TOOL,
    ]

# 说明: ListDirParams / ExistsParams 为预留工具参数，暂不暴露给 LLM。


__all__ = [
    "Tool",
    "ToolResult",
    "WriteFileParams",
    "ReadFileParams",
    "ValidateHtmlParams",
    "ListDirParams",
    "ExistsParams",
    "FILESYSTEM_WRITE_TOOL",
    "FILESYSTEM_READ_TOOL",
    "VALIDATE_HTML_TOOL",
    "get_filesystem_tools",
    "get_all_tools",
]
```

---

## 5. Agent 系统实现

### 5.1 BaseAgent 修改

**文件**: `packages/backend/app/agents/base.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from ..config import Settings
from ..events.emitter import EventEmitter
from ..events.models import (
    AgentEndEvent,
    AgentProgressEvent,
    AgentStartEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from ..llm.openai_client import OpenAIClient, LLMResponse
from ..services.token_tracker import TokenTrackerService


class APIError(Exception):
    """Generic API error."""


class RateLimitError(APIError):
    """Rate limit exceeded."""


@dataclass
class AgentResult:
    message: str
    is_complete: bool = True
    confidence: Optional[float] = None
    context: Optional[str] = None
    rounds_used: Optional[int] = None
    token_usage: Optional[dict] = None


class BaseAgent:
    """
    Agent 基类

    提供:
    - LLM 客户端初始化
    - 统一的 _call_llm() 方法
    - 事件发射方法
    - Tool 调用支持
    """

    agent_type: str = "base"

    def __init__(
        self,
        db,
        session_id: str,
        settings: Settings,
        event_emitter: Optional[EventEmitter] = None,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        token_tracker: Optional[TokenTrackerService] = None,
    ) -> None:
        self.db = db
        self.session_id = session_id
        self.settings = settings
        self.event_emitter = event_emitter
        self.agent_id = agent_id or f"{self.agent_type}_1"
        self.task_id = task_id
        self.token_tracker = token_tracker

        # 初始化 LLM 客户端
        self._llm_client = OpenAIClient(
            settings=settings,
            token_tracker=token_tracker,
        )

    async def _call_llm(
        self,
        messages: List[dict],
        *,
        agent_type: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List] = None,
        stream: bool = False,
        emit_progress: bool = True,
        context: Optional[str] = None,
    ) -> LLMResponse:
        """
        统一的 LLM 调用入口

        Args:
            messages: 消息历史
            agent_type: Agent 类型 (用于 Token 追踪)
            model: 模型名称
            temperature: 温度
            max_tokens: 最大 token
            tools: 可用的工具列表
            stream: 是否流式输出
            emit_progress: 是否发射进度事件
            context: 额外的上下文信息

        Returns:
            LLMResponse 对象
        """
        agent_type = agent_type or self.agent_type

        # 发射开始事件
        self._emit_agent_start(context=context)

        try:
            if stream:
                # 流式调用
                full_response = ""
                async for chunk in self._llm_client.chat_completion_stream(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    full_response += chunk
                    if emit_progress and chunk:
                        progress = min(90, 10 + len(full_response) // 100)
                        self._emit_agent_progress(
                            message=chunk[-200:],
                            progress=progress,
                        )
                response = LLMResponse(content=full_response)
            else:
                # 非流式调用
                response = await self._llm_client.chat_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                )

            # 记录 Token 使用
            if response.token_usage and self.token_tracker:
                self.token_tracker.record_usage(
                    session_id=self.session_id,
                    agent_type=agent_type,
                    model=model or self.settings.model,
                    input_tokens=response.token_usage.input_tokens,
                    output_tokens=response.token_usage.output_tokens,
                    cost_usd=response.token_usage.cost_usd,
                )

            # 发射结束事件
            self._emit_agent_end(
                status="success",
                summary=response.content[:200] if response.content else None,
            )

            return response

        except Exception as e:
            # 发射失败事件
            self._emit_agent_end(
                status="failed",
                summary=str(e),
            )
            raise

    async def _call_llm_with_tools(
        self,
        messages: List[dict],
        tools: List,
        tool_handlers: dict,
        *,
        agent_type: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_iterations: int = 10,
        context: Optional[str] = None,
    ) -> LLMResponse:
        """
        带有 Tool 调用的 LLM 调用

        处理完整的 tool calling 循环，并发射 tool_call/tool_result 事件。
        """
        agent_type = agent_type or self.agent_type

        # 发射开始事件
        self._emit_agent_start(context=context)

        # 包装 tool handlers 以添加事件发射
        wrapped_handlers = {}
        for tool_name, handler in tool_handlers.items():
            wrapped_handlers[tool_name] = self._wrap_tool_handler(
                tool_name,
                handler,
                agent_type,
            )

        try:
            response = await self._llm_client.chat_with_tools(
                messages=messages,
                tools=tools,
                tool_handlers=wrapped_handlers,
                model=model,
                temperature=temperature,
                max_iterations=max_iterations,
            )

            # 记录 Token 使用
            if response.token_usage and self.token_tracker:
                self.token_tracker.record_usage(
                    session_id=self.session_id,
                    agent_type=agent_type,
                    model=model or self.settings.model,
                    input_tokens=response.token_usage.input_tokens,
                    output_tokens=response.token_usage.output_tokens,
                    cost_usd=response.token_usage.cost_usd,
                )

            # 发射结束事件
            self._emit_agent_end(
                status="success",
                summary=response.content[:200] if response.content else None,
            )

            return response

        except Exception as e:
            self._emit_agent_end(
                status="failed",
                summary=str(e),
            )
            raise

    def _emit_agent_start(self, context: Optional[str] = None) -> None:
        """发射 agent_start 事件"""
        if self.event_emitter:
            event = AgentStartEvent(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                task_id=self.task_id,
            )
            self.event_emitter.emit(event)

    def _emit_agent_progress(self, message: str, progress: int) -> None:
        """发射 agent_progress 事件"""
        if self.event_emitter:
            event = AgentProgressEvent(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                task_id=self.task_id,
                message=message,
                progress=progress,
            )
            self.event_emitter.emit(event)

    def _emit_agent_end(self, status: str, summary: Optional[str] = None) -> None:
        """发射 agent_end 事件"""
        if self.event_emitter:
            event = AgentEndEvent(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                task_id=self.task_id,
                status=status,
                summary=summary,
            )
            self.event_emitter.emit(event)

    def _wrap_tool_handler(
        self,
        tool_name: str,
        handler: callable,
        agent_type: str,
    ) -> callable:
        """
        包装 tool handler 以添加事件发射
        """
        async def wrapped_handler(**kwargs):
            # 发射 tool_call 事件
            if self.event_emitter:
                self.event_emitter.emit(ToolCallEvent(
                    agent_id=self.agent_id,
                    agent_type=agent_type,
                    task_id=self.task_id,
                    tool_name=tool_name,
                    tool_input=kwargs,
                ))

            try:
                result = await handler(**kwargs)

                # 发射 tool_result 事件 (成功)
                if self.event_emitter:
                    self.event_emitter.emit(ToolResultEvent(
                        agent_id=self.agent_id,
                        agent_type=agent_type,
                        task_id=self.task_id,
                        tool_name=tool_name,
                        success=True,
                        tool_output=result,
                    ))

                return result

            except Exception as e:
                # 发射 tool_result 事件 (失败)
                if self.event_emitter:
                    self.event_emitter.emit(ToolResultEvent(
                        agent_id=self.agent_id,
                        agent_type=agent_type,
                        task_id=self.task_id,
                        tool_name=tool_name,
                        success=False,
                        error=str(e),
                    ))
                raise

        return wrapped_handler


__all__ = ["APIError", "RateLimitError", "AgentResult", "BaseAgent"]
```

### 5.2 Agent Prompts

**文件**: `packages/backend/app/agents/prompts.py`

```python
"""
Agent System Prompts

包含所有 Agent 的 System Prompt 模板。
"""

# ============ Interview Agent Prompt ============

INTERVIEW_SYSTEM_PROMPT = """你是 Instant Coffee 的 Interview Agent，负责通过对话了解用户需求。

你的任务是：
1. 分析用户的输入，判断信息充分度 (0-100%)
2. 根据信息充分度决定是否需要继续提问:
   - 90%+ → 信息非常充分，可以直接生成
   - 70-90% → 信息较充分，问 1-2 个关键问题
   - 50-70% → 信息一般，问 2-3 个问题
   - <50% → 信息不足，多问几个问题了解需求
3. 每轮最多问 3 个问题
4. 问题要具体、易于回答
5. 提供选项让用户选择，同时支持文字输入

输出格式 (JSON):
{{
  "message": "展示给用户的问题文本 (支持 Markdown)",
  "is_complete": true/false,
  "confidence": 0.0-1.0,
  "collected_info": {{"已收集的信息": "值"}},
  "missing_info": ["还缺少的信息"]
}}

注意事项:
- 使用友好、日常的语言
- 用 Emoji 让对话更有亲和力 ✨
- 不使用技术术语
- 如果用户已经提供了足够的信息，果断结束提问
- 收集的信息要结构化，方便后续生成
"""


# ============ Generation Agent Prompt ============

GENERATION_SYSTEM_PROMPT = """你是 Instant Coffee 的 Generation Agent，负责生成移动端优化的 HTML 页面。

## 移动端设计要求 (必须遵守)

### 视口和容器
- 视口比例: 9:19.5 (手机竖屏)
- 最大宽度: 430px (iPhone Pro Max)
- 居中显示，两侧留白

### 基础样式
- 字体: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
- 正文字号: 16px
- 标题字号: 24-32px
- 行高: 1.5-1.6

### 交互元素
- 按钮最小高度: 44px (触摸优化)
- 触摸区域足够大
- 禁用双击缩放

### 滚动条处理
- 隐藏滚动条: 使用 .hide-scrollbar 类
```css
.hide-scrollbar {{
    -ms-overflow-style: none;
    scrollbar-width: none;
}}
.hide-scrollbar::-webkit-scrollbar {{
    display: none;
}}
```

### 颜色系统
- 使用柔和的渐变色背景
- 主要操作按钮使用品牌色 (#007AFF 等)
- 文字使用深色 (#1a1a1a)
- 背景使用浅色 (#f5f5f7)

## 技术要求

1. 单文件 HTML (CSS 和 JS 内联)
2. 无外部依赖 (除 Google Fonts)
3. 使用现代 CSS (Flexbox/Grid)
4. 图片响应式 (max-width: 100%)
5. 支持触摸交互

## 输出格式

直接输出完整的 HTML 代码，用特殊标记包裹以便提取:

```
<HTML_OUTPUT>
<!DOCTYPE html>
<html>
...
</html>
</HTML_OUTPUT>
```

不要在任何其他内容（如代码块标记 ```html 或额外说明），只输出这个标记包裹的 HTML。

## 渐进式生成

生成过程分为 5 个阶段:
1. 20%: 页面结构 (骨架)
2. 40%: 核心内容
3. 60%: 样式应用
4. 80%: 交互逻辑
5. 100%: 移动端优化

如果需要保存文件，可以使用 filesystem_write 工具。
"""


# ============ Refinement Agent Prompt ============

REFINEMENT_SYSTEM_PROMPT = """你是 Instant Coffee 的 Refinement Agent，负责根据用户反馈修改页面。

你的任务是：
1. 理解用户的修改意图
2. 定位需要修改的部分
3. 生成修改后的完整 HTML
4. 保持移动端适配标准

修改原则:
- 只修改用户提到的部分
- 不随意改动其他内容
- 保持代码质量和可读性
- 确保修改后仍符合移动端标准

支持的修改类型:
- 样式调整 (颜色、大小、间距、字体等)
- 内容修改 (文字、图片、链接等)
- 布局调整 (位置、对齐、间距等)
- 功能添加 (按钮、表单、动画等)
- 删除不需要的元素

输出格式:
直接输出修改后的完整 HTML 代码，用特殊标记包裹:

```
<HTML_OUTPUT>
<!DOCTYPE html>
<html>
...修改后的完整内容...
</html>
</HTML_OUTPUT>
```

不要在任何其他内容，只输出这个标记包裹的 HTML。

如果需要保存修改后的文件，可以使用 filesystem_write 工具。
"""


# ============ 工具函数 ============

def get_interview_prompt() -> str:
    """获取 Interview Agent System Prompt"""
    return INTERVIEW_SYSTEM_PROMPT


def get_generation_prompt() -> str:
    """获取 Generation Agent System Prompt"""
    return GENERATION_SYSTEM_PROMPT


def get_refinement_prompt() -> str:
    """获取 Refinement Agent System Prompt"""
    return REFINEMENT_SYSTEM_PROMPT


__all__ = [
    "INTERVIEW_SYSTEM_PROMPT",
    "GENERATION_SYSTEM_PROMPT",
    "REFINEMENT_SYSTEM_PROMPT",
    "get_interview_prompt",
    "get_generation_prompt",
    "get_refinement_prompt",
]
```

### 5.3 InterviewAgent 实现

**文件**: `packages/backend/app/agents/interview.py`

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .base import AgentResult, BaseAgent
from .prompts import get_interview_prompt


@dataclass
class InterviewState:
    """访谈状态"""
    collected_info: dict = None
    rounds_used: int = 0
    max_rounds: int = 5
    confidence: float = 0.0
    is_complete: bool = False


class InterviewAgent(BaseAgent):
    """Interview Agent - 需求收集"""

    agent_type = "interview"

    def __init__(
        self,
        db,
        session_id: str,
        settings,
        event_emitter=None,
        agent_id=None,
        task_id=None,
        token_tracker=None,
    ) -> None:
        super().__init__(
            db=db,
            session_id=session_id,
            settings=settings,
            event_emitter=event_emitter,
            agent_id=agent_id,
            task_id=task_id,
            token_tracker=token_tracker,
        )
        self.state = InterviewState()

    def reset_state(self) -> None:
        """重置访谈状态"""
        self.state = InterviewState()

    async def process(
        self,
        user_message: str,
        history: Optional[Sequence[dict]] = None,
    ) -> AgentResult:
        """
        处理用户输入，决定是提问还是结束访谈

        Args:
            user_message: 用户的输入
            history: 对话历史

        Returns:
            AgentResult: 包含问题或生成信号
        """
        # 构建消息列表
        messages = self._build_messages(user_message, history)

        # 调用 LLM
        response = await self._call_llm(
            messages=messages,
            agent_type=self.agent_type,
            context="interview_process",
        )

        # 解析响应
        result = self._parse_response(response.content)

        # 更新状态
        self.state.rounds_used += 1
        if result.get("collected_info"):
            self.state.collected_info.update(result["collected_info"])
        self.state.confidence = result.get("confidence", 0.5)
        self.state.is_complete = result.get("is_complete", False)

        # 超过最大轮次，强制结束
        if self.state.rounds_used >= self.state.max_rounds:
            self.state.is_complete = True

        return AgentResult(
            message=result.get("message", ""),
            is_complete=self.state.is_complete,
            confidence=self.state.confidence,
            context=json.dumps(self.state.collected_info),
            rounds_used=self.state.rounds_used,
        )

    def _build_messages(
        self,
        user_message: str,
        history: Optional[Sequence[dict]] = None,
    ) -> List[dict]:
        """构建消息列表"""
        messages = []

        # System prompt
        messages.append({
            "role": "system",
            "content": get_interview_prompt(),
        })

        # 对话历史
        if history:
            for msg in history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        # 当前用户输入
        # 添加访谈状态上下文
        state_context = ""
        if self.state.collected_info:
            state_context = f"\n已收集的信息:\n{json.dumps(self.state.collected_info, ensure_ascii=False)}\n"
        if self.state.rounds_used > 0:
            state_context += f"\n已提问 {self.state.rounds_used} 轮，最多 5 轮。"

        messages.append({
            "role": "user",
            "content": f"{state_context}\n用户输入: {user_message}",
        })

        return messages

    def _parse_response(self, response_content: str) -> dict:
        """解析 LLM 响应"""
        try:
            # 尝试 JSON 解析
            return json.loads(response_content)
        except json.JSONDecodeError:
            # 如果不是 JSON，返回原始内容作为问题
            return {
                "message": response_content,
                "is_complete": False,
                "confidence": 0.5,
                "collected_info": {},
            }

    def should_generate(self) -> bool:
        """判断是否可以开始生成"""
        return self.state.is_complete or self.state.confidence > 0.8

    def get_collected_info(self) -> dict:
        """获取收集到的信息"""
        return self.state.collected_info or {}


__all__ = ["InterviewAgent", "InterviewState"]
```

### 5.4 GenerationAgent 实现

**文件**: `packages/backend/app/agents/generation.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from ..events.emitter import EventEmitter
from ..llm.tools import get_filesystem_tools
from .base import AgentResult, BaseAgent
from .prompts import get_generation_prompt


@dataclass
class GenerationProgress:
    """生成进度"""
    message: str
    progress: int


@dataclass
class GenerationResult:
    """生成结果"""
    html: str
    preview_url: str
    filepath: str
    token_usage: Optional[dict] = None


class GenerationAgent(BaseAgent):
    """Generation Agent - 页面生成"""

    agent_type = "generation"

    def __init__(
        self,
        db,
        session_id: str,
        settings,
        event_emitter: Optional[EventEmitter] = None,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        token_tracker=None,
    ) -> None:
        super().__init__(
            db=db,
            session_id=session_id,
            settings=settings,
            event_emitter=event_emitter,
            agent_id=agent_id,
            task_id=task_id,
            token_tracker=token_tracker,
        )
        self._current_html = ""

    async def generate(
        self,
        *,
        requirements: str,
        output_dir: str,
        history: Optional[Sequence[dict]] = None,
        current_html: Optional[str] = None,
        stream: bool = True,
    ) -> GenerationResult:
        """
        生成移动端 HTML 页面

        Args:
            requirements: 生成需求 (从 Interview 收集的信息)
            output_dir: 输出目录
            history: 对话历史
            current_html: 当前 HTML (用于增量生成)
            stream: 是否流式输出

        Returns:
            GenerationResult: 生成结果
        """
        # 构建消息
        messages = self._build_messages(requirements, history, current_html)

        # 获取可用的 tools
        tools = get_filesystem_tools()

        # 构建 tool handlers
        tool_handlers = {
            "filesystem_write": self._write_file_handler(output_dir),
        }

        # 发射开始事件
        self._emit_agent_progress(message="开始生成页面...", progress=10)

        # 调用 LLM
        response = await self._call_llm_with_tools(
            messages=messages,
            tools=tools,
            tool_handlers=tool_handlers,
            agent_type=self.agent_type,
            context="generation",
        )

        # 提取 HTML
        html = self._extract_html(response.content)

        # 保存文件
        filepath = await self._save_html(html, output_dir)
        preview_url = Path(filepath).absolute().as_uri()

        # 发射完成事件
        self._emit_agent_progress(message="生成完成", progress=100)

        return GenerationResult(
            html=html,
            preview_url=preview_url,
            filepath=filepath,
            token_usage={
                "input_tokens": response.token_usage.input_tokens if response.token_usage else 0,
                "output_tokens": response.token_usage.output_tokens if response.token_usage else 0,
                "cost_usd": response.token_usage.cost_usd if response.token_usage else 0,
            },
        )

    async def generate_with_progress(
        self,
        *,
        requirements: str,
        output_dir: str,
        history: Optional[Sequence[dict]] = None,
        on_progress: Optional[callable] = None,
    ) -> GenerationResult:
        """
        带进度回调的生成 (用于流式输出)

        Args:
            requirements: 生成需求
            output_dir: 输出目录
            history: 对话历史
            on_progress: 进度回调 (message, progress)

        Returns:
            GenerationResult
        """
        # 构建消息
        messages = self._build_messages(requirements, history)

        # 流式调用
        messages_history = messages.copy()
        full_response = ""

        self._emit_agent_progress(message="分析需求...", progress=10)

        async for chunk in self._llm_client.chat_completion_stream(
            messages=messages_history,
            model=self.settings.model,
            temperature=self.settings.temperature,
        ):
            full_response += chunk
            if on_progress:
                progress = min(90, 10 + len(full_response) // 10)
                on_progress(f"生成中... ({len(full_response)} chars)", progress)

        # 提取 HTML
        html = self._extract_html(full_response)

        # 保存
        filepath = await self._save_html(html, output_dir)
        preview_url = Path(filepath).absolute().as_uri()

        self._emit_agent_progress(message="生成完成", progress=100)

        return GenerationResult(
            html=html,
            preview_url=preview_url,
            filepath=filepath,
        )

    def _build_messages(
        self,
        requirements: str,
        history: Optional[Sequence[dict]] = None,
        current_html: Optional[str] = None,
    ) -> List[dict]:
        """构建消息列表"""
        messages = []

        # System prompt
        messages.append({
            "role": "system",
            "content": get_generation_prompt(),
        })

        # 对话历史
        if history:
            for msg in history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        # 当前需求
        content = f"请生成一个移动端优化的 HTML 页面，满足以下需求:\n\n{requirements}"

        # 如果有当前 HTML，说明是修改
        if current_html:
            content = f"请修改以下 HTML 页面，满足新的需求:\n\n当前 HTML:\n{current_html}\n\n新需求:\n{requirements}"

        messages.append({
            "role": "user",
            "content": content,
        })

        return messages

    def _extract_html(self, content: str) -> str:
        """
        从响应中提取 HTML

        提取策略 (优先级从高到低):
        1. 特殊标记: <HTML_OUTPUT>...</HTML_OUTPUT>
        2. HTML 标记: <!DOCTYPE html>...</html>
        3. <html>...</html> 模糊匹配

        如果都找不到，返回空字符串。
        """
        if not content:
            return ""

        # 策略 1: 特殊标记 (最可靠)
        html_start = content.find("<HTML_OUTPUT>")
        if html_start != -1:
            html_end = content.find("</HTML_OUTPUT>", html_start)
            if html_end != -1:
                return content[html_start + 14:html_end].strip()

        # 策略 2: <!DOCTYPE html>
        html_start = content.find("<!DOCTYPE html>")
        if html_start != -1:
            html_end = content.rfind("</html>")
            if html_end != -1:
                return content[html_start:html_end + 7].strip()
            # 没有结束标签，返回从 DOCTYPE 开始的所有内容
            return content[html_start:].strip()

        # 策略 3: <html> 模糊匹配
        html_start = content.find("<html")
        if html_start != -1:
            # 找到 <html> 的结束符号 '>'
            tag_end = content.find(">", html_start)
            if tag_end != -1:
                html_end = content.rfind("</html>")
                if html_end != -1:
                    return content[html_start:html_end + 7].strip()

        # 找不到，返回空
        logger.warning("无法从响应中提取 HTML 内容")
        return ""

    async def _save_html(self, html: str, output_dir: str) -> str:
        """保存 HTML 文件"""
        from ..services.filesystem import FilesystemService

        fs = FilesystemService(output_dir)
        path = fs.save_html(self.session_id, html, filename="index.html")
        return str(path)

    def _write_file_handler(self, output_dir: str):
        """
        创建 filesystem_write 的 handler

        保存策略:
        - 当前预览: index.html (每次覆盖)
        - 版本历史: v{version}_{timestamp}.html
        """
        async def handler(path: str, content: str, encoding: str = "utf-8"):
            from ..services.filesystem import FilesystemService
            import time

            fs = FilesystemService(output_dir)

            # 提取文件名和版本号
            filename = Path(path).name

            # 生成版本号 (当前时间戳)
            version = int(time.time())

            # 保存为 index.html (当前预览)
            preview_path = fs.save_html(self.session_id, content, filename="index.html")

            # 同时保存版本历史
            version_filename = f"v{version}_{filename}"
            fs.save_html(self.session_id, content, filename=version_filename)

            return {
                "success": True,
                "preview_path": preview_path,
                "version_path": version_filename,
                "version": version,
            }

        return handler


__all__ = ["GenerationAgent", "GenerationProgress", "GenerationResult"]
```

### 5.5 RefinementAgent 实现

**文件**: `packages/backend/app/agents/refinement.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..events.emitter import EventEmitter
from ..llm.tools import get_filesystem_tools
from .base import BaseAgent
from .prompts import get_refinement_prompt


@dataclass
class RefinementResult:
    """修改结果"""
    html: str
    preview_url: str
    filepath: str
    token_usage: Optional[dict] = None


class RefinementAgent(BaseAgent):
    """Refinement Agent - 页面修改"""

    agent_type = "refinement"

    async def refine(
        self,
        *,
        user_input: str,
        current_html: str,
        output_dir: str,
        history: Optional[list] = None,
    ) -> RefinementResult:
        """
        根据用户反馈修改页面

        Args:
            user_input: 用户的修改描述
            current_html: 当前 HTML
            output_dir: 输出目录
            history: 对话历史

        Returns:
            RefinementResult: 修改结果
        """
        # 构建消息
        messages = self._build_messages(user_input, current_html, history)

        # 获取可用的 tools
        tools = get_filesystem_tools()

        # 构建 tool handlers
        tool_handlers = {
            "filesystem_write": self._write_file_handler(output_dir),
        }

        # 发射开始事件
        self._emit_agent_progress(message="正在修改页面...", progress=30)

        # 调用 LLM
        response = await self._call_llm_with_tools(
            messages=messages,
            tools=tools,
            tool_handlers=tool_handlers,
            agent_type=self.agent_type,
            context="refinement",
        )

        # 提取 HTML
        html = self._extract_html(response.content)

        # 发射进度
        self._emit_agent_progress(message="保存修改...", progress=80)

        # 保存文件
        filepath = await self._save_html(html, output_dir)
        preview_url = Path(filepath).absolute().as_uri()

        # 发射完成
        self._emit_agent_progress(message="修改完成", progress=100)

        return RefinementResult(
            html=html,
            preview_url=preview_url,
            filepath=filepath,
            token_usage={
                "input_tokens": response.token_usage.input_tokens if response.token_usage else 0,
                "output_tokens": response.token_usage.output_tokens if response.token_usage else 0,
                "cost_usd": response.token_usage.cost_usd if response.token_usage else 0,
            },
        )

    def _build_messages(
        self,
        user_input: str,
        current_html: str,
        history: Optional[list] = None,
    ) -> list:
        """构建消息列表"""
        messages = []

        # System prompt
        messages.append({
            "role": "system",
            "content": get_refinement_prompt(),
        })

        # 对话历史
        if history:
            for msg in history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        # 当前 HTML 和修改需求
        messages.append({
            "role": "user",
            "content": f"当前 HTML:\n{current_html}\n\n用户修改需求:\n{user_input}",
        })

        return messages

    def _extract_html(self, content: str) -> str:
        """
        从响应中提取 HTML (参考 GenerationAgent._extract_html)

        提取策略 (优先级从高到低):
        1. 特殊标记: <HTML_OUTPUT>...</HTML_OUTPUT>
        2. HTML 标记: <!DOCTYPE html>...</html>
        3. <html>...</html> 模糊匹配
        """
        if not content:
            return ""

        # 策略 1: 特殊标记
        html_start = content.find("<HTML_OUTPUT>")
        if html_start != -1:
            html_end = content.find("</HTML_OUTPUT>", html_start)
            if html_end != -1:
                return content[html_start + 14:html_end].strip()

        # 策略 2: <!DOCTYPE html>
        html_start = content.find("<!DOCTYPE html>")
        if html_start != -1:
            html_end = content.rfind("</html>")
            if html_end != -1:
                return content[html_start:html_end + 7].strip()
            return content[html_start:].strip()

        # 策略 3: <html> 模糊匹配
        html_start = content.find("<html")
        if html_start != -1:
            tag_end = content.find(">", html_start)
            if tag_end != -1:
                html_end = content.rfind("</html>")
                if html_end != -1:
                    return content[html_start:html_end + 7].strip()

        return ""

    async def _save_html(self, html: str, output_dir: str) -> str:
        """保存 HTML 文件"""
        from ..services.filesystem import FilesystemService
        import time

        fs = FilesystemService(output_dir)

        # 保存为 index.html (当前预览)
        preview_path = fs.save_html(self.session_id, html, filename="index.html")

        # 同时保存版本历史
        version = int(time.time())
        version_filename = f"v{version}_refinement.html"
        fs.save_html(self.session_id, html, filename=version_filename)

        return preview_path

    def _write_file_handler(self, output_dir: str):
        """创建 filesystem_write 的 handler (带版本历史)"""
        async def handler(path: str, content: str, encoding: str = "utf-8"):
            from ..services.filesystem import FilesystemService
            import time

            fs = FilesystemService(output_dir)
            version = int(time.time())

            # 保存预览
            preview_path = fs.save_html(self.session_id, content, filename="index.html")

            # 保存版本
            version_filename = f"v{version}_{Path(path).name}"
            fs.save_html(self.session_id, content, filename=version_filename)

            return {
                "success": True,
                "preview_path": preview_path,
                "version_path": version_filename,
                "version": version,
            }

        return handler


__all__ = ["RefinementAgent", "RefinementResult"]
```

---

## 6. Tools 系统实现

### 6.1 Tool Handlers

Tool handlers 是实际执行工具操作的函数。每个 Tool 对应一个 handler。

**实现位置**: 在各 Agent 中定义 (见上文)

**Tool Handler 签名**:
```python
async def tool_handler(**kwargs) -> Any:
    """
    执行工具操作

    Args:
        kwargs: 工具参数 (根据 Tool 定义)

    Returns:
        操作结果 (JSON 可序列化)
    """
    pass
```

### 6.2 Tool 错误处理

```python
class ToolError(Exception):
    """Tool 执行错误"""

    def __init__(self, tool_name: str, message: str, details: Optional[dict] = None) -> None:
        self.tool_name = tool_name
        self.message = message
        self.details = details
        super().__init__(f"[{tool_name}] {message}")


async def safe_call_tool(tool_name: str, handler: callable, **kwargs) -> dict:
    """
    安全调用 Tool

    Args:
        tool_name: 工具名称
        handler: handler 函数
        **kwargs: 参数

    Returns:
        {"success": bool, "output": Any, "error": str}
    """
    try:
        result = await handler(**kwargs)
        return {"success": True, "output": result, "error": None}
    except Exception as e:
        logger.exception(f"Tool 执行失败: {tool_name}")
        return {"success": False, "output": None, "error": str(e)}
```

### 6.3 Tool 执行流程

```
LLM 返回 tool_calls
    │
    ├── 解析 tool_call
    │   ├── tool_call.id
    │   ├── tool_call.function.name
    │   └── tool_call.function.arguments
    │
    ├── 发射 tool_call 事件
    │
    ├── 执行对应的 handler
    │   ├── 参数验证
    │   ├── 执行业务逻辑
    │   └── 返回结果
    │
    ├── 发射 tool_result 事件
    │
    └── 将结果添加到消息历史
        └── role: "tool"
            tool_call_id: ...
            name: ...
        content: {"success": ..., "output": ..., "error": ...}
```

### 6.4 Tool 安全边界

为避免工具被滥用，必须在 handler 层强制以下约束：
- `filesystem_*` 仅允许 `output_dir` 子路径，拒绝绝对路径与 `..` 穿越
- 限制单次写入大小与允许的文件类型（如 `.html`/`.css`/`.js`）
- 读取操作仅允许白名单目录

---

## 7. 事件集成

### 7.1 Agent 事件流

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ InterviewAgent.process()                                    │
├─────────────────────────────────────────────────────────────┤
│ 1. 发射 agent_start (agent_id: interview_1)                 │
│ 2. 调用 _call_llm()                                          │
│    ├── LLM 处理                                              │
│    ├── Token 记录                                            │
│    └── 发射 agent_progress (可选)                            │
│ 3. 发射 agent_end (status: success/failed)                  │
│ 4. 返回 AgentResult                                          │
│    └── is_complete = True → 进入 Generation                 │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Tool 事件流

```
LLM 返回 tool_calls
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ _call_llm_with_tools()                                      │
├─────────────────────────────────────────────────────────────┤
│ For each tool_call:                                         │
│    ├── 发射 tool_call                                       │
│    │   type: "tool_call"                                    │
│    │   tool_name: "filesystem_write"                        │
│    │   tool_input: {"path": "...", "content": "..."}        │
│    │                                                            │
│    ├── 执行 tool handler                                    │
│    │                                                            │
│    ├── 发射 tool_result                                     │
│    │   type: "tool_result"                                  │
│    │   success: true/false                                  │
│    │   tool_output: {"path": "..."}                         │
│    │   error: "..." (if failed)                             │
│    │                                                            │
│    └── 添加 tool 结果到消息历史                              │
│        role: "tool"                                         │
│        tool_call_id: "..."                                  │
│        content: {"success": true, "output": ...}            │
│                                                             │
│ 继续循环直到 LLM 不返回 tool_calls                           │
└─────────────────────────────────────────────────────────────┘
```

### 7.3 进度事件

```python
# Generation Agent 进度示例
self._emit_agent_progress(message="分析需求...", progress=10)
self._emit_agent_progress(message="生成页面结构...", progress=30)
self._emit_agent_progress(message="应用样式...", progress=60)
self._emit_agent_progress(message="添加交互逻辑...", progress=80)
self._emit_agent_progress(message="完成", progress=100)
```

---

## 8. Token 追踪

### 8.1 追踪流程

```
BaseAgent._call_llm()
    │
    ▼
OpenAIClient.chat_completion()
    │
    ├── 发送请求
    │
    ├── 接收响应
    │   └── response.usage.prompt_tokens
    │   └── response.usage.completion_tokens
    │
    ▼
TokenTrackerService.record_usage()
    │
    ├── 保存到数据库
    │   └── token_usage 表
    │
    └── 返回 TokenUsage 记录
```
> 注: 流式调用不一定返回 usage，必要时改用非流式统计或使用 `include_usage`。

### 8.2 Token 使用统计

```python
# 在 Agent 中记录
if response.token_usage and self.token_tracker:
    self.token_tracker.record_usage(
        session_id=self.session_id,
        agent_type=self.agent_type,  # interview / generation / refinement
        model=model,
        input_tokens=response.token_usage.input_tokens,
        output_tokens=response.token_usage.output_tokens,
        cost_usd=response.token_usage.cost_usd,
    )
```

### 8.3 成本计算

> 注: 模型价格表应配置化并定期更新，以下仅为示例估算。

```python
# OpenAIClient._calculate_cost()
PRICING = {
    "gpt-4o": {"input": 5.0, "output": 15.0},      # $5/$15 per 1M tokens
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},  # $0.15/$0.60 per 1M
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING.get(model, PRICING["gpt-4o-mini"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost
```

---

## 9. 错误处理

### 9.1 错误类型

| 错误类型 | 说明 | 处理方式 |
|---------|------|---------|
| `APIError` | LLM API 错误 | 重试 3 次，指数退避 |
| `RateLimitError` | 速率限制 | 等待后重试 |
| `ToolError` | Tool 执行错误 | 返回失败结果给 LLM |
| `ValidationError` | 参数验证错误 | 返回错误信息 |

> 建议优先使用 OpenAI SDK 的异常类型做判断，字符串匹配仅作为兜底。

### 9.2 重试机制

```python
import asyncio
from typing import TypeVar

T = TypeVar("T")

async def with_retry(
    func: callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    **kwargs,
) -> T:
    """带指数退避的重试"""
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
                logger.warning(f"尝试 {attempt + 1} 失败，等待 {delay}s 后重试")
                await asyncio.sleep(delay)
            else:
                logger.error(f"所有重试尝试均失败: {e}")
                raise

    raise last_exception
```

### 9.3 错误事件

```python
# 当 Agent 执行失败时
if self.event_emitter:
    self.event_emitter.emit(ErrorEvent(
        message=f"{self.agent_type} 执行失败",
        details=str(error),
    ))
```

---

## 10. 文件变更清单

### 10.1 新建文件

| 文件路径 | 描述 |
|---------|------|
| `packages/backend/app/llm/__init__.py` | LLM 模块入口 |
| `packages/backend/app/llm/openai_client.py` | OpenAI SDK 封装 |
| `packages/backend/app/llm/tools.py` | Tools 定义 |
| `packages/backend/app/agents/prompts.py` | Agent System Prompts |

### 10.2 修改文件

| 文件路径 | 变更内容 |
|---------|---------|
| `packages/backend/app/agents/base.py` | 添加 `_call_llm()`, `_call_llm_with_tools()`, 事件发射方法 |
| `packages/backend/app/agents/interview.py` | 实现 `process()` 真实 LLM 调用 |
| `packages/backend/app/agents/generation.py` | 实现 `generate()` 真实 LLM 调用 + 流式输出 |
| `packages/backend/app/agents/refinement.py` | 实现 `refine()` 真实 LLM 调用 |

### 10.3 依赖更新

```bash
# requirements.txt / pyproject.toml (二选一)
openai>=1.12.0
```

---

## 11. 验收标准

### 11.1 功能验收

- [ ] Interview Agent 能够根据用户输入智能提问
- [ ] Generation Agent 能够生成符合移动端标准的 HTML
- [ ] Refinement Agent 能够根据反馈修改页面
- [ ] Tool 调用正常工作 (filesystem_write, filesystem_read)
- [ ] Token 使用量正确记录到数据库
- [ ] 事件正确发射到前端

### 11.2 质量验收

- [ ] 所有 LLM 调用支持重试机制
- [ ] 流式输出正常工作
- [ ] 错误信息友好
- [ ] HTML 输出符合移动端规范
- [ ] 代码类型提示完整
- [ ] filesystem 工具仅允许 output_dir 子路径
- [ ] 前端默认阶段展示，必要时可切换实时

### 11.3 性能验收

- [ ] Interview 响应 < 5s
- [ ] Generation 响应 < 60s
- [ ] Refinement 响应 < 15s
- [ ] 并发调用正常工作

---

**文档版本**: v0.3
**最后更新**: 2026-01-31
**状态**: 待实现

---

## 附录 A: 完整示例

### A.1 InterviewAgent 使用示例

```python
from app.agents.interview import InterviewAgent
from app.db.database import get_db
from app.config import get_settings

# 初始化
db = next(get_db())
settings = get_settings()

agent = InterviewAgent(
    db=db,
    session_id="session_123",
    settings=settings,
    event_emitter=event_emitter,
)

# 处理用户输入
result = await agent.process(
    user_message="帮我做一个作品集页面",
    history=[],
)

print(result.message)  # 展示给用户的问题
print(result.is_complete)  # 是否可以开始生成
print(result.context)  # 收集到的信息 (JSON)
```

### A.2 GenerationAgent 使用示例

```python
from app.agents.generation import GenerationAgent

agent = GenerationAgent(
    db=db,
    session_id="session_123",
    settings=settings,
    event_emitter=event_emitter,
)

# 生成页面
result = await agent.generate(
    requirements="""
    页面类型: 作品集
    作品数量: 20
    风格: 简约现代
    """,
    output_dir="~/instant-coffee-output",
)

print(result.html)  # 生成的 HTML
print(result.preview_url)  # 预览 URL
print(result.filepath)  # 文件路径
```

### A.3 RefinementAgent 使用示例

```python
from app.agents.refinement import RefinementAgent

agent = RefinementAgent(
    db=db,
    session_id="session_123",
    settings=settings,
    event_emitter=event_emitter,
)

# 修改页面
result = await agent.refine(
    user_input="把标题改成红色，字体变大",
    current_html="<html>...</html>",
    output_dir="~/instant-coffee-output",
)

print(result.html)  # 修改后的 HTML
print(result.preview_url)  # 预览 URL
```

---

## 附录 B: 事件序列图

### B.1 完整对话流程

```
┌──────┐    ┌─────────────┐    ┌──────────────────┐    ┌───────┐
│ User │    │ Chat API    │    │ InterviewAgent   │    │ LLM   │
└──┬───┘    └──────┬──────┘    └────────┬─────────┘    └───┬───┘
   │               │                     │                   │
   │ chat()        │                     │                   │
   │──────────────>│                     │                   │
   │               │ process()            │                   │
   │               │─────────────────────>│                   │
   │               │                     │ chat_completion() │
   │               │                     │──────────────────>│
   │               │                     │                   │
   │               │                     │   agent_start     │
   │               │                     │<──────────────────┤
   │               │                     │                   │
   │               │                     │   agent_progress  │
   │               │                     │<──────────────────┤
   │               │                     │                   │
   │               │                     │   agent_end       │
   │               │                     │<──────────────────┤
   │               │                     │                   │
   │               │    AgentResult      │                   │
   │               │<────────────────────│                   │
   │               │                     │                   │
   │  显示问题     │                     │                   │
   │<──────────────│                     │                   │
   │               │                     │                   │
   │ 用户回答      │                     │                   │
   │──────────────>│                     │                   │
   │               │ process()            │                   │
   │               │─────────────────────>│                   │
   │               │                     │                   │
   │               │                     │      ... (重复)   │
   │               │                     │                   │
   │               │    AgentResult      │                   │
   │               │ (is_complete=True)  │                   │
   │               │<────────────────────│                   │
   │               │                     │                   │
   │               │ generate()          │                   │
   │               │─────────────────────>│                   │
   │               │                     │                   │
   │               │                     │ chat_completion() │
   │               │                     │   + tools         │
   │               │                     │──────────────────>│
   │               │                     │                   │
   │               │                     │   tool_call       │
   │               │                     │   filesystem_write│
   │               │                     │<──────────────────┤
   │               │                     │                   │
   │               │                     │   tool_result     │
   │               │                     │   success         │
   │               │                     │<──────────────────┤
   │               │                     │                   │
   │               │                     │   agent_end       │
   │               │                     │<──────────────────┤
   │               │                     │                   │
   │               │    GenerationResult │                   │
   │               │<────────────────────│                   │
   │               │                     │                   │
   │  显示 HTML    │                     │                   │
   │<──────────────│                     │                   │
```

---

## 附录 C: 环境变量配置

```bash
# .env

# OpenAI 配置 (必需)
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1

# 模型配置
MODEL=gpt-4o-mini
TEMPERATURE=0.7
MAX_TOKENS=4096  # 示例值，可根据模型调整

# 其他配置
DATABASE_URL=sqlite:///./instant-coffee.db
OUTPUT_DIR=~/instant-coffee-output
```

---

## 附录 D: 常见问题

### Q1: 如何切换到其他 LLM 提供商？

目前使用 OpenAI SDK，可以通过修改 `OpenAIClient` 类支持其他提供商。Anthropic SDK 有不同的接口，需要额外适配。

### Q2: 如何添加新的 Tool？

1. 在 `tools.py` 中定义 Tool schema
2. 创建对应的 handler 函数
3. 在 Agent 的 `tool_handlers` 中注册

### Q3: Token 消耗太高怎么办？

1. 减少对话历史长度
2. 使用更小的模型 (gpt-4o-mini)
3. 减少 max_tokens
4. 优化 System Prompt

### Q4: 如何调试 Agent 行为？

1. 启用详细日志
2. 查看 `_call_llm` 发送的完整消息
3. 检查 LLM 返回的原始响应
