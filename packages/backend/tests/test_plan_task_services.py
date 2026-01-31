import uuid

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Plan, Session as SessionModel, Task, TaskStatus
from app.db.utils import get_db, transaction_scope
from app.services.plan import PlanService
from app.services.task import TaskService


def _create_plan_with_tasks(database, session_id, plan_id, tasks):
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Plan Session"))
        session.flush()
        PlanService(session).create_plan(
            session_id=session_id,
            goal="Test plan",
            tasks=tasks,
            plan_id=plan_id,
        )


def test_task_dependency_block_and_unblock(tmp_path):
    db_path = tmp_path / "deps.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    plan_id = uuid.uuid4().hex
    task_a = uuid.uuid4().hex
    task_b = uuid.uuid4().hex
    _create_plan_with_tasks(
        database,
        session_id,
        plan_id,
        [
            {"id": task_a, "title": "A"},
            {"id": task_b, "title": "B", "depends_on": [task_a]},
        ],
    )

    with get_db(database) as session:
        service = TaskService(session)
        service.set_status(task_a, TaskStatus.FAILED.value, message="boom")
        session.commit()

    with get_db(database) as session:
        blocked = session.get(Task, task_b)
        assert blocked.status == TaskStatus.BLOCKED.value

    with get_db(database) as session:
        service = TaskService(session)
        service.skip_task(task_a, reason="skip")
        session.commit()

    with get_db(database) as session:
        updated = session.get(Task, task_b)
        assert updated.status == TaskStatus.PENDING.value


def test_abort_session_marks_plans_and_tasks(tmp_path):
    db_path = tmp_path / "abort.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    plan_id = uuid.uuid4().hex
    task_id = uuid.uuid4().hex
    _create_plan_with_tasks(
        database,
        session_id,
        plan_id,
        [{"id": task_id, "title": "Run"}],
    )

    with get_db(database) as session:
        service = TaskService(session)
        service.set_status(task_id, TaskStatus.IN_PROGRESS.value)
        session.commit()

    with get_db(database) as session:
        service = TaskService(session)
        plan_ids = service.abort_session(session_id)
        session.commit()

    assert plan_id in plan_ids

    with get_db(database) as session:
        plan = session.get(Plan, plan_id)
        task = session.get(Task, task_id)
        assert plan.status == "aborted"
        assert task.status == TaskStatus.ABORTED.value
