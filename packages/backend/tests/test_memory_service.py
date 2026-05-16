import uuid

from app.db.database import Database
from app.db.migrations import init_db
from app.db.models import Session as SessionModel
from app.db.utils import get_db, transaction_scope
from app.services.memory import ProjectMemoryService


def test_project_memory_extracts_architecture_contract_and_test_notes(tmp_path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'memory.db'}")
    init_db(database)
    session_id = uuid.uuid4().hex

    with transaction_scope(database) as session:
        session.add(SessionModel(id=session_id, title="Memory Test"))

    tool_calls = [
        {
            "name": "write_file",
            "arguments": '{"file_path":"packages/backend/app/api/runs.py","content":"#fff"}',
        },
        {
            "name": "edit_file",
            "arguments": '{"file_path":"packages/web/src/types/index.ts","old_string":"a","new_string":"b"}',
        },
        {
            "name": "write_file",
            "arguments": '{"file_path":"packages/backend/tests/test_runs_api.py","content":"pytest"}',
        },
        {
            "name": "shell",
            "arguments": '{"command":"PYTHONPATH=.:../agent/src python -m pytest tests/test_runs_api.py -q"}',
        },
    ]

    with get_db(database) as session:
        service = ProjectMemoryService(session)
        service.extract_and_save_decisions(session_id, tool_calls)
        summary = service.build_memory_summary(session_id)

    assert "architecture_notes" in summary
    assert "packages/backend/app/api/runs.py" in summary["architecture_notes"]
    assert "interface_contracts" in summary
    assert "packages/web/src/types/index.ts" in summary["interface_contracts"]
    assert "testing_notes" in summary
    assert "Uses pytest for backend verification" in summary["testing_notes"]
    assert "packages/backend/tests/test_runs_api.py" in summary["testing_notes"]
