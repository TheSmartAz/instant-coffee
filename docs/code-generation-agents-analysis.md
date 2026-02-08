# AI 代码生成工具深度分析报告

> 基于 easy-coding-agents 和 nanocode 两个开源项目的深入研究
>
> 分析日期: 2025-02-06

---

## 目录

1. [项目概览对比](#一项目概览对比)
2. [easy-coding-agents 完整分析](#二easy-coding-agents-完整分析)
3. [nanocode 完整分析](#三nanocode-完整分析)
4. [代码生成与修改机制对比](#四代码生成与修改机制对比)
5. [上下文管理策略深度分析](#五上下文管理策略深度分析)
6. [对 instant-coffee 的实施建议](#六对-instant-coffee-的实施建议)

---

## 一、项目概览对比

| 特性 | easy-coding-agents | nanocode |
|------|-------------------|----------|
| **仓库** | [yushui2022/easy-coding-agents](https://github.com/yushui2022/easy-coding-agents) | [1rgs/nanocode](https://github.com/1rgs/nanocode) |
| **定位** | 企业级自主 AI 编程助手 | 极简 Claude Code 替代品 |
| **代码规模** | 多模块架构 (~2000+ 行) | 单文件实现 (~250 行) |
| **文件数量** | 15+ Python 文件 | 1 个 Python 文件 |
| **依赖** | zhipuai, aiofiles, rich, asyncio, prompt-toolkit | 零外部依赖 (仅标准库) |
| **LLM** | 智谱 AI (GLM-4) | Claude / OpenRouter |
| **核心创新** | Task-Driven 自主循环 + 三层记忆 | 极简主义 + 自举构建 |
| **UI** | Rich 终端美化 | ANSI 简单输出 |
| **适用场景** | 复杂多步骤编程任务 | 快速代码编辑 |

### 设计哲学对比

**easy-coding-agents**: 企业级工程化
- 完整的三层记忆架构
- 任务驱动的自主执行
- 高性能异步引擎
- 丰富的 UI 交互

**nanocode**: 极简主义
- 250 行代码实现核心功能
- 零依赖但功能完整
- 自举构建验证设计
- 清晰的递归终止条件

---

## 二、easy-coding-agents 完整分析

### 2.1 项目目录结构

```
easy-coding-agents/
├── main.py                          # 入口文件
├── core/
│   ├── engine.py                    # 核心引擎 (n0 主循环)
│   ├── task.py                      # 任务管理系统
│   ├── stream.py                    # wu 流式处理器
│   ├── prompts.py                   # 系统提示
│   └── config.py                    # 配置管理
├── memory/
│   ├── __init__.py                  # MemoryManager (Facade)
│   ├── short_term.py                # 短期记忆 (Buffer)
│   ├── medium_term.py               # 中期记忆 (AU2 压缩)
│   ├── long_term.py                 # 长期记忆 (CLAUDE.md)
│   ├── session_store.py             # 会话持久化
│   └── sessions/                    # 历史会话 JSON 文件
├── tools/
│   ├── base.py                      # 工具注册表
│   ├── filesystem.py                # 文件操作工具
│   ├── shell.py                     # Shell 命令工具
│   ├── search.py                    # 搜索工具
│   └── todo.py                      # 任务管理工具
├── utils/
│   └── logger.py                    # 日志系统
├── workspace/                       # 默认输出目录
├── requirements.txt
├── .env.example
└── AI_CODER_GUIDE.md
```

### 2.2 核心架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     AgentEngine (核心引擎)                    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │ Short-Term  │ ←→ │ Medium-Term │ ←→ │  Long-Term  │      │
│  │   Memory    │    │  (AU2 压缩) │    │ (Archivist) │      │
│  │             │    │             │    │             │      │
│  │ 活跃上下文  │    │ 8维压缩摘要 │    │ CLAUDE.md   │      │
│  │ Token监控   │    │             │    │             │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
├─────────────────────────────────────────────────────────────┤
│                   TaskManager (任务清单)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ pending  │→ │in_progress│→ │completed │  │ skipped  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
├─────────────────────────────────────────────────────────────┤
│                   ToolRegistry (工具注册表)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │read/write│ │glob/grep │ │  bash    │ │   todo   │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 核心文件完整代码

#### 2.3.1 main.py - 程序入口

```python
import asyncio
import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from core.engine import AgentEngine
from utils.logger import logger, console
from core.config import Config

async def interactive_loop(engine: AgentEngine):
    session = PromptSession()
    console.print("[bold green]Easy-Coding-Agent[/bold green] initialized.")
    console.print(f"Model: [cyan]{Config.MODEL_NAME}[/cyan] | API: [cyan]ZhipuAI[/cyan]")
    console.print("Type '/exit' to quit.\n")

    while engine.running:
        try:
            with patch_stdout(raw=True):
                user_input = await session.prompt_async("❯ ")
            if not user_input.strip():
                continue
            if user_input.strip().lower() == '/exit':
                engine.stop()
                break
            await engine.push_event("user_input", user_input)
            # 等待处理完成
            await engine.processing_queue.join()
        except (EOFError, KeyboardInterrupt):
            await engine.push_event("stop", None)
            break

async def main():
    Config.validate()
    engine = AgentEngine()
    engine_task = asyncio.create_task(engine.start())
    try:
        await interactive_loop(engine)
    finally:
        engine.stop()
        if not engine_task.done():
            engine_task.cancel()
            try:
                await engine_task
            except asyncio.CancelledError:
                pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

**关键设计点**:
- `prompt_toolkit.PromptSession` 提供交互式命令行
- `patch_stdout(raw=True)` 确保日志不打断用户输入
- `processing_queue.join()` 确保任务完成后再显示新提示符

#### 2.3.2 core/engine.py - 核心引擎 (h2A 双缓冲架构)

```python
import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from utils.logger import logger, console
from core.stream import StreamHandler
from memory import MemoryManager
from core.prompts import get_system_prompt
from core.task import TaskManager
from tools.base import registry
from rich.panel import Panel
from rich.syntax import Syntax

import tools.filesystem
import tools.search
import tools.shell
import tools.todo

@dataclass
class Event:
    type: str  # 'user_input', 'stop'
    content: Any
    metadata: Dict = field(default_factory=dict)

class AgentEngine:
    """
    核心执行框架 (n0) with Double-Buffered Async Message Queue (h2A).

    h2A = h (Double-Buffered) + 2 (Two Queues) + A (Async)
    """
    def __init__(self):
        # h2A: Double Buffering
        self.input_queue = asyncio.Queue()      # Buffer 1: External Inputs
        self.processing_queue = asyncio.Queue() # Buffer 2: Internal Tasks
        self.running = True

        # Initialize components
        self.stream_handler = StreamHandler()
        self.memory = MemoryManager(self.stream_handler)
        self.task_manager = TaskManager()
        tools.todo.set_global_task_manager(self.task_manager)

        self.tools_schema = registry.get_schema()

    async def start(self):
        """启动 n0 主循环"""
        logger.info("Starting Agent Engine...")
        long_term_data = await self.memory.initialize()
        full_system_prompt = get_system_prompt()
        if long_term_data:
            full_system_prompt += f"\n\n=== LONG TERM MEMORY (EXPERIENCE) ===\n{long_term_data}"
        self.memory.set_system_prompt(full_system_prompt)

        try:
            await asyncio.gather(
                self.input_consumer(),
                self.task_consumer()
            )
        except asyncio.CancelledError:
            logger.info("Engine stopped.")

    async def input_consumer(self):
        """Buffer 1 消费者: 接收原始事件"""
        while self.running:
            try:
                event = await self.input_queue.get()
                await self.processing_queue.put(event)
                self.input_queue.task_done()
            except Exception as e:
                logger.error(f"Error in input_consumer: {e}")

    async def task_consumer(self):
        """Buffer 2 消费者: 执行逻辑"""
        while self.running:
            try:
                event = await self.processing_queue.get()
                if event.type == "user_input":
                    await self.handle_user_input(event.content)
                elif event.type == "stop":
                    self.running = False
                    self.processing_queue.task_done()
                    return
                self.processing_queue.task_done()
            except Exception as e:
                logger.error(f"Error in task_consumer: {e}")

    async def handle_user_input(self, content: str):
        self.memory.add("user", content)
        await self._run_autonomous_loop()

    async def _run_autonomous_loop(self):
        """
        核心控制回路 (n0): Task-Driven 自主执行

        这是整个系统的大脑，负责:
        1. 自动规划任务
        2. 循环执行直到完成
        3. 状态驱动的系统提示
        """
        max_turns = 30
        turn_count = 0
        start_time = time.time()

        while turn_count < max_turns:
            turn_count += 1

            # 显示耗时
            elapsed = time.time() - start_time
            if elapsed > 2.0:
                mins, secs = divmod(int(elapsed), 60)
                time_str = f"{mins}分{secs}秒" if mins > 0 else f"{secs}秒"
                console.print(f"[dim]生成中... (已耗时: {time_str})[/dim]", end="\r")

            # 1. 构建上下文 (自动触发 AU2 压缩)
            messages = await self.memory.get_context()

            # 2. 注入系统状态
            state_prompt = ""
            if not self.task_manager.tasks:
                state_prompt = "Status: Idle. Waiting for user input or task planning."
            elif self.task_manager.has_unfinished_tasks():
                next_task = self.task_manager.get_next_pending()
                status_str = "Working" if next_task.status == "in_progress" else "Pending"
                state_prompt = f"Status: {status_str}.\n{self.task_manager.render()}\n\nNEXT ACTION REQUIRED: Continue working on Task {next_task.id}: '{next_task.content}'. Use available tools to make progress."
            else:
                state_prompt = f"Status: All tasks completed.\n{self.task_manager.render()}\n\nNEXT ACTION REQUIRED: Summarize results and ask user for next steps."

            current_messages = messages + [{"role": "system", "content": f"\n{state_prompt}\n"}]

            # 3. 调用 LLM
            try:
                response_gen = self.stream_handler.chat(current_messages, self.tools_schema)
                full_content, tool_calls = await self.stream_handler.render_stream(response_gen)
            except Exception as e:
                console.print(f"[red]LLM 错误: {e}[/red]")
                break

            # 4. 更新记忆
            self.memory.add("assistant", full_content, tool_calls=tool_calls if tool_calls else None)

            # 5. 检查终止条件
            if not tool_calls:
                if self.task_manager.has_unfinished_tasks():
                    console.print("[dim]自动继续: 任务尚未完成...[/dim]")
                    continue
                else:
                    break

            # 6. 执行工具
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                args_str = tc["function"]["arguments"]
                call_id = tc["id"]

                # 美化工具调用日志
                try:
                    args = json.loads(args_str)
                    # 格式化显示
                    args_pretty = json.dumps(args, ensure_ascii=False, indent=2)
                    console.print(Panel(
                        Syntax(args_pretty, "json", theme="monokai", word_wrap=True),
                        title=f"[bold cyan]🛠️ 正在执行: {func_name}[/bold cyan]",
                        border_style="cyan",
                        expand=False
                    ))
                except json.JSONDecodeError:
                    args = {}

                try:
                    result = await registry.execute(func_name, args)
                except Exception as e:
                    result = f"Error executing tool: {str(e)}"

                snippet = result[:200] + "..." if len(result) > 200 else result
                console.print(f"[dim]执行结果: {snippet}[/dim]")
                console.print()

                # 7. 添加工具结果到记忆
                self.memory.add("tool", result, tool_call_id=call_id, name=func_name)

            # 自动保存
            await self.memory.auto_save()

    async def push_event(self, type: str, content: Any, metadata: Dict = None):
        event = Event(type=type, content=content, metadata=metadata or {})
        await self.input_queue.put(event)

    def stop(self):
        self.running = False
```

**h2A 双缓冲架构**:

```
用户输入
    ↓
input_queue (Buffer 1) ← 原始事件缓冲
    ↓
processing_queue (Buffer 2) ← 处理任务缓冲
    ↓
task_consumer
    ↓
_run_autonomous_loop
```

**状态注入机制**:

```python
# 根据任务状态动态修改 System Prompt
if not self.task_manager.tasks:
    state_prompt = "Status: Idle. Parse input into tasks."
elif self.task_manager.has_unfinished_tasks():
    next_task = self.task_manager.get_next_pending()
    state_prompt = f"Status: Working. Continue Task {next_task.id}..."
else:
    state_prompt = "Status: All done. Summarize and wait."
```

#### 2.3.3 core/task.py - 任务管理系统

```python
from dataclasses import dataclass
from typing import List, Optional
from utils.logger import console

@dataclass
class Task:
    id: str
    content: str
    status: str = "pending"  # pending, in_progress, completed, skipped

class TaskManager:
    """管理动态待办事项列表，保持 Agent 正轨"""

    def __init__(self):
        self.tasks: List[Task] = []

    def add_task(self, content: str) -> str:
        """添加新任务并返回 ID"""
        task_id = str(len(self.tasks) + 1)
        task = Task(id=task_id, content=content)
        self.tasks.append(task)
        return task_id

    def update_task(self, task_id: str, status: str) -> bool:
        """更新任务状态"""
        for task in self.tasks:
            if task.id == task_id:
                task.status = status
                return True
        return False

    def get_next_pending(self) -> Optional[Task]:
        """获取下一个待处理任务 (优先 in_progress)"""
        # 优先检查 in_progress
        for task in self.tasks:
            if task.status == "in_progress":
                return task
        # 然后检查 pending
        for task in self.tasks:
            if task.status == "pending":
                return task
        return None

    def has_unfinished_tasks(self) -> bool:
        """检查 pending 或 in_progress 任务"""
        return any(t.status in ["pending", "in_progress"] for t in self.tasks)

    def render(self) -> str:
        """返回待办列表的字符串表示（用于 LLM 上下文）"""
        if not self.tasks:
            return "(No active todo list)"
        lines = ["Current Todo List:"]
        for task in self.tasks:
            icon = " "
            if task.status == "completed":
                icon = "[x]"
            elif task.status == "in_progress":
                icon = "[->]"
            elif task.status == "skipped":
                icon = "[-]"
            else:
                icon = "[ ]"
            lines.append(f"{task.id}. {icon} {task.content}")
        return "\n".join(lines)

    def print_summary(self):
        """打印美化摘要到控制台"""
        if not self.tasks:
            return
        console.print("\n[bold underline]Todo List Status:[/bold underline]")
        for task in self.tasks:
            if task.status == "completed":
                style = "green strike"
                icon = "✔"
            elif task.status == "in_progress":
                style = "yellow bold"
                icon = "➜"
            elif task.status == "skipped":
                style = "dim"
                icon = "-"
            else:
                style = "white"
                icon = "○"
            console.print(f"[{style}] {task.id}. {icon} {task.content}[/{style}]")
        console.print()
```

**状态机**:

```
        ┌─────────┐
        │ pending │
        └────┬────┘
             │
             ▼
      ┌──────────────┐
      │ in_progress  │
      └──────┬───────┘
             │
      ┌──────┴──────┐
      ▼             ▼
 ┌─────────┐  ┌─────────┐
 │completed│  │ skipped │
 └─────────┘  └─────────┘
```

#### 2.3.4 core/stream.py - wu 流式处理器

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from zhipuai import ZhipuAI
from core.config import Config
from utils.logger import logger

class StreamHandler:
    """
    处理 LLM 实时流式响应

    wu = (W)rapper + (u)nified streaming
    """
    def __init__(self):
        if not Config.ZHIPU_API_KEY:
            logger.warning("ZHIPU_API_KEY not set. API calls will fail.")
            self.client = None
        else:
            self.client = ZhipuAI(api_key=Config.ZHIPU_API_KEY)
        self.executor = ThreadPoolExecutor(max_workers=1)

    async def chat(self, messages, tools):
        """ZhipuAI 同步流的异步包装"""
        if not self.client:
            raise ValueError("API Key missing")
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()

        def _producer():
            """在独立线程中运行，将同步 API 转为异步"""
            try:
                response = self.client.chat.completions.create(
                    model=Config.MODEL_NAME,
                    messages=messages,
                    tools=tools,
                    stream=True,
                    do_sample=True,
                    temperature=0.1
                )
                for chunk in response:
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
                loop.call_soon_threadsafe(queue.put_nowait, None)  # Sentinel
            except Exception as e:
                logger.error(f"Stream error: {e}")
                loop.call_soon_threadsafe(queue.put_nowait, None)

        # 在线程中启动生产者
        loop.run_in_executor(self.executor, _producer)

        # 从队列消费 (生成器模式)
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    async def render_stream(self, stream_generator):
        """渲染流到控制台并聚合完整响应"""
        full_content = ""
        tool_calls = []

        console.print(f"\n[bold cyan]AI[/bold cyan] ", end="")

        async for chunk in stream_generator:
            delta = chunk.choices[0].delta

            # 处理文本
            if delta.content:
                content_chunk = delta.content
                print(content_chunk, end="", flush=True)  # 打字机效果
                full_content += content_chunk

            # 处理工具调用
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    index = tc.index
                    if index is not None:
                        while len(tool_calls) <= index:
                            tool_calls.append({
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""}
                            })
                        if tc.id:
                            tool_calls[index]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls[index]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls[index]["function"]["arguments"] += tc.function.arguments

        print()  # Newline
        return full_content, tool_calls
```

**流式处理架构**:

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│ ZhipuAI Stream  │────▶│ ThreadPool   │────▶│ Async Queue │
│ (同步 API)      │     │ _producer    │     │             │
└─────────────────┘     └──────────────┘     └──────┬──────┘
                                                     │
                                                     ▼
                                            ┌──────────────┐
                                            │ Main Loop    │
                                            │ async for    │
                                            └──────────────┘
```

#### 2.3.5 core/prompts.py - 系统提示

```python
import os
import platform

def get_system_prompt():
    cwd = os.getcwd()
    os_name = platform.system()
    return f"""You are an advanced AI coding assistant powered by ZhipuAI.
Your architecture includes a double-buffered async message queue (h2A) and streaming output (wu).

CORE DIRECTIVES:
1. **Task-Driven Execution (MANDATORY)**: You are a TASK-DRIVEN autonomous agent.
   - Your PRIMARY OBJECTIVE is to clear your Todo List.
   - **User input is just the trigger to create initial tasks.**
   - Once tasks are created, you MUST loop autonomously until all tasks are marked `completed`.
   - **DO NOT STOP** to ask for confirmation unless blocked.
   - **ALWAYS** check your Todo List status at each turn.

2. **State Transition Rules**:
   - Empty Todo List: Parse input → Call `todo_add` → Start executing
   - Tasks exist: Pick `pending` → Mark `in_progress` → Execute → Mark `completed`
   - All done: Summarize → Wait for new input

3. **Understand First**: Use `glob`, `grep`, or `read` before coding.

4. **Workspace Discipline**:
   - New files go to `workspace/` directory
   - Example: `workspace/snake.py`, `workspace/index.html`

5. **Tools**: `edit` for small changes, `write` for new files, `bash` for commands.

6. **Conciseness**: Be concise. Focus on code.

ENVIRONMENT:
- CWD: {cwd}
- OS: {os_name}
"""
```

### 2.4 三层记忆系统

#### 2.4.1 memory/short_term.py - 短期记忆

```python
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from core.config import Config
from utils.logger import logger

@dataclass
class MemoryOverflowError(Exception):
    """信号: 短期记忆已超过容量"""
    current_tokens: int
    limit: int

class ShortTermMemory:
    """
    第一层: 短期记忆
    管理内存中的"活数据"，直接参与每一轮对话
    """
    def __init__(self):
        self.active_context: List[Dict[str, Any]] = []
        self.system_prompt: Optional[Dict[str, Any]] = None
        self.token_limit = Config.MAX_HISTORY_TOKENS

    def set_system_prompt(self, content: str):
        self.system_prompt = {"role": "system", "content": content}

    def add(self, role: str, content: Any, tool_calls: List = None,
            tool_call_id: str = None, name: str = None):
        msg = {"role": role, "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if tool_call_id:
            msg["tool_call_id"] = tool_call_id
        if name:
            msg["name"] = name
        self.active_context.append(msg)
        self._check_overflow()

    def get_context(self) -> List[Dict[str, Any]]:
        """返回系统提示 + 活跃上下文"""
        context = []
        if self.system_prompt:
            context.append(self.system_prompt)
        context.extend(self.active_context)
        return context

    def _estimate_tokens(self) -> int:
        """估算当前 token 使用量: 字符数 / 3"""
        text = "".join(str(m.get("content", "")) for m in self.active_context)
        if self.system_prompt:
            text += str(self.system_prompt.get("content", ""))
        return int(len(text) / 3)

    def _check_overflow(self):
        """监控 token 使用，超过 92% 时抛出信号"""
        current = self._estimate_tokens()
        threshold = self.token_limit * 0.92
        if current > threshold:
            logger.warning(f"Memory Overflow: {current}/{self.token_limit}")
            raise MemoryOverflowError(current, self.token_limit)

    def replace_context(self, new_context: List[Dict[str, Any]]):
        """压缩器用于替换旧上下文"""
        self.active_context = new_context
```

#### 2.4.2 memory/medium_term.py - AU2 压缩算法

```python
import asyncio
import json
from typing import List, Dict, Any, Optional
from utils.logger import logger
from core.stream import StreamHandler

class MediumTermMemory:
    """
    第二层: 中期记忆
    负责对话的"脱水快照"和 AU2 压缩

    AU2 = Agentic Understanding & Unification
    """
    def __init__(self, stream_handler: StreamHandler):
        self.stream_handler = stream_handler
        self.is_compressing = False

    async def compress(self, full_context: List[Dict[str, Any]]) -> tuple:
        """
        执行 AU2 压缩算法

        切片策略:
        - System 消息: 全部保留
        - 前 2 条: 保留 (对话开场)
        - 后 4 条: 保留 (最近上下文)
        - 中间部分: 压缩成 8 维摘要
        """
        if self.is_compressing or len(full_context) < 10:
            return full_context, None

        self.is_compressing = True
        logger.info("Starting AU2 Context Compression...")
        au2_data = None

        try:
            # 1. 分离消息
            system_msgs = [m for m in full_context if m['role'] == 'system']
            dialogue = [m for m in full_context if m['role'] != 'system']

            if len(dialogue) < 10:
                return full_context, None

            # 2. 切片
            intro = dialogue[:2]      # 开头保留
            recent = dialogue[-4:]    # 最近保留
            middle = dialogue[2:-4]   # 中间需要压缩
            middle_text = json.dumps(middle, ensure_ascii=False, indent=1)

            # 3. AU2 Prompt 生成
            prompt = f"""
You are a Memory Compressor (AU2 Algorithm).
Compress the following conversation history into a structured 8-dimensional summary.

Input JSON:
{middle_text}

Output Format (Strict JSON):
{{
  "background": "Context of the task",
  "decisions": "Key technical decisions made",
  "tools": "Tools used and their outcomes",
  "intent": "User's core intent evolution",
  "results": "What has been achieved so far",
  "errors": "Errors encountered and fixes",
  "legacy_issues": "Unresolved problems",
  "next_steps": "Planned next actions"
}}
"""
            # 4. 调用 LLM 压缩
            compress_msgs = [{"role": "user", "content": prompt}]
            response_gen = self.stream_handler.chat(compress_msgs, tools=None)
            compressed_json_str, _ = await self.stream_handler.render_stream(response_gen)

            # 5. 解析和格式化
            summary_text = ""
            try:
                clean_json = compressed_json_str.replace("```json", "").replace("```", "").strip()
                au2_data = json.loads(clean_json)
                summary_text = (
                    f"--- AU2 COMPRESSED MEMORY ---\n"
                    f"Background: {au2_data.get('background')}\n"
                    f"Decisions: {au2_data.get('decisions')}\n"
                    f"Intent: {au2_data.get('intent')}\n"
                    f"Results: {au2_data.get('results')}\n"
                    f"Legacy Issues: {au2_data.get('legacy_issues')}\n"
                    f"-----------------------------"
                )
            except json.JSONDecodeError:
                summary_text = f"--- COMPRESSED SUMMARY ---\n{compressed_json_str}"
                au2_data = {"raw_summary": compressed_json_str}

            # 6. 重构上下文
            new_context = system_msgs + intro + [{"role": "system", "content": summary_text}] + recent
            logger.info("AU2 Compression Completed.")
            return new_context, au2_data

        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return full_context, None
        finally:
            self.is_compressing = False
```

**AU2 八维压缩示意图**:

```
原始对话 (20 条消息)
├─ System (1 条)
├─ 前 2 条 (保留)
├─ 中间 13 条 ──压缩──▶ 8 维摘要
└─ 后 4 条 (保留)

8 维摘要 = {
    background: "任务背景",
    decisions: "技术决策",
    tools: "使用的工具",
    intent: "用户意图",
    results: "已完成工作",
    errors: "错误和修复",
    legacy_issues: "未解决问题",
    next_steps: "下一步计划"
}
```

#### 2.4.3 memory/long_term.py - 长期记忆

```python
import os
import aiofiles
import asyncio
from utils.logger import logger

class LongTermMemory:
    """
    第三层: 长期记忆
    管理跨越程序生命周期的"经验书" (CLAUDE.md)
    """
    def __init__(self, file_path="CLAUDE.md"):
        self.file_path = file_path
        self._lock = asyncio.Lock()  # 原子写锁

    async def load(self) -> str:
        """启动时加载长期记忆"""
        if not os.path.exists(self.file_path):
            return ""
        try:
            async with aiofiles.open(self.file_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
            logger.info(f"Loaded Long-Term Memory from {self.file_path}")
            return content
        except Exception as e:
            logger.error(f"Failed to load long-term memory: {e}")
            return ""

    async def update(self, key_decisions: str, preferences: str = None):
        """
        追加新见解到记忆文件
        原子操作防止损坏
        """
        async with self._lock:
            try:
                entry = f"\n\n## Update\n"
                if preferences:
                    entry += f"### User Preferences\n{preferences}\n"
                if key_decisions:
                    entry += f"### Key Decisions / Legacy Issues\n{key_decisions}\n"
                async with aiofiles.open(self.file_path, mode='a', encoding='utf-8') as f:
                    await f.write(entry)
                logger.info("Long-Term Memory updated.")
            except Exception as e:
                logger.error(f"Failed to write long-term memory: {e}")
```

#### 2.4.4 memory/session_store.py - 会话持久化

```python
import json
import os
import glob
from typing import Dict, Any, List, Optional
from datetime import datetime
import aiofiles
from utils.logger import logger

class SessionStore:
    """
    处理短期和中期记忆的 JSON 序列化
    路径: memory/sessions/session_{timestamp}.json
    """
    def __init__(self, session_dir="memory/sessions"):
        self.session_dir = session_dir
        self.current_session_file = None
        self._ensure_dir()

    def _ensure_dir(self):
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir)

    def create_new_session(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_session_file = os.path.join(self.session_dir, f"session_{timestamp}.json")
        logger.info(f"New session created: {self.current_session_file}")

    def get_latest_session(self) -> Optional[str]:
        """查找最新的会话文件"""
        files = glob.glob(os.path.join(self.session_dir, "session_*.json"))
        if not files:
            return None
        return max(files, key=os.path.getctime)

    async def save(self, messages: List[Dict], au2_summary: Optional[Dict] = None):
        """
        自动保存: 持久化当前状态到 JSON
        格式: {timestamp, au2_summary, messages}
        """
        if not self.current_session_file:
            self.create_new_session()

        data = {
            "timestamp": datetime.now().isoformat(),
            "au2_summary": au2_summary,
            "messages": messages
        }

        try:
            async with aiofiles.open(self.current_session_file, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Failed to auto-save session: {e}")

    async def load(self, file_path: str) -> Dict[str, Any]:
        """从文件加载会话数据"""
        try:
            async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to load session {file_path}: {e}")
            return {}
```

#### 2.4.5 memory/__init__.py - MemoryManager (Facade)

```python
from typing import List, Dict, Any, Optional
from utils.logger import logger
from core.stream import StreamHandler

from memory.short_term import ShortTermMemory, MemoryOverflowError
from memory.medium_term import MediumTermMemory
from memory.long_term import LongTermMemory
from memory.session_store import SessionStore

class MemoryManager:
    """
    三层记忆架构的门面
    协调短期、中期和长期记忆
    """
    def __init__(self, stream_handler: StreamHandler):
        self.short_term = ShortTermMemory()
        self.medium_term = MediumTermMemory(stream_handler)
        self.long_term = LongTermMemory()
        self.session_store = SessionStore()
        self.current_au2_summary = None

    async def initialize(self):
        """启动时加载长期记忆和最新会话"""
        long_term_content = await self.long_term.load()

        latest_session = self.session_store.get_latest_session()
        if latest_session:
            logger.info(f"Found previous session: {latest_session}")
            data = await self.session_store.load(latest_session)
            if data:
                self.short_term.active_context = data.get("messages", [])
                self.current_au2_summary = data.get("au2_summary")
                logger.info("Session resumed successfully.")

        return long_term_content

    def set_system_prompt(self, content: str):
        self.short_term.set_system_prompt(content)

    def add(self, role: str, content: Any, **kwargs):
        """主入口: 添加到短期记忆 -> 检查溢出"""
        try:
            self.short_term.add(role, content, **kwargs)
        except MemoryOverflowError:
            pass  # 压缩将在 get_context 时触发

    async def auto_save(self):
        """持久化当前会话"""
        await self.session_store.save(
            self.short_term.active_context,
            self.current_au2_summary
        )

    async def get_context(self) -> List[Dict[str, Any]]:
        """
        获取 LLM 上下文
        在返回前检查溢出并在需要时运行压缩
        """
        try:
            self.short_term._check_overflow()
        except MemoryOverflowError:
            logger.warning("Memory overflow confirmed. Executing AU2 compression...")
            full_context = self.short_term.get_context()

            # 执行 AU2
            new_context, au2_data = await self.medium_term.compress(full_context)

            # 更新短期记忆
            self.short_term.replace_context(new_context)

            # 更新中期记忆缓存
            if au2_data:
                self.current_au2_summary = au2_data

            # 压缩后立即自动保存
            await self.auto_save()

        return self.short_term.get_context()
```

### 2.5 工具系统

#### 2.5.1 tools/base.py - 工具注册表

```python
from typing import Dict, Any, Callable, List
from dataclasses import dataclass
import inspect

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, parameters: Dict[str, Any]):
        """装饰器工厂: 返回装饰器函数"""
        def decorator(func):
            self.tools[name] = ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                func=func
            )
            return func
        return decorator

    def get_schema(self) -> List[Dict[str, Any]]:
        """生成 OpenAI/ZhipuAI 兼容的工具模式"""
        schemas = []
        for tool in self.tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters.get("properties", {}),
                        "required": tool.parameters.get("required", [])
                    }
                }
            })
        return schemas

    async def execute(self, name: str, args: Dict[str, Any]) -> str:
        if name not in self.tools:
            return f"Error: Tool '{name}' not found."
        try:
            func = self.tools[name].func
            if inspect.iscoroutinefunction(func):
                return await func(**args)
            return func(**args)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"

# 全局注册表
registry = ToolRegistry()
```

#### 2.5.2 tools/filesystem.py - 文件操作

```python
import os
import aiofiles
from tools.base import registry

@registry.register(
    name="read",
    description="Read file content with line numbers. Use offset/limit for large files.",
    parameters={
        "properties": {
            "path": {"type": "string", "description": "Absolute path to file"},
            "offset": {"type": "integer", "description": "Start line number (0-indexed)"},
            "limit": {"type": "integer", "description": "Max lines to read"}
        },
        "required": ["path"]
    }
)
async def read_file(path: str, offset: int = 0, limit: int = 200) -> str:
    if not os.path.exists(path):
        return f"Error: File {path} not found."
    try:
        async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
            lines = await f.readlines()
        total_lines = len(lines)
        if offset >= total_lines:
            return f"Error: Offset {offset} out of bounds (file has {total_lines} lines)."
        selected = lines[offset : offset + limit]
        content = "".join(f"{offset + i + 1:4}| {line}" for i, line in enumerate(selected))
        footer = ""
        if offset + limit < total_lines:
            footer = f"\n... ({total_lines - (offset + limit)} more lines) ..."
        return content + footer
    except Exception as e:
        return f"Error reading file: {str(e)}"

@registry.register(
    name="write",
    description="Write content to a file (overwrites existing).",
    parameters={
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"}
        },
        "required": ["path", "content"]
    }
)
async def write_file(path: str, content: str) -> str:
    try:
        async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
            await f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

@registry.register(
    name="edit",
    description="Replace a unique string in a file with a new string.",
    parameters={
        "properties": {
            "path": {"type": "string"},
            "old_str": {"type": "string"},
            "new_str": {"type": "string"}
        },
        "required": ["path", "old_str", "new_str"]
    }
)
async def edit_file(path: str, old_str: str, new_str: str) -> str:
    if not os.path.exists(path):
        return f"Error: File {path} not found."
    try:
        async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
            content = await f.read()
        if old_str not in content:
            return "Error: old_str not found in file."
        count = content.count(old_str)
        if count > 1:
            return f"Error: old_str occurs {count} times. Please provide a more unique context."
        new_content = content.replace(old_str, new_str)
        async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
            await f.write(new_content)
        return "Successfully edited file."
    except Exception as e:
        return f"Error editing file: {str(e)}"
```

#### 2.5.3 tools/search.py - 搜索工具

```python
import glob as pyglob
import os
import re
from tools.base import registry

@registry.register(
    name="glob",
    description="Find files matching a glob pattern.",
    parameters={
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "default": "."}
        },
        "required": ["pattern"]
    }
)
async def glob_search(pattern: str, path: str = ".") -> str:
    try:
        full_pattern = os.path.join(path, pattern)
        files = pyglob.glob(full_pattern, recursive=True)
        # 过滤掉常见忽略目录
        files = [f for f in files if ".git" not in f and "venv" not in f
                 and "__pycache__" not in f and "node_modules" not in f]
        if not files:
            return "No files found."
        # 按修改时间排序
        files.sort(key=lambda x: os.path.getmtime(x) if os.path.isfile(x) else 0, reverse=True)
        return "\n".join(files[:50])
    except Exception as e:
        return f"Error executing glob: {str(e)}"

@registry.register(
    name="grep",
    description="Search for a regex pattern in files.",
    parameters={
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "default": "."},
            "include": {"type": "string", "default": "**/*"}
        },
        "required": ["pattern"]
    }
)
async def grep_search(pattern: str, path: str = ".", include: str = "**/*") -> str:
    try:
        regex = re.compile(pattern)
        hits = []
        search_files = pyglob.glob(os.path.join(path, include), recursive=True)
        for filepath in search_files:
            if not os.path.isfile(filepath):
                continue
            if any(ignore in filepath for ignore in
                   [".git", "venv", "__pycache__", "node_modules"]):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            hits.append(f"{filepath}:{i}: {line.strip()}")
                        if len(hits) >= 100:
                            break
            except Exception:
                pass
            if len(hits) >= 100:
                break
        if not hits:
            return "No matches found."
        return "\n".join(hits)
    except Exception as e:
        return f"Error executing grep: {str(e)}"
