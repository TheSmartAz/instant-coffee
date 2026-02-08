from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

FieldType = Literal["string", "number", "boolean", "array", "object"]
RelationType = Literal["one-to-one", "one-to-many", "many-to-one", "many-to-many"]


class FieldDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: FieldType
    required: bool
    description: Optional[str] = None


class EntityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: List[FieldDefinition]
    primaryKey: str


class Relation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    type: RelationType
    foreignKey: str


class DataModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: Dict[str, EntityDefinition]
    relations: List[Relation]


def _field(name: str, field_type: FieldType, required: bool, description: Optional[str] = None) -> FieldDefinition:
    return FieldDefinition(name=name, type=field_type, required=required, description=description)


def _entity(primary_key: str, fields: List[FieldDefinition]) -> EntityDefinition:
    return EntityDefinition(fields=fields, primaryKey=primary_key)


def _relation(from_entity: str, to_entity: str, relation_type: RelationType, foreign_key: str) -> Relation:
    return Relation(from_=from_entity, to=to_entity, type=relation_type, foreignKey=foreign_key)


def _ecommerce_entities() -> Dict[str, EntityDefinition]:
    return {
        "Product": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("name", "string", True),
                _field("price", "number", True),
                _field("originalPrice", "number", False),
                _field("image", "string", True),
                _field("images", "array", False),
                _field("description", "string", False),
                _field("category_id", "string", True),
                _field("stock", "number", False),
                _field("tags", "array", False),
            ],
        ),
        "Category": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("name", "string", True),
                _field("icon", "string", False),
            ],
        ),
        "CartItem": _entity(
            "product_id",
            [
                _field("order_id", "string", False),
                _field("product_id", "string", True),
                _field("quantity", "number", True),
                _field("selected", "boolean", False),
            ],
        ),
        "Order": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("items", "array", True),
                _field("total", "number", True),
                _field("status", "string", True),
                _field("shippingAddress", "object", False),
                _field("user_id", "string", False),
                _field("created_at", "string", True),
            ],
        ),
        "User": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("name", "string", True),
                _field("avatar", "string", False),
                _field("phone", "string", False),
            ],
        ),
    }


def _ecommerce_relations() -> List[Relation]:
    return [
        _relation("Product", "Category", "many-to-one", "category_id"),
        _relation("CartItem", "Product", "many-to-one", "product_id"),
        _relation("Order", "CartItem", "one-to-many", "order_id"),
        _relation("Order", "User", "many-to-one", "user_id"),
    ]


def _travel_entities() -> Dict[str, EntityDefinition]:
    return {
        "Trip": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("title", "string", True),
                _field("destination", "string", True),
                _field("startDate", "string", True),
                _field("endDate", "string", True),
                _field("coverImage", "string", False),
                _field("description", "string", False),
            ],
        ),
        "DayPlan": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("trip_id", "string", True),
                _field("date", "string", True),
                _field("dayNumber", "number", True),
                _field("title", "string", False),
            ],
        ),
        "Activity": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("day_id", "string", True),
                _field("time", "string", True),
                _field("title", "string", True),
                _field("location_id", "string", False),
                _field("location", "string", False),
                _field("duration", "number", False),
                _field("notes", "string", False),
            ],
        ),
        "Location": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("name", "string", True),
                _field("address", "string", False),
                _field("lat", "number", False),
                _field("lng", "number", False),
                _field("type", "string", False),
            ],
        ),
    }


def _travel_relations() -> List[Relation]:
    return [
        _relation("DayPlan", "Trip", "many-to-one", "trip_id"),
        _relation("Activity", "DayPlan", "many-to-one", "day_id"),
        _relation("Activity", "Location", "many-to-one", "location_id"),
    ]


