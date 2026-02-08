from app.schemas.scenario import EcommerceModel, KanbanModel, LandingModel, ManualModel, TravelModel


def _field(name: str, field_type: str, required: bool) -> dict:
    return {"name": name, "type": field_type, "required": required}


def test_ecommerce_model_matches_spec():
    expected = {
        "entities": {
            "Product": {
                "fields": [
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
                "primaryKey": "id",
            },
            "Category": {
                "fields": [
                    _field("id", "string", True),
                    _field("name", "string", True),
                    _field("icon", "string", False),
                ],
                "primaryKey": "id",
            },
            "CartItem": {
                "fields": [
                    _field("order_id", "string", False),
                    _field("product_id", "string", True),
                    _field("quantity", "number", True),
                    _field("selected", "boolean", False),
                ],
                "primaryKey": "product_id",
            },
            "Order": {
                "fields": [
                    _field("id", "string", True),
                    _field("items", "array", True),
                    _field("total", "number", True),
                    _field("status", "string", True),
                    _field("shippingAddress", "object", False),
                    _field("user_id", "string", False),
                    _field("created_at", "string", True),
                ],
                "primaryKey": "id",
            },
            "User": {
                "fields": [
                    _field("id", "string", True),
                    _field("name", "string", True),
                    _field("avatar", "string", False),
                    _field("phone", "string", False),
                ],
                "primaryKey": "id",
            },
        },
        "relations": [
            {"from": "Product", "to": "Category", "type": "many-to-one", "foreignKey": "category_id"},
            {"from": "CartItem", "to": "Product", "type": "many-to-one", "foreignKey": "product_id"},
            {"from": "Order", "to": "CartItem", "type": "one-to-many", "foreignKey": "order_id"},
            {"from": "Order", "to": "User", "type": "many-to-one", "foreignKey": "user_id"},
        ],
    }
    model = EcommerceModel().model_dump(by_alias=True, exclude_none=True)
    assert model == expected


def test_travel_model_matches_spec():
    expected = {
        "entities": {
            "Trip": {
                "fields": [
                    _field("id", "string", True),
                    _field("title", "string", True),
                    _field("destination", "string", True),
                    _field("startDate", "string", True),
                    _field("endDate", "string", True),
                    _field("coverImage", "string", False),
                    _field("description", "string", False),
                ],
                "primaryKey": "id",
            },
            "DayPlan": {
                "fields": [
                    _field("id", "string", True),
                    _field("trip_id", "string", True),
                    _field("date", "string", True),
                    _field("dayNumber", "number", True),
                    _field("title", "string", False),
                ],
                "primaryKey": "id",
            },
            "Activity": {
                "fields": [
                    _field("id", "string", True),
                    _field("day_id", "string", True),
                    _field("time", "string", True),
                    _field("title", "string", True),
                    _field("location_id", "string", False),
                    _field("location", "string", False),
                    _field("duration", "number", False),
                    _field("notes", "string", False),
                ],
                "primaryKey": "id",
            },
            "Location": {
                "fields": [
                    _field("id", "string", True),
                    _field("name", "string", True),
                    _field("address", "string", False),
                    _field("lat", "number", False),
                    _field("lng", "number", False),
                    _field("type", "string", False),
                ],
                "primaryKey": "id",
            },
        },
        "relations": [
            {"from": "DayPlan", "to": "Trip", "type": "many-to-one", "foreignKey": "trip_id"},
            {"from": "Activity", "to": "DayPlan", "type": "many-to-one", "foreignKey": "day_id"},
            {"from": "Activity", "to": "Location", "type": "many-to-one", "foreignKey": "location_id"},
        ],
    }
    model = TravelModel().model_dump(by_alias=True, exclude_none=True)
    assert model == expected


def test_manual_model_matches_spec():
    expected = {
        "entities": {
            "Manual": {
                "fields": [
                    _field("id", "string", True),
                    _field("title", "string", True),
                    _field("version", "string", False),
                    _field("lastUpdated", "string", False),
                ],
                "primaryKey": "id",
            },
            "Section": {
                "fields": [
                    _field("id", "string", True),
                    _field("manual_id", "string", True),
                    _field("title", "string", True),
                    _field("order", "number", True),
                    _field("parent_id", "string", False),
                ],
                "primaryKey": "id",
            },
            "Page": {
                "fields": [
                    _field("id", "string", True),
                    _field("section_id", "string", True),
                    _field("title", "string", True),
                    _field("content", "string", True),
                    _field("order", "number", True),
                ],
                "primaryKey": "id",
            },
        },
        "relations": [
            {"from": "Section", "to": "Manual", "type": "many-to-one", "foreignKey": "manual_id"},
            {"from": "Section", "to": "Section", "type": "many-to-one", "foreignKey": "parent_id"},
            {"from": "Page", "to": "Section", "type": "many-to-one", "foreignKey": "section_id"},
        ],
    }
    model = ManualModel().model_dump(by_alias=True, exclude_none=True)
    assert model == expected


def test_kanban_model_matches_spec():
    expected = {
        "entities": {
            "Board": {
                "fields": [
                    _field("id", "string", True),
                    _field("title", "string", True),
                    _field("description", "string", False),
                ],
                "primaryKey": "id",
            },
            "Column": {
                "fields": [
                    _field("id", "string", True),
                    _field("board_id", "string", True),
                    _field("title", "string", True),
                    _field("order", "number", True),
                    _field("color", "string", False),
                ],
                "primaryKey": "id",
            },
            "Task": {
                "fields": [
                    _field("id", "string", True),
                    _field("column_id", "string", True),
                    _field("title", "string", True),
                    _field("description", "string", False),
                    _field("priority", "string", False),
                    _field("dueDate", "string", False),
                    _field("assignee_id", "string", False),
                    _field("order", "number", True),
                ],
                "primaryKey": "id",
            },
            "User": {
                "fields": [
                    _field("id", "string", True),
                    _field("name", "string", True),
                    _field("avatar", "string", False),
                ],
                "primaryKey": "id",
            },
            "Tag": {
                "fields": [
                    _field("id", "string", True),
                    _field("name", "string", True),
                    _field("color", "string", True),
                ],
                "primaryKey": "id",
            },
        },
        "relations": [
            {"from": "Column", "to": "Board", "type": "many-to-one", "foreignKey": "board_id"},
            {"from": "Task", "to": "Column", "type": "many-to-one", "foreignKey": "column_id"},
            {"from": "Task", "to": "User", "type": "many-to-one", "foreignKey": "assignee_id"},
        ],
    }
    model = KanbanModel().model_dump(by_alias=True, exclude_none=True)
    assert model == expected


def test_landing_model_matches_spec():
    expected = {
        "entities": {
            "Lead": {
                "fields": [
                    _field("id", "string", True),
                    _field("email", "string", True),
                    _field("name", "string", False),
                    _field("phone", "string", False),
                    _field("company", "string", False),
                    _field("message", "string", False),
                    _field("source", "string", False),
                    _field("created_at", "string", True),
                ],
                "primaryKey": "id",
            },
            "Feature": {
                "fields": [
                    _field("id", "string", True),
                    _field("title", "string", True),
                    _field("description", "string", True),
                    _field("icon", "string", False),
                ],
                "primaryKey": "id",
            },
            "Testimonial": {
                "fields": [
                    _field("id", "string", True),
                    _field("quote", "string", True),
                    _field("author", "string", True),
                    _field("role", "string", False),
                    _field("avatar", "string", False),
                ],
                "primaryKey": "id",
            },
        },
        "relations": [],
    }
    model = LandingModel().model_dump(by_alias=True, exclude_none=True)
    assert model == expected
