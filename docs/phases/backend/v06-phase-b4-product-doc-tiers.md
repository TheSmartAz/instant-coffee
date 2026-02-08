# Phase B4: Product Doc Tiers

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B1 (Skills Registry)
  - **Blocks**: B2

## Goal

Implement structured product document output with three tiers (Checklist, Standard, Extended) based on complexity, ensuring all output includes structured fields for downstream agent consumption.

## Detailed Tasks

### Task 1: Define Tier Output Schemas

**Description**: Create Pydantic models for each document tier.

**Implementation Details**:
- [ ] Create base `ProductDocStructured` model
- [ ] Create `ProductDocChecklist` for simple outputs
- [ ] Create `ProductDocStandard` for medium complexity
- [ ] Create `ProductDocExtended` for complex products
- [ ] Include routing metadata fields

**Files to modify/create**:
- `packages/backend/app/schemas/product_doc.py` (update)
- `packages/backend/app/services/product_doc.py` (update)

**Acceptance Criteria**:
- [ ] All tiers share base fields (product_type, complexity, doc_tier)
- [ ] Checklist tier has minimal structure
- [ ] Standard tier includes pages, data_flow, state_contract
- [ ] Extended tier supports mermaid and multi-doc

### Task 2: Implement Tier Selection Logic

**Description**: Create service to select appropriate tier based on complexity.

**Implementation Details**:
- [ ] Add `select_tier(product_type, complexity)` method
- [ ] Landing/card/invitation → checklist
- [ ] Simple flow app → checklist
- [ ] Medium flow app → standard
- [ ] Complex flow app → extended
- [ ] Allow manual override via request

**Files to modify/create**:
- `packages/backend/app/services/product_doc.py`

**Acceptance Criteria**:
- [ ] Correct tier selected for each product type/complexity combo
- [ ] Manual override takes precedence
- [ ] Selection logged to session metadata

### Task 3: Update ProductDoc Agent for Tiered Output

**Description**: Modify ProductDoc agent to generate tier-specific documents.

**Implementation Details**:
- [ ] Update agent prompt to accept doc_tier parameter
- [ ] Create tier-specific prompt templates
- [ ] Implement structured output parsing
- [ ] Handle mermaid diagram generation for extended tier
- [ ] Validate output against tier schema

**Files to modify/create**:
- `packages/backend/app/agents/product_doc.py`
- `packages/backend/app/agents/prompts.py` (add tier prompts)

**Acceptance Criteria**:
- [ ] Checklist output: goal + core points + constraints
- [ ] Standard output: full structured doc + data flow
- [ ] Extended output: standard + mermaid + detailed specs
- [ ] All outputs parse into respective schemas

### Task 4: Add Structured Field Output

**Description**: Ensure all document tiers output structured JSON fields.

**Implementation Details**:
- [ ] Add `pages` list with slug and role
- [ ] Add `data_flow` list for cross-page events
- [ ] Add `state_contract` for flow apps
- [ ] Add `style_reference` field
- [ ] Add `component_inventory` list

**Files to modify/create**:
- `packages/backend/app/schemas/product_doc.py`
- `packages/backend/app/agents/product_doc.py`

**Acceptance Criteria**:
- [ ] All structured fields present in output (even if empty)
- [ ] Pages include slug and role fields
- [ ] Data flow includes from, event, to
- [ ] State contract includes keys and schema

### Task 5: Implement Mermaid Diagram Support

**Description**: Add mermaid diagram generation for extended tier.

**Implementation Details**:
- [ ] Generate page flow diagrams
- [ ] Generate data flow diagrams
- [ ] Generate component hierarchy diagrams
- [ ] Embed mermaid code in document output
- [ ] Validate mermaid syntax

**Files to modify/create**:
- `packages/backend/app/agents/product_doc.py`

**Acceptance Criteria**:
- [ ] Extended tier includes mermaid diagrams
- [ ] Page flow shows navigation between pages
- [ ] Data flow shows event propagation
- [ ] Mermaid syntax is valid

## Technical Specifications

### ProductDocStructured (Base)

```python
class PageInfo(BaseModel):
    slug: str
    role: str  # catalog, checkout, profile, etc.
    title: Optional[str] = None

class DataFlow(BaseModel):
    from_page: str
    event: str  # add_to_cart, submit_booking, etc.
    to_page: str

class StateContract(BaseModel):
    shared_state_key: str = "instant-coffee:state"
    records_key: str = "instant-coffee:records"
    events_key: str = "instant-coffee:events"
    schema: Dict[str, Any]

class StyleReferenceInfo(BaseModel):
    mode: str  # full_mimic, style_only
    scope: Dict[str, Any]
    images: List[str]  # Image IDs

class ProductDocStructured(BaseModel):
    product_type: str  # ecommerce, booking, dashboard, landing, card, invitation
    complexity: str  # simple, medium, complex
    doc_tier: str  # checklist, standard, extended
    goal: str
    pages: List[PageInfo] = []
    data_flow: List[DataFlow] = []
    state_contract: Optional[StateContract] = None
    style_reference: Optional[StyleReferenceInfo] = None
    component_inventory: List[str] = []
```

### Tier-Specific Models

```python
class ProductDocChecklist(ProductDocStructured):
    """Minimal output for simple products"""
    core_points: List[str]
    constraints: List[str]

class ProductDocStandard(ProductDocStructured):
    """Standard output for medium complexity"""
    users: List[str]
    user_stories: List[str]
    components: List[str]
    data_flow_explanation: str

class ProductDocExtended(ProductDocStandard):
    """Extended output for complex products"""
    mermaid_page_flow: Optional[str] = None
    mermaid_data_flow: Optional[str] = None
    detailed_specs: List[str]
    appendices: List[str] = []
```

### Tier Selection Logic

```python
def select_doc_tier(product_type: str, complexity: str) -> str:
    # Static/Showcase types always checklist
    if product_type in ["landing", "card", "invitation"]:
        return "checklist"

    # Flow apps by complexity
    if complexity == "simple":
        return "checklist"
    elif complexity == "medium":
        return "standard"
    else:  # complex
        return "extended"
```

### Agent Prompt Template (Standard)

```
Generate a product document for: {product_type} ({complexity})

Document tier: {doc_tier}

Include structured sections:
- Goal (what this product does)
- Users (who will use it)
- Page structure (list with slugs and roles)
- Data flow (cross-page events)
- State contract (for flow apps)
- Component inventory (shared components)

Output must be valid JSON matching the {doc_tier} schema.
```

## Testing Requirements

- [ ] Unit tests for tier selection logic
- [ ] Unit tests for schema validation
- [ ] Integration tests for agent output parsing
- [ ] Tests for mermaid diagram validity
- [ ] Tests for each tier output format

## Notes & Warnings

- Structured fields must always be present (even if empty lists)
- Mermaid diagrams should be validated for syntax
- Extended tier mermaid is optional - don't block if generation fails
- State contract only for flow apps (ecommerce, booking, dashboard)
- Checklist tier should still include structured fields for downstream use
