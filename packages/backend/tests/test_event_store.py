import uuid

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Plan, PlanEvent, Session as SessionModel, Task, TaskEvent
from app.db.utils import get_db, transaction_scope
from app.events.models import PlanCreatedEvent, TaskProgressEvent
from app.services.event_store import EventStoreService
from app.services.plan import PlanService


def test_event_store_plan_created_persists_plan(tmp_path):
    db_path = tmp_path / "plan_events.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    plan_id = uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Plan Events"))

    plan_payload = {
        "id": plan_id,
        "goal": "Build demo",
        "tasks": [
            {
                "id": "task-1",
                "title": "Collect requirements",
                "depends_on": [],
                "can_parallel": True,
            }
        ],
    }

    with get_db(database) as session:
        store = EventStoreService(session)
        store.record_event(PlanCreatedEvent(plan=plan_payload, session_id=session_id))
        session.commit()

    with get_db(database) as session:
        plan = session.get(Plan, plan_id)
        assert plan is not None
        assert plan.goal == "Build demo"
        assert session.query(Task).count() == 1
        assert session.query(PlanEvent).count() == 1


def test_event_store_task_event_persists_task_event(tmp_path):
    db_path = tmp_path / "task_events.db"
    database = Database(f"sqlite:///{db_path}")
    init_db(database)

    session_id = uuid.uuid4().hex
    plan_id = uuid.uuid4().hex
    task_id = uuid.uuid4().hex
    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Task Events"))
        session.flush()
        PlanService(session).create_plan(
            session_id=session_id,
            goal="Run task",
            tasks=[{"id": task_id, "title": "Do work"}],
            plan_id=plan_id,
        )

    with get_db(database) as session:
        store = EventStoreService(session)
        store.record_event(TaskProgressEvent(task_id=task_id, progress=42))
        session.commit()

    with get_db(database) as session:
        assert session.query(TaskEvent).count() == 1
