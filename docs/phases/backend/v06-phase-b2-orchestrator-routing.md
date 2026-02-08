# Phase B2: Orchestrator Routing + Style/Guardrail Injection

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B1 (Skills Registry), B4 (Product Doc Tiers)
  - **Blocks**: B5, B6, B7

## Goal

Implement the Orchestrator routing logic that classifies user input, evaluates complexity, selects the appropriate skill, style profile, guardrails, document tier, and model route before generation.

## Detailed Tasks

### Task 1: Product Type Classification

**Description**: Implement classification logic to identify product type from user input.

**Implementation Details**:
- [ ] Create `ProductClassifier` agent/service
- [ ] Support product types: ecommerce, booking, dashboard, landing, card, invitation
- [ ] Use LLM for classification (light model)
- [ ] Return type + confidence score
- [ ] Handle ambiguous inputs with default fallback

**Files to modify/create**:
- `packages/backend/app/agents/classifier.py` (new file)
- `packages/backend/app/agents/orchestrator/routing.py` (new file)

**Acceptance Criteria**:
- [ ] Classifies "I want an online store" as ecommerce
- [ ] Classifies "Make a booking page" as booking
- [ ] Classifies "Create a landing page" as landing
- [ ] Returns confidence score >= 0.7 for clear inputs

### Task 2: Complexity Evaluation

**Description**: Implement complexity evaluation based on input analysis.

**Implementation Details**:
- [ ] Create `ComplexityEvaluator` class
- [ ] Evaluate dimensions: page count, cross-page data flow, forms, data structure
- [ ] Return complexity level: simple, medium, complex
- [ ] Use heuristic rules + LLM judgment

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator/complexity.py` (new file)

**Acceptance Criteria**:
- [ ] Single page showcase = simple
- [ ] Multi-page with forms = medium
- [ ] Multi-page with complex data flow = complex
- [ ] Returns structured complexity report

### Task 3: @Page Target Parsing

**Description**: Parse and resolve @Page mentions in user input.

**Implementation Details**:
- [ ] Create `PageTargetResolver` class
- [ ] Parse @Page syntax (e.g., "@Home", "@Cart")
- [ ] Match against existing project pages
- [ ] Return list of target page slugs
- [ ] Handle partial matches and case sensitivity

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator/targets.py` (new file)

**Acceptance Criteria**:
- [ ] Extracts "@Home" from "Update @Home with new hero"
- [ ] Returns empty list when no @Page found
- [ ] Validates page exists in project
- [ ] Handles multiple @Page mentions

### Task 4: Skill Selection

**Description**: Select appropriate skill based on product type and complexity.

**Implementation Details**:
- [ ] Integrate with SkillsRegistry (B1)
- [ ] Select skill matching product_type
- [ ] Consider complexity for skill variant selection
- [ ] Fallback to generic skill if no match found
- [ ] Log selection reasoning

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator/skill_selector.py` (new file)

**Acceptance Criteria**:
- [ ] ecommerce + any complexity → flow-ecommerce-v1
- [ ] landing + simple → static-landing-v1
- [ ] invitation/card + simple → static-invitation-v1
- [ ] Returns valid skill or None with reason

### Task 5: Style Profile Routing

**Description**: Route user style preferences to a style profile.

**Implementation Details**:
- [ ] Load style router + profiles from Skills Registry (B1)
- [ ] Match user keywords to profile
- [ ] Default to clean-modern when no match
- [ ] Record selected profile in routing decision

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py` (update)

**Acceptance Criteria**:
- [ ] "luxury spa" → soft-elegant
- [ ] "AI analytics dashboard" → bold-tech
- [ ] No keywords → clean-modern

### Task 6: Guardrail Injection

**Description**: Load and inject mobile guardrails into generation context.

