from pathlib import Path

from app.services.data_protocol import DataProtocolGenerator


class TestDataProtocolE2E:
    def test_flow_app_generates_state_contract(self, tmp_path):
        generator = DataProtocolGenerator(
            output_dir=str(tmp_path),
            session_id="flow-session",
            db=None,
        )

        contract = generator.generate_state_contract("ecommerce")

        assert contract["shared_state_key"] == "instant-coffee:state"
        assert contract["records_key"] == "instant-coffee:records"
        assert contract["events_key"] == "instant-coffee:events"
        assert contract["schema"]
        assert contract["events"]

    def test_static_app_generates_minimal_contract(self, tmp_path):
        generator = DataProtocolGenerator(
            output_dir=str(tmp_path),
            session_id="static-session",
            db=None,
        )

        contract = generator.generate_state_contract("landing")

        assert contract["schema"] == {}
        assert contract["events"] == []

    def test_write_shared_assets_creates_files(self, tmp_path):
        generator = DataProtocolGenerator(
            output_dir=str(tmp_path),
            session_id="asset-session",
            db=None,
        )
        contract = generator.generate_state_contract("ecommerce")
        assets = generator.write_shared_assets("ecommerce", contract, include_client=True)

        assert assets.contract_path.exists()
        assert assets.data_store_path.exists()
        assert assets.data_client_path is not None
        assert assets.data_client_path.exists()

        store_script = assets.data_store_path.read_text(encoding="utf-8")
        assert "InstantCoffeeDataStore" in store_script
        assert "instant-coffee:state" in store_script
        assert "localStorage" in store_script

    def test_inject_data_scripts_adds_tags(self, tmp_path):
        generator = DataProtocolGenerator(
            output_dir=str(tmp_path),
            session_id="inject-session",
            db=None,
        )
        contract = generator.generate_state_contract("ecommerce")
        html = "<!doctype html><html><head><title>Test</title></head><body>Hi</body></html>"
        injected = generator.inject_scripts_into_page(
            html=html,
            product_type="ecommerce",
            page_slug="index",
            contract=contract,
        )

        assert "__instantCoffeeContract" in injected
        assert "shared/data-store.js" in injected
        assert "shared/data-client.js" in injected