```

#### 2.5.4 tools/shell.py - Shell 命令

```python
import asyncio
import subprocess
from tools.base import registry

@registry.register(
    name="bash",
    description="Execute a shell command (bash/cmd/powershell).",
    parameters={
        "properties": {
            "cmd": {"type": "string"}
        },
        "required": ["cmd"]
    }
)
async def run_shell(cmd: str) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            return "Error: Command timed out after 30s."
        output = stdout.decode('utf-8', errors='replace')
        error = stderr.decode('utf-8', errors='replace')
        result = output
        if error:
            result += f"\nSTDERR:\n{error}"
        if not result.strip():
            return "(Command executed with no output)"
        return result.strip()
    except Exception as e:
        return f"Error executing command: {str(e)}"
```

#### 2.5.5 tools/todo.py - 任务管理

```python
from tools.base import registry
from core.task import TaskManager

_GLOBAL_TASK_MANAGER = None

def set_global_task_manager(manager: TaskManager):
    global _GLOBAL_TASK_MANAGER
    _GLOBAL_TASK_MANAGER = manager

@registry.register(
    name="todo_add",
    description="Add a new task to the todo list.",
    parameters={
        "properties": {
            "content": {"type": "string"}
        },
        "required": ["content"]
    }
)
def todo_add(content: str) -> str:
    if not _GLOBAL_TASK_MANAGER:
        return "Error: Task manager not initialized."
    task_id = _GLOBAL_TASK_MANAGER.add_task(content)
    _GLOBAL_TASK_MANAGER.print_summary()
    return f"Task added with ID: {task_id}"

