# Phase B4: Sitemap Agent & AutoMultiPageDecider

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: D1 (Schema), B1 (ProductDoc Service)
  - **Blocks**: B5, B6

## Goal

Implement the SitemapAgent that derives page structure from ProductDoc, and the AutoMultiPageDecider that determines whether to generate single or multiple pages.

## Detailed Tasks

### Task 1: Implement AutoMultiPageDecider

**Description**: Create the decision logic for single vs multi-page generation.

**Implementation Details**:
- [ ] Create AutoMultiPageDecider class
- [ ] Analyze ProductDoc.structured.pages to determine complexity
- [ ] Analyze ProductDoc.structured.features for scope
- [ ] Calculate confidence score (0.0 - 1.0)
- [ ] Apply routing rules:
  - confidence >= 0.75 → auto multi-page
  - 0.45 <= confidence < 0.75 → suggest multi-page, allow user confirmation
  - confidence < 0.45 → single page
- [ ] Return decision with reasons

**Files to modify/create**:
- `packages/backend/app/agents/multipage_decider.py` (new)

**Acceptance Criteria**:
- [ ] Decision logic returns consistent results
- [ ] Confidence scores are well-calibrated
- [ ] Reasons are explainable and useful

---

### Task 2: Create SitemapAgent Class

**Description**: Implement the SitemapAgent that generates detailed page structure.

**Implementation Details**:
- [ ] Create SitemapAgent extending BaseAgent
- [ ] Implement `generate(product_doc: ProductDoc, multi_page: bool) -> SitemapResult`
- [ ] Extract pages from ProductDoc.structured.pages
- [ ] Generate nav structure with labels and order
- [ ] Generate global_style from design_direction
- [ ] Validate output against Pydantic schema

**Files to modify/create**:
- `packages/backend/app/agents/sitemap.py` (new)

**Acceptance Criteria**:
- [ ] Sitemap includes all pages from ProductDoc
- [ ] Navigation structure is complete and ordered
- [ ] Global style reflects design direction

---

### Task 3: Design Sitemap Prompt

**Description**: Create prompts for Sitemap generation from ProductDoc.

**Implementation Details**:
- [ ] Create system prompt defining Sitemap structure
- [ ] Define nav and global_style schemas in prompt
- [ ] Include mobile-first design constraints
- [ ] Handle single-page vs multi-page scenarios
- [ ] Ensure page sections align with ProductDoc features

**Files to modify/create**:
- `packages/backend/app/agents/prompts.py`

**Acceptance Criteria**:
- [ ] Sitemap output is valid JSON
- [ ] Pages have proper sections defined
- [ ] Global style is appropriate for mobile

---

### Task 4: Implement Global Style Generation

**Description**: Generate CSS design tokens from design direction.

**Implementation Details**:
- [ ] Parse color_preference into primary_color hex
- [ ] Select appropriate font_family
- [ ] Define button styles (min 44px height)
- [ ] Define spacing scale
- [ ] Output as global_style object
- [ ] Optionally generate CSS variables

**Files to modify/create**:
- `packages/backend/app/agents/sitemap.py`
- `packages/backend/app/utils/style.py` (new)

**Acceptance Criteria**:
- [ ] Global style produces valid CSS
- [ ] Colors and fonts match design direction
- [ ] Mobile constraints enforced

---

### Task 5: Create Sitemap Output Schema

**Description**: Define Pydantic models for Sitemap validation.

**Implementation Details**:
- [ ] Create SitemapPage model (title, slug, purpose, sections, required)
- [ ] Create NavItem model (slug, label, order)
- [ ] Create GlobalStyle model (primary_color, font_family, etc.)
- [ ] Create SitemapResult model combining all above
- [ ] Add validation rules (pages count 1-8, etc.)

**Files to modify/create**:
- `packages/backend/app/schemas/sitemap.py` (new)

**Acceptance Criteria**:
- [ ] Schema validates all required fields
- [ ] Page count constraints enforced
- [ ] Invalid sitemap data rejected

---

### Task 6: Add Sitemap Events

**Description**: Implement SSE events for Sitemap generation.

**Implementation Details**:
- [ ] Add `multipage_decision_made` event type
- [ ] Add `sitemap_proposed` event type
- [ ] Include decision details (decision, confidence, reasons)
- [ ] Include pages_count in sitemap event

**Files to modify/create**:
- `packages/backend/app/events/models.py`
- `packages/backend/app/agents/sitemap.py`
- `packages/backend/app/agents/multipage_decider.py`

**Acceptance Criteria**:
- [ ] Events emitted at appropriate times
- [ ] Decision event includes confidence and reasons
- [ ] Sitemap event includes page count