def _manual_entities() -> Dict[str, EntityDefinition]:
    return {
        "Manual": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("title", "string", True),
                _field("version", "string", False),
                _field("lastUpdated", "string", False),
            ],
        ),
        "Section": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("manual_id", "string", True),
                _field("title", "string", True),
                _field("order", "number", True),
                _field("parent_id", "string", False),
            ],
        ),
        "Page": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("section_id", "string", True),
                _field("title", "string", True),
                _field("content", "string", True),
                _field("order", "number", True),
            ],
        ),
    }


def _manual_relations() -> List[Relation]:
    return [
        _relation("Section", "Manual", "many-to-one", "manual_id"),
        _relation("Section", "Section", "many-to-one", "parent_id"),
        _relation("Page", "Section", "many-to-one", "section_id"),
    ]


def _kanban_entities() -> Dict[str, EntityDefinition]:
    return {
        "Board": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("title", "string", True),
                _field("description", "string", False),
            ],
        ),
        "Column": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("board_id", "string", True),
                _field("title", "string", True),
                _field("order", "number", True),
                _field("color", "string", False),
            ],
        ),
        "Task": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("column_id", "string", True),
                _field("title", "string", True),
                _field("description", "string", False),
                _field("priority", "string", False),
                _field("dueDate", "string", False),
                _field("assignee_id", "string", False),
                _field("order", "number", True),
            ],
        ),
        "User": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("name", "string", True),
                _field("avatar", "string", False),
            ],
        ),
        "Tag": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("name", "string", True),
                _field("color", "string", True),
            ],
        ),
    }


def _kanban_relations() -> List[Relation]:
    return [
        _relation("Column", "Board", "many-to-one", "board_id"),
        _relation("Task", "Column", "many-to-one", "column_id"),
        _relation("Task", "User", "many-to-one", "assignee_id"),
    ]


def _landing_entities() -> Dict[str, EntityDefinition]:
    return {
        "Lead": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("email", "string", True),
                _field("name", "string", False),
                _field("phone", "string", False),
                _field("company", "string", False),
                _field("message", "string", False),
                _field("source", "string", False),
                _field("created_at", "string", True),
            ],
        ),
        "Feature": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("title", "string", True),
                _field("description", "string", True),
                _field("icon", "string", False),
            ],
        ),
        "Testimonial": _entity(
            "id",
            [
                _field("id", "string", True),
                _field("quote", "string", True),
                _field("author", "string", True),
                _field("role", "string", False),
                _field("avatar", "string", False),
            ],
        ),
    }


def _landing_relations() -> List[Relation]:
    return []


class EcommerceModel(DataModel):
    entities: Dict[str, EntityDefinition] = Field(default_factory=_ecommerce_entities)
    relations: List[Relation] = Field(default_factory=_ecommerce_relations)


class TravelModel(DataModel):
    entities: Dict[str, EntityDefinition] = Field(default_factory=_travel_entities)
    relations: List[Relation] = Field(default_factory=_travel_relations)


class ManualModel(DataModel):
    entities: Dict[str, EntityDefinition] = Field(default_factory=_manual_entities)
    relations: List[Relation] = Field(default_factory=_manual_relations)


class KanbanModel(DataModel):
    entities: Dict[str, EntityDefinition] = Field(default_factory=_kanban_entities)
    relations: List[Relation] = Field(default_factory=_kanban_relations)


class LandingModel(DataModel):
    entities: Dict[str, EntityDefinition] = Field(default_factory=_landing_entities)
    relations: List[Relation] = Field(default_factory=_landing_relations)


def get_default_data_model(product_type: str) -> DataModel | None:
    normalized = (product_type or "").strip().lower()
    if normalized == "ecommerce":
        return EcommerceModel()
    if normalized == "travel":
        return TravelModel()
    if normalized == "manual":
        return ManualModel()
    if normalized == "kanban":
        return KanbanModel()
    if normalized in {"landing", "card", "invitation"}:
        return LandingModel()
    return None


__all__ = [
    "DataModel",
    "EntityDefinition",
    "FieldDefinition",
    "Relation",
    "EcommerceModel",
    "TravelModel",
    "ManualModel",
    "KanbanModel",
    "LandingModel",
    "get_default_data_model",
]
