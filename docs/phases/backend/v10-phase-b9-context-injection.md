# Phase v10-B9: Richer Context Injection

## Metadata

- **Category**: Backend
- **Priority**: P1
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: None (enrichment feature)

## Goal

Enhance context injection with design tokens, page structure, and resource inventory.

## Detailed Tasks

### Task 1: Design Token Extraction

**Description**: Extract design tokens from CSS.

**Implementation Details**:
- [ ] Extract color variables
- [ ] Extract font families
- [ ] Extract spacing values
- [ ] Add to context injector

**Files to modify**:
- `packages/agent/src/ic/soul/context_injector.py`

**Acceptance Criteria**:
- [ ] Tokens extracted from CSS

---

### Task 2: Page Structure Summary

**Description**: Generate summary of page structure.

**Implementation Details**:
- [ ] List sections per page
- [ ] Track component usage
- [ ] Add to context

**Files to modify**:
- `packages/agent/src/ic/soul/context_injector.py`

**Acceptance Criteria**:
- [ ] Page summaries available

---

### Task 3: Resource Inventory

**Description**: Track uploaded assets and external resources.

**Implementation Details**:
- [ ] List uploaded images
- [ ] Track external resource URLs
- [ ] Add to context

**Files to modify**:
- `packages/agent/src/ic/soul/context_injector.py`

**Acceptance Criteria**:
- [ ] Resources tracked and available

## Technical Specifications

### Injection Items

1. **Design Tokens**
```python
{
    "colors": {"primary": "#007AFF", "secondary": "#5856D6"},
    "fonts": ["Inter", "SF Pro"],
    "spacing": {"sm": "8px", "md": "16px", "lg": "24px"}
}
```

2. **Page Structure**
```python
{
    "pages": {
        "home": {"sections": ["hero", "features", "cta"], "components": ["Button", "Card"]},
        "about": {"sections": ["header", "team", "contact"]}
    }
}
```

3. **Resource Inventory**
```python
{
    "images": [{"path": "/assets/hero.jpg", "purpose": "hero background"}],
    "external": [{"url": "https://fonts.google.com", "purpose": "fonts"}]
}
```

## Testing Requirements

- [ ] Test token extraction
- [ ] Test page summary generation
- [ ] Test resource tracking

## Notes & Warnings

- Depends on Phase 2 (HTML tool) for structure
- Should be incremental - don't rebuild every turn