@registry.register(
    name="todo_update",
    description="Update the status of a task.",
    parameters={
        "properties": {
            "task_id": {"type": "string"},
            "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "skipped"]}
        },
        "required": ["task_id", "status"]
    }
)
def todo_update(task_id: str, status: str) -> str:
    if not _GLOBAL_TASK_MANAGER:
        return "Error: Task manager not initialized."
    if _GLOBAL_TASK_MANAGER.update_task(task_id, status):
        _GLOBAL_TASK_MANAGER.print_summary()
        return f"Task {task_id} updated to {status}."
    return f"Error: Task {task_id} not found."

@registry.register(
    name="todo_list",
    description="List all tasks and their status.",
    parameters={
        "properties": {},
        "required": []
    }
)
def todo_list() -> str:
    if not _GLOBAL_TASK_MANAGER:
        return "Error: Task manager not initialized."
    return _GLOBAL_TASK_MANAGER.render()
```

---

## 三、nanocode 完整分析

### 3.1 项目结构

```
nanocode/
├── README.md          # 项目说明
├── nanocode.py        # 主程序 (单文件, ~250 行)
└── screenshot.png     # 运行截图
```

### 3.2 完整源码

```python
#!/usr/bin/env python3
"""
nanocode - A minimal Claude Code replacement
Single file, zero dependencies, ~250 lines
"""

