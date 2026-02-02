# Phase B7: RefinementAgent Update for Multi-Page

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B2 (Page Service), B6 (Generation Agent Update)
  - **Blocks**: B8

## Goal

Extend the RefinementAgent to support multi-page refinement with page targeting, ProductDoc context injection, and proper version creation.

## Detailed Tasks

### Task 1: Update RefinementAgent Input Interface

**Description**: Add parameters for page-specific refinement.

**Implementation Details**:
- [ ] Add `page: Page` parameter (target page to modify)
- [ ] Add `product_doc: ProductDoc` parameter (context)
- [ ] Add `global_style: GlobalStyle` parameter (for style consistency)
- [ ] Add `all_pages: List[Page]` parameter (for navigation updates if needed)
- [ ] Keep backward compatibility for single-page mode

**Files to modify/create**:
- `packages/backend/app/agents/refinement.py`

**Acceptance Criteria**:
- [ ] Page parameter correctly identifies target
- [ ] ProductDoc context available in refinement
- [ ] Single-page mode still works

---

### Task 2: Implement Page Targeting Logic

**Description**: Add logic to determine which page to modify.

**Implementation Details**:
- [ ] If page explicitly provided, use it directly
- [ ] If message contains page slug/title, match it
- [ ] If multiple pages could match, return disambiguation
- [ ] If no page matches but message suggests global change, handle accordingly
- [ ] For single-page sessions, auto-target the only page

**Files to modify/create**:
- `packages/backend/app/agents/refinement.py`

**Acceptance Criteria**:
- [ ] Correct page targeted from message
- [ ] Disambiguation returned when ambiguous
- [ ] Global changes handled appropriately

---

### Task 3: Update Refinement Prompt for ProductDoc Context

**Description**: Modify prompts to include ProductDoc and design system.

**Implementation Details**:
- [ ] Include ProductDoc context in system prompt
- [ ] Include global_style CSS variables
- [ ] Specify that changes must maintain design consistency
- [ ] Remind about mobile-first constraints
- [ ] Include page-specific purpose and sections

**Files to modify/create**:
- `packages/backend/app/agents/prompts.py`

**Acceptance Criteria**:
- [ ] Refinement respects ProductDoc requirements
- [ ] Style consistency maintained
- [ ] Mobile constraints preserved

---

### Task 4: Implement Navigation Preservation

**Description**: Ensure navigation is preserved/updated during refinement.

**Implementation Details**:
- [ ] Parse existing navigation from current HTML
- [ ] If refinement doesn't touch nav, preserve exactly
- [ ] If page list changed, update nav accordingly
- [ ] Maintain nav styling consistency

**Files to modify/create**:
- `packages/backend/app/agents/refinement.py`
- `packages/backend/app/utils/html.py`

**Acceptance Criteria**:
- [ ] Navigation preserved by default
- [ ] Nav updates when needed
- [ ] Nav styling consistent

---

### Task 5: Update Output to Create PageVersion

**Description**: Save refinement result as new PageVersion.

**Implementation Details**:
- [ ] After refinement, call PageVersionService.create()
- [ ] Include refinement description in version notes
- [ ] Update Page.current_version_id
- [ ] Emit page_version_created event
- [ ] Emit page_preview_ready event

**Files to modify/create**:
- `packages/backend/app/agents/refinement.py`

**Acceptance Criteria**:
- [ ] New PageVersion created after refinement
- [ ] Version number incremented
- [ ] Events emitted

---

### Task 6: Implement Batch Refinement Support

**Description**: Support refining multiple pages with same change.

**Implementation Details**:
- [ ] Add `batch_refine()` method for applying same change to multiple pages
- [ ] Process pages sequentially (to avoid token limit issues)
- [ ] Track which pages succeeded/failed
- [ ] Return summary of changes

**Files to modify/create**:
- `packages/backend/app/agents/refinement.py`

**Acceptance Criteria**:
- [ ] Batch refinement works for multiple pages
- [ ] Failures don't block other pages
- [ ] Summary includes success/failure status

---

## Technical Specifications

### Updated RefinementAgent Interface

