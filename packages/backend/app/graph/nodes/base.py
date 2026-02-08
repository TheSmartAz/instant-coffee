from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class NodeContract:
    name: str
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]

    def all_fields(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self.input_fields + self.output_fields))


NODE_CONTRACTS: dict[str, NodeContract] = {
    "mcp_setup": NodeContract(
        name="mcp_setup",
        input_fields=(),
        output_fields=("mcp_tools",),
    ),
    "refine_gate": NodeContract(
        name="refine_gate",
        input_fields=("user_feedback",),
        output_fields=(),
    ),
    "brief": NodeContract(
        name="brief",
        input_fields=("user_input", "assets"),
        output_fields=("product_doc", "pages", "data_model"),
    ),
    "style_extractor": NodeContract(
        name="style_extractor",
        input_fields=("assets",),
        output_fields=("style_tokens",),
    ),
    "component_registry": NodeContract(
        name="component_registry",
        input_fields=("product_doc", "style_tokens", "pages"),
        output_fields=("component_registry",),
    ),
    "generate": NodeContract(
        name="generate",
        input_fields=("component_registry", "pages", "data_model"),
        output_fields=("page_schemas", "data_model_migration"),
    ),
    "aesthetic_scorer": NodeContract(
        name="aesthetic_scorer",
        input_fields=("page_schemas", "style_tokens"),
        output_fields=("aesthetic_scores", "aesthetic_suggestions"),
    ),
    "refine": NodeContract(
        name="refine",
        input_fields=("page_schemas", "user_feedback", "aesthetic_suggestions"),
        output_fields=("page_schemas",),
    ),
    "verify": NodeContract(
        name="verify",
        input_fields=(
            "page_schemas",
            "component_registry",
            "build_status",
            "build_artifacts",
            "error",
            "verify_report",
            "verify_blocked",
        ),
        output_fields=("verify_report", "verify_blocked"),
    ),
    "render": NodeContract(
        name="render",
        input_fields=("session_id", "page_schemas", "component_registry", "style_tokens", "assets"),
        output_fields=("build_artifacts", "build_status"),
    ),
}


def list_node_contracts() -> tuple[NodeContract, ...]:
    return tuple(NODE_CONTRACTS.values())


def validate_contract_fields(state_fields: Iterable[str]) -> dict[str, list[str]]:
    field_set = set(state_fields)
    missing: dict[str, list[str]] = {}
    for name, contract in NODE_CONTRACTS.items():
        absent = [field for field in contract.all_fields() if field not in field_set]
        if absent:
            missing[name] = absent
    return missing


__all__ = ["NodeContract", "NODE_CONTRACTS", "list_node_contracts", "validate_contract_fields"]
