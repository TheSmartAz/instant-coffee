from pathlib import Path

from app.services.data_protocol import DataProtocolGenerator
from app.utils.product_doc import build_data_client_script, build_data_store_script, inject_data_scripts


def test_generate_state_contract_flow_defaults(tmp_path):
    generator = DataProtocolGenerator(output_dir=str(tmp_path), session_id="session-1", db=None)
    contract = generator.generate_state_contract("ecommerce")
    assert contract["shared_state_key"] == "instant-coffee:state"
    assert contract["records_key"] == "instant-coffee:records"
    assert contract["events_key"] == "instant-coffee:events"
    assert isinstance(contract.get("schema"), dict)
    assert isinstance(contract.get("events"), list)
    assert contract["events"]


def test_generate_state_contract_static_minimal(tmp_path):
    generator = DataProtocolGenerator(output_dir=str(tmp_path), session_id="session-1", db=None)
    contract = generator.generate_state_contract("landing")
    assert contract["schema"] == {}
    assert contract["events"] == []


def test_write_shared_assets_creates_files(tmp_path):
    generator = DataProtocolGenerator(output_dir=str(tmp_path), session_id="session-1", db=None)
    contract = generator.generate_state_contract("booking")
    assets = generator.write_shared_assets("booking", contract, include_client=True)
    assert assets.shared_dir.exists()
    assert assets.contract_path.exists()
    assert assets.data_store_path.exists()
    assert assets.data_client_path is not None
    assert assets.data_client_path.exists()
    assert assets.shared_dir == Path(tmp_path) / "session-1" / "shared"


def test_script_generation_contains_expected_markers():
    contract = {
        "shared_state_key": "instant-coffee:state",
        "records_key": "instant-coffee:records",
        "events_key": "instant-coffee:events",
        "schema": {},
        "events": [],
    }
    store_script = build_data_store_script(contract)
    client_script = build_data_client_script("ecommerce", contract)
    assert "InstantCoffeeDataStore" in store_script
    assert "instant-coffee:update" in store_script
    assert "InstantCoffeeDataClient" in client_script


def test_inject_data_scripts_adds_tags():
    html = "<html><head></head><body>Content</body></html>"
    injected = inject_data_scripts(
        html,
        store_src="shared/data-store.js",
        client_src="shared/data-client.js",
    )
    assert "shared/data-store.js" in injected
    assert "shared/data-client.js" in injected
    assert injected.index("data-store.js") < injected.index("data-client.js")
