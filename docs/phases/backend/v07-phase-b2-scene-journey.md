# Phase B2: Scene/Journey Capabilities

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel with B1
- **Dependencies**:
  - **Blocked by**: None (can start with B1)
  - **Blocks**: B3 (Component Registry needs data_model)

## Goal

Implement scenario detection rules and structured data models for five supported scenarios: Ecommerce, Travel, Manual, Kanban, and Landing.

## Detailed Tasks

### Task 1: Implement Scenario Detection

**Description**: Create keyword-based scenario detection with confidence scoring

**Implementation Details**:
- [ ] Create `packages/backend/app/services/scenario_detector.py`
- [ ] Implement SCENARIO_KEYWORDS dictionary
- [ ] Add detect_scenario(user_input: str) function
- [ ] Return product_type with confidence score

**Files to create**:
- `packages/backend/app/services/scenario_detector.py`

**Acceptance Criteria**:
- [ ] Detects ecommerce/travel/manual/kanban/landing scenarios
- [ ] Returns confidence score (0-1)
- [ ] Falls back to "simple" when no match

---

### Task 2: Define Scenario Data Model Classes

**Description**: Create Pydantic models for each scenario's data entities and relations

**Implementation Details**:
- [ ] Create `packages/backend/app/schemas/scenario.py`
- [ ] Define DataModel, EntityDefinition, FieldDefinition, Relation classes
- [ ] Create EcommerceModel, TravelModel, ManualModel, KanbanModel, LandingModel subclasses
- [ ] Validate against Appendix A in spec

**Files to create**:
- `packages/backend/app/schemas/scenario.py`

**Acceptance Criteria**:
- [ ] All entity fields match spec Appendix A
- [ ] Relations properly defined
- [ ] Primary key fields marked correctly

---

### Task 3: Update ProductDoc Schema

**Description**: Extend ProductDocStructured to include scene-specific fields

**Implementation Details**:
- [ ] Modify `packages/backend/app/schemas/product_doc.py`
- [ ] Add product_type field with enum values
- [ ] Add complexity field (simple/medium/complex)
- [ ] Update pages definition with role field
- [ ] Add data_model field

**Files to modify**:
- `packages/backend/app/schemas/product_doc.py`

**Acceptance Criteria**:
- [ ] ProductDoc includes product_type enum
- [ ] Complexity classification works
- [ ] PageDefinition includes role field
- [ ] Data model integrates with entities

---

### Task 4: Create Scene Prompts

**Description**: Generate LLM prompts for structured output based on detected scene

**Implementation Details**:
- [ ] Create `packages/backend/app/agents/scene_prompts.py`
- [ ] Add prompt templates for each scenario
- [ ] Include entity fields, relations guidance
- [ ] Add few-shot examples for complex scenarios

**Files to create**:
- `packages/backend/app/agents/scene_prompts.py`

**Acceptance Criteria**:
- [ ] Prompts generate valid JSON
- [ ] Scene-specific components mentioned
- [ ] Data relations properly captured

## Technical Specifications

### Scenario Keywords

```python
SCENARIO_KEYWORDS = {
    "ecommerce": ["商品", "购物车", "下单", "商城", "电商", "store", "cart", "checkout"],
    "travel": ["行程", "旅行", "日程", "景点", "trip", "itinerary", "booking"],
    "manual": ["说明书", "文档", "手册", "指南", "manual", "docs", "guide"],
    "kanban": ["看板", "任务", "项目管理", "board", "task", "kanban"],
    "landing": ["落地页", "宣传页", "首页", "landing", "hero", "cta"]
}
```

### DataModel Interface

```python
from typing import TypedDict, Optional
from pydantic import BaseModel

class DataModel(BaseModel):
    entities: dict[str, EntityDefinition]
    relations: list[Relation]

class EntityDefinition(BaseModel):
    fields: list[FieldDefinition]
    primaryKey: str

class FieldDefinition(BaseModel):
    name: str
    type: str  # "string" | "number" | "boolean" | "array" | "object"
    required: bool
    description: Optional[str] = None

class Relation(BaseModel):
    from_: str
    to: str
    type: str  # "one-to-one" | "one-to-many" | "many-to-one" | "many-to-many"
    foreignKey: str
```

### PageDefinition with Role

```python
class PageDefinition(BaseModel):
    slug: str           # URL 路径
    title: str          # 页面标题
    role: str           # 页面角色 (catalog/detail/checkout/...)
    description: Optional[str] = None
```

### ProductDocStructured Update

```python
class ProductDocStructured(BaseModel):
    product_type: str   # ecommerce/travel/manual/kanban/landing/card/invitation
    complexity: str     # simple/medium/complex
    pages: list[PageDefinition]
    data_model: Optional[DataModel] = None
    # ... existing fields
```

## Testing Requirements

- [ ] Unit test: Scenario detection accuracy
- [ ] Unit test: Data model validation
- [ ] Integration test: Full Brief node with scenario output
- [ ] Test all 5 scenarios with sample inputs

## Notes & Warnings

- Scene detection should be case-insensitive
- Keywords should support both Chinese and English
- Confidence threshold: 0.5 minimum for auto-detection
- Manual override possible via API parameter
