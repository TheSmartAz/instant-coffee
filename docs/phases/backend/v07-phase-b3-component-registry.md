# Phase B3: Component Registry Node

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ✅ Can develop in parallel with B1, B2
- **Dependencies**:
  - **Blocked by**: B1 (GraphState required), B2 (data_model required)
  - **Blocks**: B4 (Generate needs component_registry)

## Goal

Implement the Component Registry Node that generates unified component specifications and enforces component consistency across all pages.

## Detailed Tasks

### Task 1: Create Component Registry Schema

**Description**: Define data structures for component definitions, props, and design tokens

**Implementation Details**:
- [ ] Create `packages/backend/app/schemas/component.py`
- [ ] Define ComponentRegistry, ComponentDefinition, PropDefinition, DesignTokens classes
- [ ] Add slots, variants, default values support
- [ ] Include token normalization from style_tokens

**Files to create**:
- `packages/backend/app/schemas/component.py`

**Acceptance Criteria**:
- [ ] ComponentRegistry matches spec section 5.4
- [ ] DesignTokens has radius/spacing/shadow enums
- [ ] Props support asset and binding types

---

### Task 2: Implement Component Registry LLM Node

**Description**: Create the component_registry_node that generates component specifications

**Implementation Details**:
- [ ] Create `packages/backend/app/graph/nodes/component_registry.py`
- [ ] Implement component_registry_node(state) function
- [ ] Use LLM to generate component definitions based on product_doc
- [ ] Map style_tokens to DesignTokens
- [ ] Ensure all page components are covered

**Files to create**:
- `packages/backend/app/graph/nodes/component_registry.py`

**Acceptance Criteria**:
- [ ] Generates complete component_registry for all pages
- [ ] DesignTokens derived from style_tokens
- [ ] Components match page requirements

---

### Task 3: Implement Component Validation

**Description**: Create validation function to ensure page schemas only use registered components

**Implementation Details**:
- [ ] Create `packages/backend/app/services/component_validator.py`
- [ ] Implement validate_page_schema(schema, registry) -> list[str]
- [ ] Implement auto_fix_unknown_components(schema, registry)
- [ ] Add fuzzy matching for similar component names

**Files to create**:
- `packages/backend/app/services/component_validator.py`

**Acceptance Criteria**:
- [ ] Returns list of errors for unregistered components
- [ ] Supports nested component validation
- [ ] Auto-fix replaces unknown with closest match

---

### Task 4: Integrate with Generate Node

**Description**: Wire component_registry output to Generate node input

**Implementation Details**:
- [ ] Update `packages/backend/app/graph/nodes/generate.py`
- [ ] Require component_registry in input state
- [ ] Output page_schemas referencing registered components
- [ ] Call validation before completing node

**Files to modify**:
- `packages/backend/app/graph/nodes/generate.py`

**Acceptance Criteria**:
- [ ] Generate node uses component_registry
- [ ] Validation runs on output page_schemas
- [ ] Errors propagated to state if validation fails

## Technical Specifications

### ComponentRegistry Schema

```python
from typing import TypedDict, Optional, List

class ComponentRegistry(TypedDict):
    components: List[ComponentDefinition]
    tokens: DesignTokens

class ComponentDefinition(TypedDict):
    id: str           # nav-primary, card-product
    type: str         # nav, card, hero, form, list, ...
    slots: List[str]  # 可填充的插槽
    props: List[PropDefinition]
    variants: Optional[List[str]]  # 可选变体

class PropDefinition(TypedDict):
    name: str
    type: str  # "string" | "number" | "boolean" | "asset" | "binding"
    required: bool
    default: Optional[Any]

class DesignTokens(TypedDict):
    radius: str       # "none" | "small" | "medium" | "large"
    spacing: str      # "compact" | "normal" | "airy"
    shadow: str       # "none" | "subtle" | "medium" | "strong"
```

### Pre-defined Component Library

| 组件 ID | 类型 | 用途 | 映射 React 组件 |
|---------|------|------|----------------|
| `nav-primary` | nav | 主导航栏 | `@/components/Nav` |
| `nav-bottom` | nav | 底部导航 | `@/components/BottomNav` |
| `hero-banner` | hero | 首屏横幅 | `@/components/Hero` |
| `card-product` | card | 商品卡片 | `@/components/ProductCard` |
| `card-task` | card | 任务卡片 | `@/components/TaskCard` |
| `card-timeline` | card | 时间轴卡片 | `@/components/TimelineCard` |
| `list-simple` | list | 简单列表 | `@/components/SimpleList` |
| `list-grid` | list | 网格列表 | `@/components/GridList` |
| `form-basic` | form | 基础表单 | `@/components/BasicForm` |
| `form-checkout` | form | 结算表单 | `@/components/CheckoutForm` |
| `button-primary` | button | 主按钮 | `@/components/Button` |
| `button-secondary` | button | 次按钮 | `@/components/Button` |
| `section-header` | section | 区块标题 | `@/components/SectionHeader` |
| `cart-summary` | summary | 购物车摘要 | `@/components/CartSummary` |
| `order-summary` | summary | 订单摘要 | `@/components/OrderSummary` |
| `footer-simple` | footer | 简单页脚 | `@/components/Footer` |
| `breadcrumb` | nav | 面包屑 | `@/components/Breadcrumb` |
| `tabs-basic` | tabs | 基础标签页 | `@/components/Tabs` |
| `modal-confirm` | modal | 确认弹窗 | `@/components/ConfirmModal` |
| `toast-message` | toast | 消息提示 | `@/components/Toast` |

### Validation Function

```python
def validate_page_schema(schema: dict, registry: dict) -> List[str]:
    """校验页面 schema 中的组件是否都在注册表中"""
    errors = []
    registered_ids = {c["id"] for c in registry["components"]}

    def check_component(comp: dict, path: str):
        if comp["id"] not in registered_ids:
            errors.append(f"{path}: 未注册的组件 '{comp['id']}'")
        for i, child in enumerate(comp.get("children", [])):
            check_component(child, f"{path}.children[{i}]")

    for i, comp in enumerate(schema["components"]):
        check_component(comp, f"components[{i}]")

    return errors
```

## Testing Requirements

- [ ] Unit test: ComponentRegistry generation
- [ ] Unit test: Component validation with registered/unregistered components
- [ ] Unit test: DesignTokens normalization from style_tokens
- [ ] Integration test: End-to-end with Generate node
- [ ] Test all 5 scenarios for component coverage

## Notes & Warnings

- At least 20 pre-defined components required
- All generated components must reference registry
- Registry should be cached per session
- Component IDs use kebab-case convention
