from app.services.data_protocol import DataProtocolGenerator


def test_contract_includes_runtime_context(tmp_path, monkeypatch):
    monkeypatch.setenv("VITE_API_URL", "http://localhost:8000/")

    generator = DataProtocolGenerator(output_dir=str(tmp_path), session_id="session-ctx", db=None)
    html = generator.prepare_html(
        "<html><head></head><body>ok</body></html>",
        product_doc={
            "structured": {
                "product_type": "ecommerce",
                "state_contract": {
                    "schema": {"cart": {"items": []}},
                    "events": ["add_to_cart"],
                },
            }
        },
        page_slug="index",
    )

    assert "data-store.js" in html

    contract_path = tmp_path / "session-ctx" / "shared" / "state-contract.json"
    contract = __import__("json").loads(contract_path.read_text(encoding="utf-8"))
    assert contract["session_id"] == "session-ctx"
    assert contract["api_base_url"] == "http://localhost:8000"
    assert "data_model" in contract
    assert contract["data_model"]["entities"]
    assert "entity_state_map" in contract
    assert contract["entity_state_map"].get("Cart") == "cart.items"


def test_generated_runtime_uses_api_calls(tmp_path):
    generator = DataProtocolGenerator(output_dir=str(tmp_path), session_id="session-api", db=None)
    generator.write_shared_assets(
        "ecommerce",
        {
            "product_type": "ecommerce",
            "session_id": "session-api",
            "api_base_url": "http://localhost:8000",
            "schema": {"cart": {"items": []}},
            "events": ["add_to_cart"],
            "data_model": {
                "entities": {
                    "CartItem": {
                        "fields": [{"name": "name", "type": "string", "required": True}],
                        "primaryKey": "id",
                    }
                },
                "relations": [],
            },
        },
        include_client=True,
    )

    store_js = (tmp_path / "session-api" / "shared" / "data-store.js").read_text(encoding="utf-8")
    client_js = (tmp_path / "session-api" / "shared" / "data-client.js").read_text(encoding="utf-8")

    assert "fetch(path" in store_js
    assert "/api/sessions/" in store_js
    assert "CONTRACT.session_id" in store_js
    assert "localStorage.setItem(this.recordsKey" in store_js
    assert "localStorage.getItem(this.recordsKey" in store_js
    assert "/data/tables" in store_js
    assert "resolveStatePathForEntity" in store_js
    assert "applyEntityRecordsToState" in store_js
    assert "CONTRACT.entity_state_map" in store_js
    assert "applyEntityRecordsToState(nextState, statePath, tableName, records);" in store_js
    assert "addRecord(cartEntity" in client_js
    assert "addRecord(orderEntity" in client_js


def test_state_contract_schema_fallback_to_data_model(tmp_path):
    generator = DataProtocolGenerator(output_dir=str(tmp_path), session_id="session-fallback", db=None)
    html = generator.prepare_html(
        "<html><head></head><body>ok</body></html>",
        product_doc={
            "structured": {
                "product_type": "travel",
                "state_contract": {
                    "schema": {
                        "trip": {"title": "A", "budget": 123},
                        "activities": [{"name": "hike"}],
                    },
                    "events": ["save_plan"],
                },
            }
        },
    )
    assert "data-client.js" in html

    contract_path = tmp_path / "session-fallback" / "shared" / "state-contract.json"
    contract = __import__("json").loads(contract_path.read_text(encoding="utf-8"))
    entities = contract["data_model"]["entities"]
    assert "Trip" in entities
    assert "Activity" in entities
