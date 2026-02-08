# Phase B7: Aesthetic Scoring

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B3 (Style Reference), B6 (Multi-model Routing)
  - **Blocks**: None

## Goal

Implement aesthetic scoring for Landing/Card pages with automatic scoring, threshold-based Style Refiner triggering, and rewrite logic with quality comparison.

## Detailed Tasks

### Task 1: Define Aesthetic Scoring Schema

**Description**: Create data structures for scoring criteria and results.

**Implementation Details**:
- [ ] Create `AestheticScore` Pydantic model
- [ ] Define 5 scoring dimensions: typography, contrast, layout, color, cta
- [ ] Each dimension scored 1-5, total 25
- [ ] Include auto-checks for WCAG, line-height, type-scale

**Files to modify/create**:
- `packages/backend/app/schemas/validation.py` (new file)

**Acceptance Criteria**:
- [ ] Score model validates ranges (1-5 per dimension)
- [ ] Total score calculated correctly
- [ ] Auto-checks return pass/fail status

### Task 2: Implement Visual Analysis Agent

**Description**: Create agent to score generated pages on aesthetic dimensions.

**Implementation Details**:
- [ ] Create `AestheticScorer` agent
- [ ] Use light/vision model for scoring
- [ ] Prompt for 5-dimension scoring
- [ ] Request JSON output format
- [ ] Include issue list in response

**Files to modify/create**:
- `packages/backend/app/agents/aesthetic_scorer.py` (new file)
- `packages/backend/app/agents/prompts.py` (add scoring prompt)

**Acceptance Criteria**:
- [ ] Returns score for each dimension
- [ ] Returns total score (sum of dimensions)
- [ ] Lists specific issues found
- [ ] Includes auto-check results

### Task 3: Implement Auto-Checks

**Description**: Add automated validation for measurable criteria.

**Implementation Details**:
- [ ] WCAG contrast checker (4.5:1 requirement)
- [ ] Line-height range check (1.4-1.8)
- [ ] Type scale difference check (title/body/CTA distinct)
- [ ] Parse generated HTML/CSS for values

**Files to modify/create**:
- `packages/backend/app/utils/validation.py` (new file)

**Acceptance Criteria**:
- [ ] Contrast check returns pass/fail + ratio
- [ ] Line-height check validates body text
- [ ] Type scale check ensures hierarchy
- [ ] All checks return structured results

### Task 4: Implement Threshold Triggers

**Description**: Define scoring thresholds and trigger Style Refiner when below threshold.

**Implementation Details**:
- [ ] Set MVP threshold at 18/25
- [ ] Check product type (only Landing/Card use aesthetic scoring)
- [ ] Trigger Style Refiner if score < threshold
- [ ] Limit to 2 rewrite attempts

**Files to modify/create**:
- `packages/backend/app/agents/validator.py` (update)

**Acceptance Criteria**:
- [ ] Scores >= 18 pass without refiner
- [ ] Scores < 18 trigger Style Refiner
- [ ] Maximum 2 refiner iterations
- [ ] Flow apps bypass aesthetic scoring

### Task 5: Implement Rewrite Logic with Comparison

**Description**: Handle Style Refiner rewrites with quality comparison.

**Implementation Details**:
- [ ] Store original version before refiner
- [ ] Score refiner output
- [ ] Compare scores: keep higher
- [ ] If refiner score < original, keep original
- [ ] If 2nd iteration score < 1st, keep 1st

**Files to modify/create**:
- `packages/backend/app/agents/style_refiner.py` (new file or update)
- `packages/backend/app/agents/validator.py` (update)

**Acceptance Criteria**:
- [ ] Original preserved for comparison
- [ ] Higher-scoring version selected
- [ ] Never degrades score
- [ ] Stops after 2 iterations

### Task 6: Integrate with Generation Pipeline

**Description**: Hook aesthetic scoring into post-generation validation.

**Implementation Details**:
- [ ] Score output after generation
- [ ] Trigger refiner if needed
- [ ] Log scores to session metadata
- [ ] Return final (possibly refined) HTML

**Files to modify/create**:
- `packages/backend/app/agents/orchestrator.py` (update)

**Acceptance Criteria**:
- [ ] All Landing/Card pages scored
- [ ] Low scores trigger refiner
- [ ] Scores logged for analysis
- [ ] Generation completes with best version

## Technical Specifications

### AestheticScore Schema