import glob
import json
import os
import re
import subprocess
import urllib.request
import urllib.error

# ============== Configuration ==============

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
API_URL = (
    "https://openrouter.ai/api/v1/messages"
    if OPENROUTER_KEY
    else "https://api.anthropic.com/v1/messages"
)
MODEL = os.environ.get(
    "MODEL",
    "anthropic/claude-opus-4-5" if OPENROUTER_KEY else "claude-opus-4-5"
)

# ============== ANSI Colors ==============

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"

# ============== Tool Functions ==============

def read(args):
    """Read file content with optional offset/limit"""
    path = args["path"]
    offset = args.get("offset", 0)
    limit = args.get("limit")

    try:
        with open(path, 'r') as f:
            lines = f.readlines()

        total = len(lines)
        if offset >= total:
            return f"error: offset {offset} >= total lines {total}"

        end = total if limit is None else offset + limit
        selected = lines[offset:end]

        # Add line numbers
        result = "".join(f"{offset + i + 1:4}| {line}" for i, line in enumerate(selected))

        if end < total:
            result += f"\n... ({total - end} more lines)"

        return result
    except FileNotFoundError:
        return f"error: file not found: {path}"
    except Exception as err:
        return f"error: {err}"


def write(args):
    """Write content to file (overwrite)"""
    path = args["path"]
    content = args["content"]

    try:
        # Create directory if needed
        dir_path = os.path.dirname(path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        with open(path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as err:
        return f"error: {err}"


def edit(args):
    """Replace string in file (with safety checks)"""
    path = args["path"]
    old = args["old"]
    new = args["new"]
    replace_all = args.get("all", False)

    try:
        with open(path, 'r') as f:
            text = f.read()

        # Safety check 1: old must exist
        if old not in text:
            return f"error: old_string not found in {path}"

        # Safety check 2: uniqueness check
        count = text.count(old)
        if not replace_all and count > 1:
            return f"error: old_string appears {count} times, must be unique (use all=true)"

        # Perform replacement
        text = text.replace(old, new)

        with open(path, 'w') as f:
            f.write(text)

        return f"Successfully replaced {count} occurrence(s)"
    except FileNotFoundError:
        return f"error: file not found: {path}"
    except Exception as err:
        return f"error: {err}"


def glob_files(args):
    """Find files by pattern"""
    pattern = args["pattern"]

    try:
        files = glob.glob(pattern, recursive=True)
        # Filter common ignores
        files = [f for f in files if not any(
            ignore in f for ignore in [".git", "venv", "__pycache__", "node_modules"]
        )]

        if not files:
            return "No files found"

        # Sort by modification time
        files.sort(key=lambda x: os.path.getmtime(x) if os.path.isfile(x) else 0, reverse=True)

        return "\n".join(files[:50])
    except Exception as err:
        return f"error: {err}"


def grep_content(args):
    """Search content with regex"""
    pattern = args["pattern"]
    path = args.get("path", ".")

    try:
        regex = re.compile(pattern)
        hits = []

        # Find all files in path
        if os.path.isfile(path):
            files = [path]
        else:
            files = []
            for root, dirs, filenames in os.walk(path):
                # Filter directories
                dirs[:] = [d for d in dirs if d not in {".git", "venv", "__pycache__", "node_modules"}]
                for filename in filenames:
                    files.append(os.path.join(root, filename))

        # Search each file
        for filepath in files:
            try:
                with open(filepath, 'r', errors='ignore') as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            hits.append(f"{filepath}:{i}: {line.strip()}")
                            if len(hits) >= 50:
                                break
            except Exception:
                pass
            if len(hits) >= 50:
                break

        if not hits:
            return "No matches found"

        return "\n".join(hits)
    except Exception as err:
        return f"error: {err}"


def bash(args):
    """Execute shell command with real-time output"""
    cmd = args["cmd"]

    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        output_lines = []

        # Stream output line by line
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                # Print with indentation
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)

        # Check exit code
        return_code = proc.poll()
        if return_code != 0:
            return f"Command failed with exit code {return_code}"

        return "".join(output_lines)
    except Exception as err:
        return f"error: {err}"


# ============== Tool Registry ==============

TOOLS = {
    "read": (
        "Read file content with optional offset/limit",
        {"path": "string", "offset": "number?", "limit": "number?"},
        read
    ),
    "write": (
        "Write content to file (overwrites existing)",
        {"path": "string", "content": "string"},
        write
    ),
    "edit": (
        "Replace a unique string in a file with a new string",
        {"path": "string", "old": "string", "new": "string", "all": "boolean?"},
        edit
    ),
    "glob": (
        "Find files matching a glob pattern (e.g., **/*.py)",
        {"pattern": "string"},
        glob_files
    ),
    "grep": (
        "Search file contents with a regex pattern",
        {"pattern": "string", "path": "string?"},
        grep_content
    ),
    "bash": (
        "Execute a shell command",
        {"cmd": "string"},
        bash
    ),
}


def make_schema():
    """Generate Claude API tool schema from TOOLS dict"""
    result = []
    for name, (description, params, _) in TOOLS.items():
        properties = {}
        required = []

        for param_name, param_type in params.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")

            # Map to JSON Schema types
            json_type = "integer" if base_type == "number" else "boolean" if base_type == "boolean" else "string"

            properties[param_name] = {"type": json_type}
            if not is_optional:
                required.append(param_name)

        result.append({
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        })

    return result


# ============== API Client ==============

def call_api(messages, system_prompt=""):
    """Call Anthropic/OpenRouter API"""
    request_body = {
        "model": MODEL,
        "max_tokens": 8192,
        "system": system_prompt,
        "messages": messages,
        "tools": make_schema(),
    }

    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    if OPENROUTER_KEY:
        headers["Authorization"] = f"Bearer {OPENROUTER_KEY}"
    else:
        headers["x-api-key"] = os.environ.get("ANTHROPIC_API_KEY", "")

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(request_body).encode(),
        headers=headers
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode())
            return data
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return {"error": f"HTTP {e.code}: {error_body}"}
    except Exception as err:
        return {"error": str(err)}


