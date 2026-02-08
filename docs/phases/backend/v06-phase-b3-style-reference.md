# Phase B3: Style Reference Service

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B1 (Skills Registry)
  - **Blocks**: B7

## Goal

Implement style reference extraction from uploaded images, outputting design tokens (colors, typography, spacing, layout patterns) for use in generation, with fallback to internal style profiles.

## Detailed Tasks

### Task 1: Create Style Reference Data Models

**Description**: Define data structures for style reference inputs and outputs.

**Implementation Details**:
- [ ] Create `StyleReference` Pydantic model
- [ ] Create `StyleTokens` model for extracted design tokens
- [ ] Support modes: full_mimic, style_only
- [ ] Support scope: model_decide, specific_pages
- [ ] Include image metadata (id, source, page_hint)

**Files to modify/create**:
- `packages/backend/app/services/style_reference.py` (new file)
- `packages/backend/app/schemas/style_reference.py` (new file)

**Acceptance Criteria**:
- [ ] StyleReference model validates all fields
- [ ] Supports 1-3 image references
- [ ] Modes are enum-validated

### Task 2: Implement Style Token Extraction

**Description**: Extract design tokens from reference images using vision model.

**Implementation Details**:
- [ ] Create `StyleExtractor` class
- [ ] Use vision-capable model for image analysis
- [ ] Extract: colors (primary, accent, background), typography (family, scale), radius, shadow, spacing
- [ ] Extract layout patterns in full_mimic mode
- [ ] Return structured tokens JSON

**Files to modify/create**:
- `packages/backend/app/services/style_reference.py`

**Acceptance Criteria**:
- [ ] Extracts color palette with hex codes
- [ ] Identifies typography style (sans/serif, scale)
- [ ] Identifies border radius (sharp/rounded/pill)
- [ ] Identifies shadow style (none/soft/strong)
- [ ] In full_mimic mode, identifies layout patterns

### Task 3: Implement Layout Pattern Recognition

**Description**: Extract and describe layout patterns from reference images.

**Implementation Details**:
- [ ] Extend vision prompt for layout analysis
- [ ] Identify: hero sections, card grids, split layouts, vertical lists
- [ ] Output structured layout pattern list
- [ ] Map patterns to applicable page types

**Files to modify/create**:
- `packages/backend/app/services/style_reference.py`

**Acceptance Criteria**:
- [ ] Identifies hero-left, hero-center, hero-full patterns
- [ ] Identifies card-grid, card-list patterns
- [ ] Identifies split-layout patterns
- [ ] Returns pattern list with confidence scores

### Task 4: Create Style Reference Prompts

**Description**: Design prompts for vision model style extraction.

**Implementation Details**:
- [ ] Create "style_only" prompt for colors/typography only
- [ ] Create "full_mimic" prompt for colors + layout
- [ ] Include WCAG contrast checking instructions
- [ ] Request JSON output format

**Files to modify/create**:
- `packages/backend/app/agents/prompts.py` (add style reference prompts)

**Acceptance Criteria**:
- [ ] Prompts elicit structured JSON responses
- [ ] Style-only prompt ignores layout
- [ ] Full-mimic prompt includes layout patterns

### Task 5: Integrate with Generation Pipeline

**Description**: Inject style tokens into generation context.

**Implementation Details**:
- [ ] Pass style tokens to ProductDoc agent
- [ ] Pass style tokens to Generation agent
- [ ] Create `global_style` section in generation context
- [ ] Apply scope filtering (specific pages vs all)
- [ ] Merge with style profile tokens (reference tokens override profile)

**Files to modify/create**:
- `packages/backend/app/agents/generation.py` (update)
- `packages/backend/app/agents/product_doc.py` (update)

**Acceptance Criteria**:
- [ ] Style tokens appear in generation context
- [ ] Scope filtering limits token injection to target pages
- [ ] @Page targeting combined with style scope
- [ ] When no images, style profile tokens provide defaults
- [ ] When images exist, reference tokens override profile tokens

### Task 6: Handle Missing/Fallback Scenarios

