import asyncio
import uuid

from app.config import get_settings
from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel, Task, TaskStatus
from app.db.utils import get_db
from app.events.emitter import EventEmitter
from app.events.types import EventType
from app.executor.parallel import ParallelExecutor
from app.executor.task_executor import BaseTaskExecutor, TaskExecutorFactory
from app.services.plan import PlanService


def _create_plan(database, session_id, plan_id, tasks):
    with get_db(database) as session:
        session.add(SessionModel(id=session_id, title="Test Session"))
        session.flush()
        PlanService(session).create_plan(
            session_id=session_id,
            goal="Test Plan",
            tasks=tasks,
            plan_id=plan_id,
        )
        session.commit()


def test_parallel_executor_respects_max_concurrency(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "parallel.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    plan_id = uuid.uuid4().hex
    tasks = [
        {"id": f"task_{idx}", "title": f"Task {idx}", "agent_type": "dummy"}
        for idx in range(6)
    ]
    _create_plan(database, session_id, plan_id, tasks)

    current = 0
    max_seen = 0

    class DummyExecutor(BaseTaskExecutor):
        async def execute(self, task, emitter, context):
            nonlocal current, max_seen
            current += 1
            max_seen = max(max_seen, current)
            await asyncio.sleep(0.05)
            current -= 1
            return {"ok": True}

    monkeypatch.setitem(TaskExecutorFactory._executors, "dummy", DummyExecutor)

    with get_db(database) as session:
        plan = PlanService(session).get_plan(plan_id)
        assert plan is not None
        emitter = EventEmitter(session_id=session_id)
        executor = ParallelExecutor(
            db=session,
            plan=plan,
            emitter=emitter,
            settings=get_settings(),
            output_dir=str(tmp_path),
            user_message="hi",
            history=[],
            max_concurrent=2,
        )

        async def run() -> None:
            async for _ in executor.execute():
                pass

        asyncio.run(run())

        tasks_in_db = session.query(Task).filter(Task.plan_id == plan_id).all()
        assert all(task.status == TaskStatus.DONE.value for task in tasks_in_db)
        assert max_seen <= 2


def test_parallel_executor_failure_blocks_dependents(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "failure.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    plan_id = uuid.uuid4().hex
    task_a = "task_a"
    task_b = "task_b"
    tasks = [
        {"id": task_a, "title": "Fail", "agent_type": "fail"},
        {"id": task_b, "title": "Blocked", "agent_type": "dummy", "depends_on": [task_a]},
    ]
    _create_plan(database, session_id, plan_id, tasks)

    class FailExecutor(BaseTaskExecutor):
        async def execute(self, task, emitter, context):
            raise RuntimeError("boom")

    class DummyExecutor(BaseTaskExecutor):
        async def execute(self, task, emitter, context):
            return {"ok": True}

    monkeypatch.setitem(TaskExecutorFactory._executors, "fail", FailExecutor)
    monkeypatch.setitem(TaskExecutorFactory._executors, "dummy", DummyExecutor)

    with get_db(database) as session:
        plan = PlanService(session).get_plan(plan_id)
        assert plan is not None
        emitter = EventEmitter(session_id=session_id)
        executor = ParallelExecutor(
            db=session,
            plan=plan,
            emitter=emitter,
            settings=get_settings(),
            output_dir=str(tmp_path),
            user_message="hi",
            history=[],
            max_concurrent=2,
        )

        async def run() -> None:
            async for _ in executor.execute():
                pass

        asyncio.run(run())

        task_b_record = session.get(Task, task_b)
        assert task_b_record is not None
        assert task_b_record.status == TaskStatus.BLOCKED.value

        blocked_events = [
            event for event in emitter.get_events() if event.type == EventType.TASK_BLOCKED
        ]
        assert blocked_events
        assert blocked_events[0].task_id == task_b