**Implementation Details**:
- [ ] Load guardrails referenced by the selected skill
- [ ] Pass hard/soft rules to ProductDoc + Generation prompts
- [ ] Ensure guardrails are internal-only (not surfaced to users)

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py` (update)
- `packages/backend/app/agents/product_doc.py` (update)
- `packages/backend/app/agents/generation.py` (update)

**Acceptance Criteria**:
- [ ] Guardrails appear in internal context
- [ ] Hard rules influence validator behavior
- [ ] No guardrail metadata is exposed in client responses

### Task 7: Document Tier Selection

**Description**: Select appropriate document tier based on complexity.

**Implementation Details**:
- [ ] Create `DocTierSelector` class
- [ ] Map complexity to tier: simple→checklist, medium→standard, complex→extended
- [ ] Consider product type override (landing always checklist)
- [ ] Return tier + reasoning

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator/doc_tier.py` (new file)

**Acceptance Criteria**:
- [ ] Landing/card/invitation → checklist
- [ ] Simple flow app → checklist
- [ ] Medium flow app → standard
- [ ] Complex flow app → extended

### Task 8: Routing Orchestration

**Description**: Combine all routing steps into unified Orchestrator update.

**Implementation Details**:
- [ ] Update `Orchestrator.run()` method
- [ ] Execute routing before generation
- [ ] Store routing decisions in session metadata
- [ ] Pass decisions to downstream agents
- [ ] Handle routing failures gracefully

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py` (update)

**Acceptance Criteria**:
- [ ] Routing completes before generation starts
- [ ] All decisions logged to session
- [ ] Generation uses selected skill and tier
- [ ] Failure falls back to default behavior

## Technical Specifications

### Routing Flow

```python
@dataclass
class RoutingDecision:
    product_type: str
    complexity: str
    skill_id: str
    style_profile: str
    guardrails: Dict[str, Any]
    doc_tier: str
    target_pages: List[str]
    confidence: float
    reasoning: str

class OrchestratorRouter:
    async def route(self, user_input: str, project: Project) -> RoutingDecision:
        # 1. Parse targets (@Page)
        targets = self.target_resolver.parse(user_input, project.pages)

        # 2. Classify product type
        product_type = await self.classifier.classify(user_input)

        # 3. Evaluate complexity
        complexity = await self.complexity.evaluate(user_input, product_type)

        # 4. Select skill
        skill = self.skill_selector.select(product_type, complexity)

        # 5. Route style profile
        style_profile = self.style_router.route(user_input)

        # 6. Load guardrails
        guardrails = self.guardrails_loader.load(skill)

        # 7. Select doc tier
        doc_tier = self.doc_tier_selector.select(product_type, complexity)

        return RoutingDecision(...)
```

### Product Type Classification Prompt

```
You are a product type classifier. Given the user request, classify into one of:
- ecommerce: Online store, shopping, product catalog, cart, checkout
- booking: Appointment booking, reservation, scheduling
- dashboard: Data visualization, analytics, admin panel
- landing: Landing page, marketing page, product showcase
- card: Greeting card, invitation, single-page graphic
- invitation: Event invitation, RSVP

Return JSON: {"type": "...", "confidence": 0.0-1.0, "reasoning": "..."}
```

### Complexity Evaluation Dimensions

```python
@dataclass
class ComplexityReport:
    level: str  # simple, medium, complex
    page_count_estimate: int
    has_cross_page_data_flow: bool
    has_forms: bool
    data_structure_complexity: str  # simple, medium, complex
    scores: dict  # Individual dimension scores
```

## Testing Requirements

- [ ] Unit tests for product type classification
- [ ] Unit tests for complexity evaluation
- [ ] Unit tests for @Page parsing
- [ ] Unit tests for skill selection
- [ ] Integration tests for full routing flow
- [ ] Test routing with ambiguous inputs

## Notes & Warnings

- Routing should be fast (use light models)
- Cache classification results for similar inputs
- When confidence < 0.5, consider asking user for clarification
- Default to static-landing for unknown product types
- Ensure routing doesn't block for more than 5 seconds