# ============== Helpers ==============

def render_markdown(text):
    """Simple markdown rendering (bold only)"""
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def separator():
    """Print a separator line"""
    width = min(os.get_terminal_size().columns, 80)
    return f"{DIM}{'─' * width}{RESET}"


# ============== Main Loop ==============

def main():
    messages = []

    print(f"{BOLD}{BLUE}nanocode{RESET} - minimal AI coding assistant")
    print(f"Type {CYAN}/c{RESET} to clear, {CYAN}/q{RESET} or {CYAN}exit{RESET} to quit")
    print(separator())

    while True:
        try:
            # Get user input
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ["/q", "exit", "quit"]:
                print(f"{DIM}Goodbye!{RESET}")
                break
            if user_input.lower() == "/c":
                messages = []
                print(f"{DIM}Conversation cleared{RESET}")
                print(separator())
                continue

            # Add user message
            messages.append({"role": "user", "content": user_input})

            # Agentic loop: keep calling until no more tool calls
            while True:
                # Call API
                response = call_api(messages)

                if "error" in response:
                    print(f"{RED}Error: {response['error']}{RESET}")
                    break

                content_blocks = response.get("content", [])
                tool_results = []

                # Process each block
                for block in content_blocks:
                    if block["type"] == "text":
                        # Render and print text
                        text = render_markdown(block["text"])
                        print(f"{CYAN}{text}{RESET}")

                    elif block["type"] == "tool_use":
                        # Execute tool
                        tool_name = block["name"]
                        tool_input = block["input"]
                        tool_id = block["id"]

                        print(f"{GREEN}⏺ {tool_name}{RESET}({DIM}{json.dumps(tool_input)}{RESET})")

                        # Run tool
                        result = TOOLS[tool_name][2](tool_input)

                        # Check for error
                        if result.startswith("error:"):
                            print(f"  {RED}{result}{RESET}")
                        else:
                            # Preview result
                            preview = result[:200] + "..." if len(result) > 200 else result
                            print(f"  {DIM}→ {preview}{RESET}")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        })

                # Add assistant response to history
                messages.append({
                    "role": "assistant",
                    "content": content_blocks
                })

                # If no tools were called, we're done
                if not tool_results:
                    break

                # Add tool results as new user message
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

                print()  # Blank line between iterations

            print(separator())

        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Goodbye!{RESET}")
            break


