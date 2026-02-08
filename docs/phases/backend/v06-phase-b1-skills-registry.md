# Phase B1: Skills Registry + Profiles + Guardrails

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: B2, B3, B4

## Goal

Create a Skills Registry system with manifest definitions that describe applicable scenarios, component consistency, data contracts, style profiles, and mobile guardrails for different product types.

## Detailed Tasks

### Task 1: Create Skill Manifest Schema

**Description**: Define the JSON schema for skill manifests.

**Implementation Details**:
- [ ] Define `SkillManifest` dataclass/model
- [ ] Include fields: id, name, version, product_types, doc_tiers, components, state_contract, style_profiles, guardrails, page_roles, model_prefs, priority
- [ ] Add validation for required fields
- [ ] Support relative paths for state_contract templates and guardrail rules

**Files to modify/create**:
- `packages/backend/app/services/skills/__init__.py` (new)

**Acceptance Criteria**:
- [ ] SkillManifest model validates all required fields
- [ ] product_types is a list of valid product type enums
- [ ] model_prefs contains valid role keys (classifier, writer, validator, expander)

### Task 2: Create Skills Registry Service

**Description**: Build a service to load, cache, and query skill manifests.

**Implementation Details**:
- [ ] Create `SkillsRegistry` class
- [ ] Implement `load_manifests(directory)` method
- [ ] Implement `get_skill(skill_id)` method
- [ ] Implement `find_skills(product_type, complexity)` or `select_by_product()` method
- [ ] Add caching for loaded manifests
- [ ] Support hot-reloading for development (optional)

**Files to modify/create**:
- `packages/backend/app/services/skills/__init__.py`

**Acceptance Criteria**:
- [ ] Registry loads all manifests from directory on startup
- [ ] Can retrieve skill by ID
- [ ] Can filter skills by product_type and complexity
- [ ] Returns None for invalid skill IDs

### Task 3: Create Sample Manifest Files

**Description**: Create initial skill manifests for supported product types.

**Implementation Details**:
- [ ] Create `flow-ecommerce-v1.json` manifest
- [ ] Create `flow-booking-v1.json` manifest
- [ ] Create `flow-dashboard-v1.json` manifest
- [ ] Create `static-landing-v1.json` manifest
- [ ] Create `static-invitation-v1.json` manifest (covers invitation/card)
- [ ] Include component lists, style profiles, and guardrail references

**Files to modify/create**:
- `packages/backend/app/services/skills/manifests/flow-ecommerce-v1.json`
- `packages/backend/app/services/skills/manifests/flow-booking-v1.json`
- `packages/backend/app/services/skills/manifests/flow-dashboard-v1.json`
- `packages/backend/app/services/skills/manifests/static-landing-v1.json`
- `packages/backend/app/services/skills/manifests/static-invitation-v1.json`

**Acceptance Criteria**:
- [ ] All manifests validate against SkillManifest schema
- [ ] Flow app manifests include state_contract references
- [ ] Static manifests have empty/no state_contract
- [ ] Manifests reference guardrail rules

### Task 4: Create State Contract Templates

**Description**: Create default state contract templates for Flow App types.

**Implementation Details**:
- [ ] Create `contracts/ecommerce.json` with cart, items, totals schema
- [ ] Create `contracts/booking.json` with booking draft schema
- [ ] Create `contracts/dashboard.json` with data state schema
- [ ] Include shared_state_key, records_key, events_key, and schema definitions

**Files to modify/create**:
- `packages/backend/app/services/skills/contracts/ecommerce.json`
- `packages/backend/app/services/skills/contracts/booking.json`
- `packages/backend/app/services/skills/contracts/dashboard.json`

**Acceptance Criteria**:
- [ ] Contracts define state structure for their product type
- [ ] Include events_key for shared event log
- [ ] Include records structure for submitted data

### Task 5: Add Style Profiles + Guardrails Rules

**Description**: Add internal style profiles and mobile-first guardrail rules.