```python
class AutoChecks(BaseModel):
    wcag_contrast: str  # "pass" or "fail"
    contrast_ratio: Optional[float] = None
    line_height: str  # "pass" or "fail"
    line_height_value: Optional[float] = None
    type_scale: str  # "pass" or "fail"
    scale_difference: Optional[str] = None

class DimensionScores(BaseModel):
    typography: int = Field(ge=1, le=5)  # 1-5
    contrast: int = Field(ge=1, le=5)
    layout: int = Field(ge=1, le=5)
    color: int = Field(ge=1, le=5)
    cta: int = Field(ge=1, le=5)

class AestheticScore(BaseModel):
    dimensions: DimensionScores
    total: int  # Sum of dimensions (5-25)
    issues: List[str] = []
    auto_checks: AutoChecks
    passes_threshold: bool  # total >= 18 for MVP
```

### Scoring Prompt

```
You are a visual design reviewer. Score this page on 5 dimensions (1-5 each):

1. Typography: Is there clear hierarchy (title/body/CTA)? Are sizes appropriate?
2. Contrast: Is text readable against background? Good color contrast?
3. Layout: Is the layout balanced? Good use of whitespace?
4. Color: Do colors work well together? Professional appearance?
5. CTA: Is the call-to-action prominent? Clear visual guidance?

Scoring guide:
- 5: Excellent, professional quality
- 4: Good, minor issues
- 3: Acceptable, some improvement needed
- 2: Poor, significant issues
- 1: Unusable, major problems

Output JSON:
{
  "dimensions": {
    "typography": 0,
    "contrast": 0,
    "layout": 0,
    "color": 0,
    "cta": 0
  },
  "total": 0,
  "issues": ["Specific issue 1", "Specific issue 2"],
  "suggestions": ["Improvement suggestion 1"]
}
```

### Rewrite Flow

```python
@dataclass
class RewriteAttempt:
    version: int
    html: str
    score: AestheticScore
    timestamp: datetime

class AestheticValidator:
    THRESHOLD = 18
    MAX_ATTEMPTS = 2

    async def validate_and_refine(
        self,
        html: str,
        product_type: str
    ) -> tuple[str, AestheticScore]:
        """Validate HTML and refine if needed. Returns (final_html, final_score)."""

        # Only score Landing/Card
        if product_type not in ["landing", "card", "invitation"]:
            return html, None

        attempts = []
        current_html = html

        # Score original
        original_score = await self.score(current_html)
        attempts.append(RewriteAttempt(0, current_html, original_score, datetime.now()))

        # Check if refiner needed
        if original_score.total >= self.THRESHOLD:
            return current_html, original_score

        # Attempt 1
        refiner_html = await self.style_refiner.refine(current_html, original_score)
        refiner_score = await self.score(refiner_html)
        attempts.append(RewriteAttempt(1, refiner_html, refiner_score, datetime.now()))

        if refiner_score.total >= original_score.total:
            current_html = refiner_html
            current_score = refiner_score
        else:
            # Refiner made it worse, keep original
            return html, original_score

        # Check if we need second attempt
        if current_score.total >= self.THRESHOLD:
            return current_html, current_score

        # Attempt 2
        refiner_html_2 = await self.style_refiner.refine(current_html, current_score)
        refiner_score_2 = await self.score(refiner_html_2)

        if refiner_score_2.total >= current_score.total:
            return refiner_html_2, refiner_score_2
        else:
            return current_html, current_score
```

### Auto-Check Implementation

```python
def check_wcag_contrast(html: str) -> tuple[bool, float]:
    """Check if text meets WCAG 4.5:1 contrast requirement."""
    # Parse CSS and HTML
    # Calculate contrast ratios for text/background pairs
    # Return (passes, max_ratio_found)
    pass

def check_line_height(css: str) -> tuple[bool, float]:
    """Check if body text has line-height 1.4-1.8."""
    # Parse CSS for line-height values
    # Return (passes, value)
    pass

def check_type_scale(css: str) -> tuple[bool, str]:
    """Check if title/body/CTA have distinct sizes."""
    # Parse CSS for font-size values
    # Check hierarchy exists
    # Return (passes, description)
    pass
```

## Testing Requirements

- [ ] Unit tests for scoring schema validation
- [ ] Unit tests for auto-checks (contrast, line-height, type-scale)
- [ ] Integration tests for scorer agent
- [ ] Tests for rewrite logic and comparison
- [ ] Tests for threshold triggering
- [ ] Tests with various quality inputs

## Notes & Warnings

- Aesthetic scoring only for Landing/Card/invitation products
- Flow apps (ecommerce, booking, dashboard) use structural validation instead
- Threshold of 18/25 is for MVP - adjust based on real results
- Light models may not score consistently - consider using mid model
- Auto-checks supplement LLM scoring but aren't sufficient alone
- Store scores for later analysis and threshold tuning
- Don't block generation on refiner failure - return original if refiner fails