if __name__ == "__main__":
    main()
```

### 3.3 代码结构分析

```
nanocode.py 结构:
├── Configuration (API URL, Model)
├── ANSI Colors
├── Tool Functions (6个)
│   ├── read()   - 读取文件
│   ├── write()  - 写入文件
│   ├── edit()   - 编辑文件
│   ├── glob()   - 文件搜索
│   ├── grep()   - 内容搜索
│   └── bash()   - Shell 命令
├── Tool Registry (TOOLS 字典)
├── Schema Generator (make_schema)
├── API Client (call_api)
├── Helpers (render_markdown, separator)
└── Main Loop (Agentic Loop)
```

### 3.4 核心设计模式

#### 模式 1: 工具注册表模式

```python
TOOLS = {
    "read": (description, params, function),
    "write": (description, params, function),
    # ...
}

# 自动生成 API Schema
def make_schema():
    for name, (desc, params, _) in TOOLS.items():
        # 构造 tool schema
    return result
```

#### 模式 2: Agentic Loop (递归工具调用)

```
用户输入 → API → [有工具调用?] → YES → 执行工具 → 结果反馈 → API
                                                      ↓
                                                  NO → 输出答案
```

#### 模式 3: 零依赖架构

```python
# 仅使用 Python 标准库
import glob          # 文件匹配
import json          # JSON 处理
import os            # 文件操作
import re            # 正则表达式
import subprocess    # Shell 命令
import urllib.request  # HTTP 客户端 (替代 requests)
```

---

## 四、代码生成与修改机制对比

### 4.1 工具对比表

| 工具类型 | easy-coding-agents | nanocode |
|----------|-------------------|----------|
| **文件读取** | `read(path, offset, limit)` | `read(path, offset?, limit?)` |
| **文件写入** | `write(path, content)` | `write(path, content)` |
| **文件编辑** | `edit(path, old_str, new_str)` | `edit(path, old, new, all?)` |
| **文件搜索** | `glob(pattern, path)` | `glob(pattern)` |
| **内容搜索** | `grep(pattern, path, include)` | `grep(pattern, path?)` |
| **命令执行** | `bash(cmd)` | `bash(cmd)` |
| **任务管理** | `todo_add`, `todo_update`, `todo_list` | - |
| **会话管理** | 自动持久化到 JSON | - |

### 4.2 Edit 工具安全机制对比

**两者都采用"唯一匹配"策略**:

```python
# easy-coding-agents
async def edit_file(path: str, old_str: str, new_str: str) -> str:
    async with aiofiles.open(path, 'r') as f:
        content = await f.read()

    if old_str not in content:
        return "Error: old_str not found in file."

    count = content.count(old_str)
    if count > 1:
        return f"Error: old_str occurs {count} times. Please provide a more unique context."

    new_content = content.replace(old_str, new_str)
    async with aiofiles.open(path, 'w') as f:
        await f.write(new_content)
    return "Successfully edited file."

# nanocode
def edit(args):
    path, old, new = args["path"], args["old"], args["new"]
    replace_all = args.get("all", False)

    with open(path, 'r') as f:
        text = f.read()

    if old not in text:
        return f"error: old_string not found"

    count = text.count(old)
    if not replace_all and count > 1:
        return f"error: old_string appears {count} times"

    text = text.replace(old, new)
    with open(path, 'w') as f:
        f.write(text)
    return f"Successfully replaced {count} occurrence(s)"