**Implementation Details**:
- [ ] Create `rules/style-profiles.json` with 6-8 default profiles
- [ ] Create `rules/style-router.json` mapping keywords to profiles
- [ ] Create `rules/mobile-guardrails.json` with hard/soft rules

**Files to modify/create**:
- `packages/backend/app/services/skills/rules/style-profiles.json`
- `packages/backend/app/services/skills/rules/style-router.json`
- `packages/backend/app/services/skills/rules/mobile-guardrails.json`

**Acceptance Criteria**:
- [ ] Style profiles include colors, typography, radius, spacing, layout_patterns
- [ ] Router maps keywords to profiles with a default fallback
- [ ] Guardrails separate critical (hard) vs optimization (soft) rules

## Technical Specifications

### SkillManifest Schema

```python
@dataclass
class ModelPreference:
    classifier: str = "light"
    writer: str = "heavy"
    validator: str = "light"
    expander: str = "mid"
    style_refiner: str = "mid"

@dataclass
class SkillManifest:
    id: str  # e.g., "flow-ecommerce-v1"
    name: str  # e.g., "Flow App - ECommerce"
    version: str  # SemVer
    product_types: List[str]  # ["ecommerce", "booking", "dashboard", "landing", "card", "invitation"]
    doc_tiers: List[str]  # ["checklist", "standard", "extended"]
    components: List[str]  # Component names
    state_contract: Optional[str] = None  # Relative path to contract template
    style_profiles: List[str] = field(default_factory=list)
    guardrails: Optional[str] = None  # Relative path to guardrail rules
    page_roles: List[str] = field(default_factory=list)
    model_prefs: ModelPreference = field(default_factory=ModelPreference)
    priority: int = 0
```

### Sample Manifest (ecommerce)

```json
{
  "id": "flow-ecommerce-v1",
  "name": "Flow App - ECommerce",
  "version": "1.0.0",
  "product_types": ["ecommerce"],
  "doc_tiers": ["checklist", "standard", "extended"],
  "components": ["CartItem", "ProductCard", "OrderSummary", "CheckoutForm"],
  "state_contract": "contracts/ecommerce.json",
  "style_profiles": ["clean-modern", "soft-elegant", "bold-tech"],
  "guardrails": "rules/mobile-guardrails.json",
  "page_roles": ["catalog", "cart", "checkout"],
  "model_prefs": {
    "classifier": "light",
    "writer": "heavy",
    "validator": "light",
    "expander": "mid"
  },
  "priority": 100
}
```

### State Contract Template

```json
{
  "shared_state_key": "instant-coffee:state",
  "records_key": "instant-coffee:records",
  "events_key": "instant-coffee:events",
  "schema": {
    "cart": {
      "items": [],
      "totals": {"subtotal": 0, "tax": 0, "total": 0},
      "currency": "USD"
    }
  },
  "events": ["add_to_cart", "update_qty", "remove_item", "checkout_draft", "submit_order"]
}
```

### API (Internal Service)

```python
class SkillsRegistry:
    def get_skill(self, skill_id: str) -> Optional[SkillManifest]
    def find_skills(self, product_type: str, complexity: str) -> List[SkillManifest]
    def get_state_contract(self, skill_id: str) -> Optional[dict]
    def load_style_profiles(self) -> Dict[str, Any]
    def load_guardrails(self) -> Dict[str, Any]
    def list_all_skills(self) -> List[SkillManifest]
```

## Testing Requirements

- [ ] Unit tests for SkillManifest validation
- [ ] Unit tests for SkillsRegistry loading and querying
- [ ] Tests for manifest file parsing (valid/invalid)
- [ ] Tests for state contract loading

## Notes & Warnings

- Manifest directory should be configurable via environment variable
- State contracts may be missing - handle gracefully and allow LLM to generate
- Model preference values are hints, not strict requirements
- Skills can support multiple product_types (e.g., static-invitation for invitation/card)
