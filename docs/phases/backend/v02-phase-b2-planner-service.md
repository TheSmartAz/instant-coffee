# Phase B2: Planner 服务

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: D1 (Plan/Task Schema), B1 (事件协议)
  - **Blocks**: B3 (并行执行引擎), F3 (Todo 面板)

## Goal

实现 AI Planner 服务，分析用户需求并生成结构化的执行计划 (Plan)，支持多种 LLM 后端。

## Detailed Tasks

### Task 1: 创建 Planner 基类

**Description**: 定义 Planner 的抽象接口

**Implementation Details**:
- [ ] 创建 BasePlanner 抽象类
- [ ] 定义 plan() 方法签名
- [ ] 定义 Plan 输出格式

**Files to modify/create**:
- `packages/backend/app/planner/__init__.py`
- `packages/backend/app/planner/base.py`

**Acceptance Criteria**:
- [ ] BasePlanner 定义清晰的接口
- [ ] 支持异步调用

---

### Task 2: 实现 OpenAI Planner

**Description**: 使用 OpenAI API (GPT-4o-mini) 实现 Planner

**Implementation Details**:
- [ ] 创建 OpenAIPlanner 类
- [ ] 实现 Planner prompt 模板
- [ ] 解析 LLM 返回的 JSON
- [ ] 处理 API 错误和重试

**Files to modify/create**:
- `packages/backend/app/planner/openai_planner.py`
- `packages/backend/app/planner/prompts.py`

**Acceptance Criteria**:
- [ ] 可以调用 OpenAI API 生成 Plan
- [ ] 返回结构化的 Plan 对象
- [ ] 错误处理完善

---

### Task 3: 实现 Anthropic Planner

**Description**: 使用 Anthropic API (Claude Haiku) 实现 Planner

**Implementation Details**:
- [ ] 创建 AnthropicPlanner 类
- [ ] 复用 Planner prompt 模板
- [ ] 解析 LLM 返回的 JSON

**Files to modify/create**:
- `packages/backend/app/planner/anthropic_planner.py`

**Acceptance Criteria**:
- [ ] 可以调用 Anthropic API 生成 Plan
- [ ] 与 OpenAIPlanner 输出格式一致

---

### Task 4: 创建 Planner 工厂

**Description**: 根据配置创建对应的 Planner 实例

**Implementation Details**:
- [ ] 创建 PlannerFactory 类
- [ ] 读取环境变量配置
- [ ] 支持运行时切换 Planner

**Files to modify/create**:
- `packages/backend/app/planner/factory.py`
- `packages/backend/app/config.py`

**Acceptance Criteria**:
- [ ] 可以通过配置切换 Planner 实现
- [ ] 默认使用 OpenAI (GPT-4o-mini)

---

### Task 5: 创建 Plan API 端点

**Description**: 暴露 Plan 生成的 REST API

**Implementation Details**:
- [ ] 创建 POST /api/plan 端点
- [ ] 接收用户消息和会话 ID
- [ ] 返回生成的 Plan
- [ ] 保存 Plan 到数据库

**Files to modify/create**:
- `packages/backend/app/api/plan.py`
- `packages/backend/app/main.py`

**Acceptance Criteria**:
- [ ] API 可以正常调用
- [ ] Plan 保存到数据库
- [ ] 返回完整的 Plan 结构

---

## Technical Specifications

### Planner 接口定义

```python
# packages/backend/app/planner/base.py
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel

class TaskPlan(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    agent_type: str  # Interview, Generation, Refinement, Validator, Export
    depends_on: list[str] = []
    can_parallel: bool = True

class Plan(BaseModel):
    id: str
    goal: str
    tasks: list[TaskPlan]

class BasePlanner(ABC):
    @abstractmethod
    async def plan(
        self,
        user_message: str,
        context: Optional[str] = None
    ) -> Plan:
        """Generate execution plan from user message"""
        pass
```

### Planner Prompt 模板

```python
# packages/backend/app/planner/prompts.py

PLANNER_SYSTEM_PROMPT = """你是 Instant Coffee 的 Planner，负责分析用户需求并生成执行计划。

你的任务是：
1. 理解用户的需求
2. 将需求拆解为 5-15 个可执行的 Tasks
3. 标注 Task 之间的依赖关系
4. 标注哪些 Task 可以并行执行

输出格式 (JSON):
{
  "goal": "用户目标的简短描述",
  "tasks": [
    {
      "id": "task_1",
      "title": "任务标题",
      "description": "任务详细描述",
      "depends_on": [],
      "can_parallel": true,
      "agent_type": "Interview"
    }
  ]
}

可用的 Agent 类型:
- Interview: 收集用户需求，通过提问澄清细节
- Generation: 生成页面 HTML/CSS/JS
- Refinement: 根据反馈修改页面
- Validator: 验证输出是否符合要求
- Export: 导出文件到指定目录

规则:
1. 第一个 Task 通常是 Interview (除非用户需求已经非常明确)
2. Generation Task 可以并行执行 (如果生成多个独立页面)
3. 最后一个 Task 通常是 Export
4. 如果有"统一优化"类的 Task，它应该依赖所有 Generation Task
5. Task 数量控制在 5-15 个
6. 只输出 JSON，不要其他内容"""

PLANNER_USER_PROMPT = """用户需求: {user_message}

{context}

请生成执行计划 (JSON 格式):"""
```