```

### 4.3 工具注册对比

**easy-coding-agents - 装饰器模式**:

```python
registry = ToolRegistry()

@registry.register(
    name="read",
    description="Read file content with line numbers",
    parameters={
        "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"}
        },
        "required": ["path"]
    }
)
async def read_file(path: str, offset: int = 0, limit: int = 200):
    # 实现
    pass
```

**nanocode - 字典模式**:

```python
TOOLS = {
    "read": (
        "Read file content with optional offset/limit",
        {"path": "string", "offset": "number?", "limit": "number?"},
        lambda args: read(args)  # 或直接用函数名 read
    ),
}

def make_schema():
    for name, (desc, params, _) in TOOLS.items():
        # 自动生成 Schema
    return schemas
```

---

## 五、上下文管理策略深度分析

### 5.1 easy-coding-agents - 三层记忆

```
┌─────────────────────────────────────────────────────────────┐
│                    MemoryManager (Facade)                    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │ Short-Term  │    │ Medium-Term │    │  Long-Term  │      │
│  │             │    │             │    │             │      │
│  │ 活跃上下文  │◄───│ AU2 压缩器  │    │ CLAUDE.md   │      │
│  │ Token监控   │──▶│ 8维摘要     │    │ 项目经验    │      │
│  │ 92%触发    │    │             │    │ 跨会话持久  │      │
│  └─────────────┘    └─────────────┘    └─────────────┘      │
│         │                                  ▲                │
│         │           ┌──────────────┐       │                │
│         └──────────▶│SessionStore  │───────┘                │
│                     │ JSON持久化   │                        │
│                     └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

**数据流**:

```
1. 添加消息 → ShortTermMemory.add()
2. Token 检测 → _check_overflow()
3. 超过 92% → MemoryOverflowError
4. 触发压缩 → MediumTermMemory.compress()
5. 8维摘要 → AU2 算法
6. 重构上下文 → System + Intro + Summary + Recent
7. 持久化 → SessionStore.save()
8. 提取价值 → LongTermMemory.update()
```

### 5.2 nanocode - 简单累积

```python
messages = []

while True:
    # 用户输入
    messages.append({"role": "user", "content": user_input})

    # API 调用
    response = call_api(messages)

    # 助手响应
    messages.append({"role": "assistant", "content": response["content"]})

    # 工具结果
    if tool_results:
        messages.append({"role": "user", "content": tool_results})
```

**特点**:
- 无显式压缩
- 依赖 API 的 `max_tokens` 参数
- 简单但无法处理长对话

---

## 六、对 instant-coffee 的实施建议

### 6.1 架构对比

| 维度 | easy-coding-agents | nanocode | instant-coffee (当前) |
|------|-------------------|----------|----------------------|
| **架构** | Task-Driven 自主循环 | 单 Agent 递归 | Interview → Generation → Refinement |
| **LLM** | 智谱 AI | Claude/OpenRouter | Claude Sonnet 4 |
| **记忆** | 三层架构 | 简单累积 | 会话保存 + 版本控制 |
| **目标** | 通用编程助手 | 代码编辑工具 | 移动端页面生成 |
| **UI** | CLI (Rich) | CLI (ANSI) | CLI + Web (React) |
| **异步** | asyncio + 双队列 | 同步 | asyncio |

### 6.2 实施优先级

| 优先级 | 功能 | 来源 | 复杂度 | 收益 |
|--------|------|------|--------|------|
| **P0** | Edit 工具唯一性检查 | 两者共用 | 低 | 安全性提升 |
| **P0** | 实时流式输出 | nanocode | 中 | 体验大幅提升 |
| **P1** | 工具注册装饰器 | easy-coding-agents | 低 | 可维护性提升 |
| **P1** | 会话持久化 (JSON) | easy-coding-agents | 中 | 断点续传 |
| **P2** | AU2 压缩算法 | easy-coding-agents | 高 | 长对话支持 |
| **P2** | 任务驱动架构 | easy-coding-agents | 高 | 自主性提升 |

### 6.3 P0: Edit 工具安全增强

```python
# app/tools/file_editor.py
import asyncio
import aiofiles

async def edit_html_file(
    path: str,
    old_string: str,
    new_string: str,
    require_unique: bool = True
) -> str:
    """
    安全编辑 HTML 文件

    Args:
        path: 文件路径
        old_string: 要替换的旧字符串
        new_string: 新字符串
        require_unique: 是否要求唯一匹配 (默认 True)
    """
    try:
        async with aiofiles.open(path, 'r', encoding='utf-8') as f:
            content = await f.read()

        # 安全检查 1: 旧字符串必须存在
        if old_string not in content:
            return f"error: old_string not found in {path}"

        # 安全检查 2: 唯一性检查
        occurrences = content.count(old_string)
        if require_unique and occurrences > 1:
            return f"error: old_string appears {occurrences} times. " \
                   f"Use require_unique=false to replace all."

        # 执行替换
        new_content = content.replace(old_string, new_string)

        # 写回文件
        async with aiofiles.open(path, 'w', encoding='utf-8') as f:
            await f.write(new_content)

        return f"Successfully replaced {occurrences} occurrence(s)"

    except FileNotFoundError:
        return f"error: file not found: {path}"
    except Exception as e:
        return f"error: {str(e)}"
```

### 6.4 P0: 实时流式输出

```python
# app/llm/stream_handler.py
from anthropic import AsyncAnthropic
from typing import AsyncIterator, Optional, Tuple, List
from dataclasses import dataclass

@dataclass
class StreamChunk:
    type: str  # "text" or "tool_use"
    content: Optional[str] = None
    name: Optional[str] = None
    input: Optional[dict] = None

class StreamHandler:
    """Claude 流式输出处理器"""

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)

    async def stream_chat(
        self,
        messages: List[dict],
        tools: List[dict],
        system_prompt: str = "",
        model: str = "claude-sonnet-4-20250514"
    ) -> AsyncIterator[StreamChunk]:
        """
        流式聊天，返回生成器

        Yields:
            StreamChunk: 包含类型和内容
        """
        async with self.client.messages.stream(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            tools=tools,
        ) as stream:
            # 文本流
            async for text in stream.text_stream:
                yield StreamChunk(type="text", content=text)

            # 最终响应 (包含工具调用)
            response = await stream.get_final_message()
            for block in response.content:
                if block.type == "tool_use":
                    yield StreamChunk(
                        type="tool_use",
                        name=block.name,
                        input=block.input
                    )

# 使用示例
async def generate_with_progress(handler: StreamHandler, messages, tools, system_prompt):
    """带进度的生成"""
    full_text = ""
    tool_calls = []

    async for chunk in handler.stream_chat(messages, tools, system_prompt):
        if chunk.type == "text":
            print(chunk.content, end="", flush=True)
            full_text += chunk.content
        elif chunk.type == "tool_use":
            print(f"\n[工具调用] {chunk.name}")
            tool_calls.append({
                "name": chunk.name,
                "input": chunk.input
            })

    print()  # 换行
    return full_text, tool_calls
```

### 6.5 P1: 工具注册装饰器

```python
# app/agents/tools/base.py
from typing import Dict, Any, Callable, List
from dataclasses import dataclass
import inspect

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable

class ToolRegistry:
    """统一的工具注册表"""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, parameters: Dict[str, Any]):
        """
        装饰器工厂

        用法:
        @registry.register(
            name="read_file",
            description="读取文件内容",
            parameters={"properties": {...}, "required": [...]}
        )
        async def read_file(path: str):
            ...
        """
        def decorator(func: Callable):
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                func=func
            )
            return func
        return decorator

    def get_tool_schemas(self) -> List[Dict]:
        """生成 Claude API 需要的 tools 格式"""
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": tool.parameters.get("properties", {}),
                    "required": tool.parameters.get("required", [])
                }
            })
        return schemas

    async def execute(self, name: str, args: Dict) -> str:
        """执行工具"""
        if name not in self._tools:
            return f"Error: Tool '{name}' not found."

        func = self._tools[name].func
        try:
            if inspect.iscoroutinefunction(func):
                return await func(**args)
            return func(**args)
        except Exception as e:
            return f"Error: {str(e)}"

# 全局注册表
registry = ToolRegistry()
```

### 6.6 P1: 会话持久化