**Description**: Handle cases where vision model is unavailable or fails.

**Implementation Details**:
- [ ] Check for vision model availability
- [ ] Fallback to style_only mode if no vision model
- [ ] Log warnings when fallback occurs
- [ ] Allow manual style token input
 - [ ] Default to style profile tokens when no images provided

**Files to modify/create**:
- `packages/backend/app/services/style_reference.py`

**Acceptance Criteria**:
- [ ] Graceful degradation when vision unavailable
- [ ] Warning logged for missing capabilities
- [ ] Generation continues with limited style info

## Technical Specifications

### StyleReference Schema

```python
class StyleScope(BaseModel):
    type: Literal["model_decide", "specific_pages"]
    pages: List[str] = []  # Empty when model_decide

class StyleImage(BaseModel):
    id: str
    source: Literal["upload", "url"]
    page_hint: Optional[str] = None  # Which page this applies to
    url: Optional[str] = None
    base64_data: Optional[str] = None

class StyleTokens(BaseModel):
    colors: Dict[str, str]  # primary, accent, background, text, border
    typography: Dict[str, Any]  # family, scale, weights
    radius: Literal["sharp", "small", "medium", "large", "pill"]
    shadow: Literal["none", "soft", "medium", "strong"]
    spacing: Literal["tight", "medium", "airy"]
    layout_patterns: List[str] = []  # hero-left, card-grid, etc.

class StyleReference(BaseModel):
    mode: Literal["full_mimic", "style_only"]
    scope: StyleScope
    images: List[StyleImage]
    tokens: Optional[StyleTokens] = None  # Populated after extraction
```

### Vision Model Prompt (full_mimic)

```
You are a design analyst. Extract design tokens from this reference image.

Analyze and extract:
1. Colors: primary (buttons, links), accent (highlights), background (main, card, surface), text (primary, secondary)
2. Typography: font family (sans/serif/mono), size scale (small/base/large/xlarge), weights
3. Border radius: sharp (0px), small (4px), medium (8px), large (16px), pill (999px)
4. Shadow: none, soft (subtle), medium, strong (dramatic)
5. Spacing: tight (compact), medium, airy (generous whitespace)
6. Layout patterns: hero-left, hero-center, hero-full, card-grid, card-list, split-vertical, split-horizontal, stacked-sections

Return JSON:
{
  "colors": {"primary": "#hex", "accent": "#hex", "background": {"main": "#hex", "card": "#hex", "surface": "#hex"}, "text": {"primary": "#hex", "secondary": "#hex"}},
  "typography": {"family": "sans/serif/mono", "scale": "small/base/large", "weights": ["400", "600"]},
  "radius": "sharp/small/medium/large/pill",
  "shadow": "none/soft/medium/strong",
  "spacing": "tight/medium/airy",
  "layout_patterns": ["pattern1", "pattern2"]
}
```

### Service Interface

```python
class StyleReferenceService:
    def __init__(self, vision_client: LLMClient):
        self.vision_client = vision_client

    async def extract_style(
        self,
        images: List[StyleImage],
        mode: str = "full_mimic"
    ) -> StyleTokens:
        """Extract style tokens from images using vision model."""

    def apply_scope(
        self,
        tokens: StyleTokens,
        scope: StyleScope,
        target_pages: List[str]
    ) -> Dict[str, StyleTokens]:
        """Apply scope filtering to return per-page style tokens."""

    async def check_vision_capability(self) -> bool:
        """Check if configured model supports vision input."""
```

## Testing Requirements

- [ ] Unit tests for StyleReference schema validation
- [ ] Unit tests for token extraction parsing
- [ ] Integration tests with vision model
- [ ] Tests for fallback behavior
- [ ] Tests for scope filtering

## Notes & Warnings

- Vision model support is required for full_mimic mode
- Base64 image encoding can be large - consider size limits
- Layout pattern extraction is approximate - don't over-promise
- Some vision models may not support detailed layout analysis
- Consider caching extraction results for same images
- WCAG contrast checking is automated - fail if tokens don't meet 4.5:1
