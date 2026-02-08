import asyncio

from app.agents.generation import GenerationAgent
from app.config import Settings


def _make_agent() -> GenerationAgent:
    settings = Settings(default_key="test-key", default_base_url="http://localhost")
    return GenerationAgent(None, "session-b8", settings)


class _StoreRecorder:
    def __init__(self, *, fail: bool = False):
        self.enabled = True
        self.fail = fail
        self.calls: list[tuple[str, object]] = []

    async def create_schema(self, session_id: str):
        self.calls.append(("create_schema", session_id))
        if self.fail:
            raise RuntimeError("schema boom")
        return f"app_{session_id}"

    async def create_tables(self, session_id: str, data_model):
        self.calls.append(("create_tables", data_model))
        if self.fail:
            raise RuntimeError("tables boom")
        return {"entities_added": ["Product"]}



def test_generation_provisions_app_data_tables(monkeypatch):
    agent = _make_agent()
    store = _StoreRecorder()
    monkeypatch.setattr("app.agents.generation.get_app_data_store", lambda: store)

    product_doc = {
        "structured": {
            "data_model": {
                "entities": {
                    "Product": {
                        "fields": [{"name": "name", "type": "string", "required": True}],
                        "primaryKey": "id",
                    }
                },
                "relations": [],
            }
        }
    }

    asyncio.run(agent._provision_app_data_tables(product_doc=product_doc))

    assert store.calls[0] == ("create_schema", "session-b8")
    assert store.calls[1][0] == "create_tables"
    dm = store.calls[1][1]
    assert isinstance(dm, dict)
    assert "Product" in dm.get("entities", {})


def test_generation_app_data_failure_is_graceful(monkeypatch):
    agent = _make_agent()
    store = _StoreRecorder(fail=True)
    monkeypatch.setattr("app.agents.generation.get_app_data_store", lambda: store)

    product_doc = {
        "structured": {
            "data_model": {
                "entities": {
                    "Product": {
                        "fields": [{"name": "name", "type": "string", "required": True}],
                        "primaryKey": "id",
                    }
                },
                "relations": [],
            }
        }
    }

    asyncio.run(agent._provision_app_data_tables(product_doc=product_doc))
    assert store.calls == [("create_schema", "session-b8")]


def test_generation_skip_without_data_model(monkeypatch):
    agent = _make_agent()
    store = _StoreRecorder()
    monkeypatch.setattr("app.agents.generation.get_app_data_store", lambda: store)

    product_doc = {"structured": {"state_contract": {"schema": {}}}}
    asyncio.run(agent._provision_app_data_tables(product_doc=product_doc))

    assert store.calls == []
