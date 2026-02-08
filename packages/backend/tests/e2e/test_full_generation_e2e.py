import asyncio
import json
from pathlib import Path

from app.agents.orchestrator import AgentOrchestrator
from app.agents.product_doc import ProductDocAgent, ProductDocGenerateResult
from app.db.models import Session
from app.services.data_protocol import DataProtocolGenerator
from app.services.product_doc import ProductDocService


async def _fake_product_doc_generate(agent_self, *args, **kwargs):
    session_id = kwargs.get("session_id") or agent_self.session_id
    structured = {
        "project_name": "Test Store",
        "product_type": "ecommerce",
        "complexity": "medium",
        "doc_tier": "standard",
        "pages": [
            {"slug": "home", "title": "Home", "role": "catalog"},
            {"slug": "cart", "title": "Cart", "role": "checkout"},
        ],
        "state_contract": {
            "shared_state_key": "instant-coffee:state",
            "records_key": "instant-coffee:records",
            "events_key": "instant-coffee:events",
            "schema": {"cart": {"items": [], "totals": {"subtotal": 0}}},
            "events": ["add_to_cart"],
        },
        "data_flow": [
            {"from_page": "home", "event": "add_to_cart", "to_page": "cart"}
        ],
    }
    service = ProductDocService(agent_self.db)
    existing = service.get_by_session_id(session_id)
    if existing is None:
        service.create(session_id, content="# Doc", structured=structured)
    else:
        service.update(existing.id, content="# Doc", structured=structured)
    return ProductDocGenerateResult(
        content="# Doc",
        structured=structured,
        message="ok",
        tokens_used=0,
    )


async def _fake_run_generation_pipeline(agent_self, **kwargs):
    output_dir = kwargs.get("output_dir")
    product_doc = kwargs.get("product_doc")
    product_type = "ecommerce"
    if product_doc is not None:
        structured = getattr(product_doc, "structured", {})
        if isinstance(structured, dict):
            product_type = structured.get("product_type") or product_type

    generator = DataProtocolGenerator(
        output_dir=output_dir,
        session_id=agent_self.session.id,
        db=agent_self.db,
    )
    contract = generator.generate_state_contract(product_type)
    generator.write_shared_assets(product_type, contract, include_client=True)

    html = "<!doctype html><html><head><title>Test</title></head><body>Hi</body></html>"
    html = generator.inject_scripts_into_page(
        html=html,
        product_type=product_type,
        page_slug="index",
        contract=contract,
    )

    session_dir = Path(output_dir) / agent_self.session.id
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "index.html").write_text(html, encoding="utf-8")

    return {"preview_html": html, "active_page_slug": "index"}


class TestFullGenerationFlowE2E:
    def test_ecommerce_flow_generation(self, test_db, test_settings, output_dir, monkeypatch):
        session = Session(id="e2e-full-gen", title="Full Generation")
        test_db.add(session)
        test_db.commit()

        monkeypatch.setattr(ProductDocAgent, "generate", _fake_product_doc_generate)
        monkeypatch.setattr(AgentOrchestrator, "_run_generation_pipeline", _fake_run_generation_pipeline)

        orchestrator = AgentOrchestrator(test_db, session)

        async def _collect():
            return [
                response
                async for response in orchestrator.stream_responses(
                    user_message="Create an online store with products and cart",
                    output_dir=output_dir,
                    history=[],
                    trigger_interview=False,
                    generate_now=True,
                )
            ]

        responses = asyncio.run(_collect())

        assert responses
        final = responses[-1]
        assert final.preview_html is not None

        contract_path = Path(output_dir) / session.id / "shared" / "state-contract.json"
        assert contract_path.exists()
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        assert "shared_state_key" in contract
        assert "schema" in contract

    def test_multi_page_state_sharing(self, test_db, test_settings, output_dir, monkeypatch):
        session = Session(id="e2e-multi-page", title="Multi Page")
        test_db.add(session)
        test_db.commit()

        monkeypatch.setattr(ProductDocAgent, "generate", _fake_product_doc_generate)
        monkeypatch.setattr(AgentOrchestrator, "_run_generation_pipeline", _fake_run_generation_pipeline)

        orchestrator = AgentOrchestrator(test_db, session)

        async def _run_once():
            return [
                response
                async for response in orchestrator.stream_responses(
                    user_message="Create an ecommerce site with home and cart pages",
                    output_dir=output_dir,
                    history=[],
                    trigger_interview=False,
                    generate_now=True,
                )
            ]

        asyncio.run(_run_once())

        shared_dir = Path(output_dir) / session.id / "shared"
        store_path = shared_dir / "data-store.js"
        client_path = shared_dir / "data-client.js"

        assert store_path.exists()
        assert client_path.exists()

        store_script = store_path.read_text(encoding="utf-8")
        client_script = client_path.read_text(encoding="utf-8")

        assert "InstantCoffeeDataStore" in store_script
        assert "instant-coffee:state" in store_script
        assert "instantcoffeedataclient" in client_script.lower()