### OpenAI Planner 实现

```python
# packages/backend/app/planner/openai_planner.py
import json
import logging
from typing import Optional
from openai import AsyncOpenAI
from .base import BasePlanner, Plan, TaskPlan
from .prompts import PLANNER_SYSTEM_PROMPT, PLANNER_USER_PROMPT
from uuid import uuid4

logger = logging.getLogger(__name__)

class OpenAIPlanner(BasePlanner):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def plan(
        self,
        user_message: str,
        context: Optional[str] = None
    ) -> Plan:
        context_str = f"上下文: {context}" if context else ""
        user_prompt = PLANNER_USER_PROMPT.format(
            user_message=user_message,
            context=context_str
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        # 生成 Plan ID
        plan_id = uuid4().hex[:8]

        # 解析 tasks
        tasks = []
        for task_data in data.get("tasks", []):
            tasks.append(TaskPlan(
                id=task_data.get("id", uuid4().hex[:8]),
                title=task_data["title"],
                description=task_data.get("description"),
                agent_type=task_data.get("agent_type", "Generation"),
                depends_on=task_data.get("depends_on", []),
                can_parallel=task_data.get("can_parallel", True)
            ))

        return Plan(
            id=plan_id,
            goal=data.get("goal", user_message),
            tasks=tasks
        )
```

### Planner 工厂

```python
# packages/backend/app/planner/factory.py
from typing import Optional
from .base import BasePlanner
from .openai_planner import OpenAIPlanner
from .anthropic_planner import AnthropicPlanner
from ..config import get_settings

class PlannerFactory:
    @staticmethod
    def create(provider: Optional[str] = None) -> BasePlanner:
        settings = get_settings()
        provider = provider or settings.planner_provider

        if provider == "openai":
            return OpenAIPlanner(
                api_key=settings.openai_api_key,
                model=settings.planner_model
            )
        elif provider == "anthropic":
            return AnthropicPlanner(
                api_key=settings.anthropic_api_key,
                model=settings.planner_model
            )
        else:
            raise ValueError(f"Unknown planner provider: {provider}")
```

### API 端点

```python
# packages/backend/app/api/plan.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..db.utils import get_db
from ..db.models import Plan as PlanModel, Task as TaskModel
from ..planner.factory import PlannerFactory
from ..events.models import PlanCreatedEvent
from ..events.emitter import EventEmitter

router = APIRouter(prefix="/api")

class PlanRequest(BaseModel):
    session_id: str
    message: str
    context: Optional[str] = None

class PlanResponse(BaseModel):
    id: str
    goal: str
    tasks: list[dict]

@router.post("/plan", response_model=PlanResponse)
async def create_plan(
    request: PlanRequest,
    db: Session = Depends(get_db)
):
    planner = PlannerFactory.create()

    try:
        plan = await planner.plan(
            user_message=request.message,
            context=request.context
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 保存到数据库
    plan_model = PlanModel(
        id=plan.id,
        session_id=request.session_id,
        goal=plan.goal,
        status="pending"
    )
    db.add(plan_model)

    for task in plan.tasks:
        task_model = TaskModel(
            id=task.id,
            plan_id=plan.id,
            title=task.title,
            description=task.description,
            agent_type=task.agent_type,
            depends_on=json.dumps(task.depends_on),
            can_parallel=task.can_parallel,
            status="pending"
        )
        db.add(task_model)

    db.commit()

    return PlanResponse(
        id=plan.id,
        goal=plan.goal,
        tasks=[t.model_dump() for t in plan.tasks]
    )
```

### 配置扩展

```python
# packages/backend/app/config.py (扩展)
class Settings(BaseSettings):
    # 现有配置...

    # Planner 配置
    planner_provider: str = "openai"
    planner_model: str = "gpt-4o-mini"
    openai_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
```

## Testing Requirements

- [ ] Unit tests for OpenAIPlanner.plan()
- [ ] Unit tests for AnthropicPlanner.plan()
- [ ] Unit tests for PlannerFactory
- [ ] Integration tests for POST /api/plan endpoint
- [ ] Test Plan JSON parsing with various inputs
- [ ] Test error handling for API failures
- [ ] Mock LLM responses for deterministic testing

## Notes & Warnings

- OpenAI API 需要设置 `response_format={"type": "json_object"}` 确保返回 JSON
- Anthropic API 需要在 prompt 中明确要求 JSON 输出
- 考虑添加 Plan 缓存，避免重复生成相同需求的 Plan
- Task ID 需要在 Plan 内唯一，建议使用 `task_1`, `task_2` 格式
- 需要处理 LLM 返回格式不正确的情况