```python
@dataclass
class DisambiguationResult:
    """Returned when page cannot be determined."""
    candidates: List[Page]
    message: str  # "Which page do you want to modify?"

@dataclass
class RefinementResult:
    page_id: UUID
    html: str
    version: int
    tokens_used: int
    changes_made: str  # Summary of changes

@dataclass
class BatchRefinementResult:
    results: List[RefinementResult | None]  # None for failures
    failures: List[tuple[UUID, str]]  # (page_id, error_message)

class RefinementAgent(BaseAgent):
    async def refine(
        self,
        session_id: UUID,
        page: Page,
        user_message: str,
        product_doc: ProductDoc,
        global_style: GlobalStyle,
        all_pages: List[Page],
        history: List[Message] = []
    ) -> RefinementResult:
        """Refine a specific page based on user feedback."""
        pass

    async def detect_target_page(
        self,
        message: str,
        pages: List[Page]
    ) -> Page | DisambiguationResult:
        """Determine which page the user wants to modify."""
        pass

    async def batch_refine(
        self,
        session_id: UUID,
        pages: List[Page],
        user_message: str,
        product_doc: ProductDoc,
        global_style: GlobalStyle,
        history: List[Message] = []
    ) -> BatchRefinementResult:
        """Apply same refinement to multiple pages."""
        pass
```

### Updated Refinement Prompt

```python
REFINEMENT_SYSTEM_MULTIPAGE = """You are modifying an existing mobile-first HTML page.

=== Product Document Context ===
{product_doc_context}

=== Design System ===
{global_style_css}

=== Target Page ===
Title: {page_title}
Slug: {page_slug}
Purpose: {page_purpose}

=== Current HTML ===
{current_html}

=== Modification Rules ===
1. Only modify what the user requests
2. Preserve navigation structure unless specifically asked to change
3. Maintain design system consistency (use CSS variables)
4. Preserve mobile-first constraints (430px max, 44px buttons, 16px fonts)
5. Keep all existing functionality unless told to remove
6. If changing navigation, ensure all links still work

Output: Complete modified HTML document."""

REFINEMENT_USER_MULTIPAGE = """User's modification request: {user_message}

Apply the requested changes to the page while following all rules above.
Output the complete modified HTML."""
```

### Page Detection Logic

```python
def detect_target_page(message: str, pages: List[Page]) -> Page | DisambiguationResult:
    # Check for exact slug match
    for page in pages:
        if page.slug in message.lower():
            return page

    # Check for title match (fuzzy for Chinese)
    matches = []
    for page in pages:
        if page.title.lower() in message.lower():
            matches.append(page)
        # Chinese title matching
        if any(char in message for char in page.title):
            matches.append(page)

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        return DisambiguationResult(
            candidates=matches,
            message="Which page do you want to modify? " +
                    ", ".join(f"'{p.title}' ({p.slug})" for p in matches)
        )

    # No page mentioned - check if only one page exists
    if len(pages) == 1:
        return pages[0]

    # Return disambiguation with all pages
    return DisambiguationResult(
        candidates=pages,
        message="Which page do you want to modify? " +
                ", ".join(f"'{p.title}' ({p.slug})" for p in pages)
    )
```

### Global Change Detection

```python
GLOBAL_CHANGE_KEYWORDS = {
    "zh": ["所有页面", "全部", "整体", "全局", "统一"],
    "en": ["all pages", "every page", "globally", "everywhere", "site-wide"]
}

def is_global_change(message: str) -> bool:
    message_lower = message.lower()
    for keywords in GLOBAL_CHANGE_KEYWORDS.values():
        if any(kw in message_lower for kw in keywords):
            return True
    return False
```

## Testing Requirements

- [ ] Unit tests for page detection logic
- [ ] Unit tests for disambiguation handling
- [ ] Unit tests for global change detection
- [ ] Unit tests for navigation preservation
- [ ] Integration test for single-page refinement
- [ ] Integration test for batch refinement
- [ ] Test backward compatibility

## Notes & Warnings

- **Navigation Preservation**: By default, don't touch navigation unless asked
- **Version Creation**: Always create new version, never modify in place
- **Batch Refinement**: Process sequentially to avoid overwhelming LLM
- **Context Size**: ProductDoc + current HTML can be large; monitor token usage
- **Disambiguation UX**: Return helpful message listing options, not just error