```python
# app/db/session_store.py
import json
import asyncio
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import aiofiles

@dataclass
class SessionSnapshot:
    """会话快照"""
    session_id: str
    timestamp: str
    messages: List[Dict]
    page_versions: List[Dict]
    context_summary: Optional[str] = None
    user_preferences: Optional[Dict] = None

class SessionStore:
    """会话持久化存储"""

    def __init__(self, storage_dir: str = "~/.instant-coffee/sessions"):
        self.storage_dir = Path(storage_dir).expanduser()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.current_session_file = None

    def create_new_session(self):
        """创建新会话"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"session_{timestamp}"
        self.current_session_file = self.storage_dir / f"{session_id}.json"
        return session_id

    async def save_session(self, session: SessionSnapshot):
        """保存会话"""
        if not self.current_session_file:
            session.session_id = self.create_new_session()

        session.timestamp = datetime.now().isoformat()

        async with aiofiles.open(self.current_session_file, 'w') as f:
            await f.write(json.dumps(asdict(session), ensure_ascii=False, indent=2))

    async def load_session(self, session_id: str) -> Optional[SessionSnapshot]:
        """加载会话，用于断点续传"""
        file_path = self.storage_dir / f"{session_id}.json"
        if not file_path.exists():
            return None

        async with aiofiles.open(file_path, 'r') as f:
            data = json.loads(await f.read())
            return SessionSnapshot(**data)

    async def load_latest_session(self) -> Optional[SessionSnapshot]:
        """加载最新会话"""
        sessions = sorted(
            self.storage_dir.glob("session_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if not sessions:
            return None

        latest = sessions[0]
        self.current_session_file = latest

        async with aiofiles.open(latest, 'r') as f:
            data = json.loads(await f.read())
            return SessionSnapshot(**data)

    async def list_sessions(self) -> List[Dict]:
        """列出所有会话"""
        sessions = []
        for file_path in self.storage_dir.glob("session_*.json"):
            async with aiofiles.open(file_path, 'r') as f:
                data = json.loads(await f.read())
                sessions.append({
                    "session_id": data["session_id"],
                    "timestamp": data["timestamp"],
                    "message_count": len(data.get("messages", []))
                })
        return sorted(sessions, key=lambda x: x["timestamp"], reverse=True)
```

### 6.7 P2: AU2 压缩算法

```python
# app/memory/compressor.py
import json
from typing import List, Dict, Any, Optional, Tuple

class AU2Compressor:
    """
    AU2 (Agentic Understanding & Unification) 压缩器

    用于将长对话历史压缩为结构化摘要
    """

    def __init__(self, llm_client):
        self.llm = llm_client

    async def compress(self, messages: List[Dict]) -> Tuple[List[Dict], Optional[Dict]]:
        """
        压缩对话历史

        策略:
        - System: 保留
        - 前 2 条: 保留
        - 后 4 条: 保留
        - 中间部分: 8 维摘要
        """
        if len(messages) <= 10:
            return messages, None

        # 分离消息
        system = [m for m in messages if m["role"] == "system"]
        dialogue = [m for m in messages if m["role"] != "system"]

        intro = dialogue[:2]
        recent = dialogue[-4:]
        middle = dialogue[2:-4]

        # 构建 8 维摘要
        summary = await self._create_summary(middle)

        # 格式化摘要
        compressed_msg = {
            "role": "system",
            "content": self._format_summary(summary)
        }

        # 重构上下文
        new_context = system + intro + [compressed_msg] + recent
        return new_context, summary

    async def _create_summary(self, messages: List[Dict]) -> Dict[str, str]:
        """创建 8 维摘要"""
        # 将对话转换为文本
        dialogue_text = "\n".join([
            f"{m['role']}: {m.get('content', '')}"
            for m in messages
        ])

        prompt = f"""将以下对话压缩为 8 个维度的摘要 (JSON 格式):

对话内容:
{dialogue_text}

输出格式:
{{
  "background": "任务背景和目标",
  "decisions": "关键技术决策和原因",
  "tools": "使用的工具、参数和结果",
  "intent": "用户核心意图的演变",
  "results": "已完成的工作和产出",
  "errors": "遇到的错误和解决方案",
  "legacy_issues": "尚未解决的问题",
  "next_steps": "计划中的下一步行动"
}}
"""

        response = await self.llm.generate(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw_summary": response}

    def _format_summary(self, summary: Dict[str, str]) -> str:
        """格式化摘要为可读文本"""
        return f"""
[上下文摘要 - AU2 压缩]
背景: {summary.get('background', '')}
决策: {summary.get('decisions', '')}
工具: {summary.get('tools', '')}
意图: {summary.get('intent', '')}
结果: {summary.get('results', '')}
错误: {summary.get('errors', '')}
遗留问题: {summary.get('legacy_issues', '')}
下一步: {summary.get('next_steps', '')}
"""
```

### 6.8 P2: 任务驱动架构重构

```python
# app/agents/task_orchestrator.py
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"

@dataclass
class Task:
    id: str
    content: str
    status: TaskStatus = TaskStatus.PENDING

class TaskOrchestrator:
    """
    任务驱动的编排器

    替代当前的 Interview → Generation → Refinement 线性流程
    """

    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tools = tool_registry
        self.tasks: List[Task] = []

    async def process_request(self, user_input: str) -> str:
        """
        处理用户请求

        流程:
        1. 解析请求，生成初始任务
        2. 循环执行任务直到完成
        3. 返回结果
        """
        # 1. 生成任务计划
        await self._plan_tasks(user_input)

        # 2. 执行任务循环
        while self._has_unfinished_tasks():
            task = self._get_next_task()

            # 更新状态
            task.status = TaskStatus.IN_PROGRESS

            # 执行任务
            result = await self._execute_task(task)

            # 更新状态
            task.status = TaskStatus.COMPLETED

        # 3. 返回结果
        return self._get_final_result()

    async def _plan_tasks(self, user_input: str):
        """根据用户输入生成任务计划"""
        prompt = f"""
根据以下用户请求，生成完成该任务所需的步骤列表。

用户请求: {user_input}

对于移动端页面生成，考虑以下步骤:
1. 理解需求和目标
2. 收集缺失信息 (如有)
3. 生成移动端 HTML
4. 验证移动端规范
5. 根据反馈优化

返回 JSON 格式的任务列表:
{{
  "tasks": [
    {{"id": "1", "content": "任务描述"}},
    ...
  ]
}}
"""

        response = await self.llm.generate(prompt)
        data = json.loads(response)

        self.tasks = [
            Task(id=t["id"], content=t["content"])
            for t in data.get("tasks", [])
        ]

    async def _execute_task(self, task: Task) -> str:
        """执行单个任务"""
        # 根据任务内容决定使用哪些工具
        # 这里可以结合 RAG 或规则引擎
        pass

    def _has_unfinished_tasks(self) -> bool:
        """检查是否有未完成的任务"""
        return any(
            t.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
            for t in self.tasks
        )

    def _get_next_task(self) -> Task:
        """获取下一个任务 (优先 in_progress)"""
        # 优先返回正在进行的任务
        for task in self.tasks:
            if task.status == TaskStatus.IN_PROGRESS:
                return task
        # 然后返回待处理任务
        for task in self.tasks:
            if task.status == TaskStatus.PENDING:
                return task
        return None
```

---

## 七、总结

### 7.1 核心共识

两者在 **代码生成/修改** 的核心逻辑上是相通的:

```
1. 定义一组原子工具 (read/write/edit/glob/grep/bash)
2. 让 LLM 通过 Tool Use 自主组合调用
3. 递归调用直到任务完成
4. 唯一匹配保证编辑安全性
```

### 7.2 设计哲学对比

| 方面 | easy-coding-agents | nanocode |
|------|-------------------|----------|
| **哲学** | 完整工程化 | 极简主义 |
| **代码量** | 2000+ 行 | 250 行 |
| **依赖** | 5+ 外部库 | 零依赖 |
| **功能** | 完整产品 | 核心功能 |
| **适用** | 生产环境 | 学习/原型 |

### 7.3 对 instant-coffee 的价值

| 方面 | 借鉴点 |
|------|--------|
| **架构** | Task-Driven 替代线性流程 |
| **工具** | 装饰器注册 + Schema 自动生成 |
| **记忆** | AU2 压缩管理长对话 |
| **体验** | 实时流式输出 + 会话持久化 |
| **安全** | Edit 唯一性检查 |
| **简化** | 学习 nanocode 的极简哲学 |

---

**报告生成时间**: 2025-02-06
**分析者**: Claude (Opus 4.5)
**项目**: instant-coffee 移动端页面生成工具