---

## Technical Specifications

### AutoMultiPageDecider Interface

```python
@dataclass
class MultiPageDecision:
    decision: str  # "single_page" | "multi_page" | "suggest_multi_page"
    confidence: float  # 0.0 - 1.0
    reasons: List[str]
    suggested_pages: List[dict] | None  # For suggest_multi_page
    risk: str | None  # Any concerns

class AutoMultiPageDecider:
    def decide(self, product_doc: ProductDoc) -> MultiPageDecision:
        """Analyze ProductDoc and decide on page structure."""
        pass
```

### SitemapAgent Interface

```python
@dataclass
class SitemapResult:
    pages: List[SitemapPage]
    nav: List[NavItem]
    global_style: GlobalStyle
    tokens_used: int

class SitemapAgent(BaseAgent):
    async def generate(
        self,
        product_doc: ProductDoc,
        multi_page: bool = True
    ) -> SitemapResult:
        """Generate sitemap from ProductDoc."""
        pass
```

### Sitemap Output Schema

```python
class SitemapPage(BaseModel):
    title: str
    slug: str = Field(..., pattern=r'^[a-z0-9-]+$', max_length=40)
    purpose: str
    sections: List[str]
    required: bool = False

class NavItem(BaseModel):
    slug: str
    label: str
    order: int

class GlobalStyle(BaseModel):
    primary_color: str = Field(..., pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: str | None = None
    font_family: str
    font_size_base: str = "16px"
    font_size_heading: str = "24px"
    button_height: str = "44px"
    spacing_unit: str = "8px"
    border_radius: str = "8px"

class SitemapResult(BaseModel):
    pages: List[SitemapPage] = Field(..., min_length=1, max_length=8)
    nav: List[NavItem]
    global_style: GlobalStyle
```

### Decision Heuristics

```python
def calculate_confidence(product_doc: ProductDoc) -> float:
    """Calculate multi-page confidence score."""
    score = 0.0

    # Page count from ProductDoc
    page_count = len(product_doc.structured.get("pages", []))
    if page_count >= 3:
        score += 0.4
    elif page_count >= 2:
        score += 0.25

    # Feature count
    features = product_doc.structured.get("features", [])
    must_features = [f for f in features if f.get("priority") == "must"]
    if len(must_features) >= 4:
        score += 0.3
    elif len(must_features) >= 2:
        score += 0.15

    # Content indicators in description
    multi_page_keywords = ["页面", "pages", "服务", "services", "产品", "products",
                          "关于", "about", "联系", "contact", "博客", "blog"]
    description = product_doc.structured.get("description", "").lower()
    if any(kw in description for kw in multi_page_keywords):
        score += 0.2

    # Sections complexity
    total_sections = sum(
        len(p.get("sections", []))
        for p in product_doc.structured.get("pages", [])
    )
    if total_sections >= 10:
        score += 0.1

    return min(score, 1.0)
```

### Sitemap Prompt Template

```python
SITEMAP_SYSTEM = """You are a website information architect. Generate a detailed sitemap from the product document.

Output JSON Schema:
{
  "pages": [
    {
      "title": "string",
      "slug": "string (lowercase, hyphenated, max 40 chars)",
      "purpose": "string",
      "sections": ["string"],
      "required": boolean
    }
  ],
  "nav": [
    {"slug": "string", "label": "string", "order": number}
  ],
  "global_style": {
    "primary_color": "#hexcode",
    "secondary_color": "#hexcode (optional)",
    "font_family": "string",
    "font_size_base": "16px",
    "font_size_heading": "24px",
    "button_height": "44px",
    "spacing_unit": "8px",
    "border_radius": "8px"
  }
}

Constraints:
- Index page must have slug "index" and required=true
- Other pages: required=false unless critical
- Page count: 1-8 pages
- Mobile-first: buttons 44px, fonts 16px base

Output only valid JSON, no additional text."""
```

## Testing Requirements

- [ ] Unit tests for AutoMultiPageDecider with various ProductDocs
- [ ] Unit tests for SitemapAgent generate method
- [ ] Unit tests for confidence calculation
- [ ] Unit tests for global_style generation
- [ ] Unit tests for output schema validation
- [ ] Integration test with mock LLM
- [ ] Event emission tests

## Notes & Warnings

- **Index Page Required**: Always ensure index page is included with slug="index"
- **Page Count Limits**: Enforce 1-8 pages to prevent scope creep
- **Color Parsing**: LLM may output color names; convert to hex
- **Fallback Strategy**: If LLM output invalid, fall back to single index page
- **User Override**: Support explicit user override to single/multi page mode
