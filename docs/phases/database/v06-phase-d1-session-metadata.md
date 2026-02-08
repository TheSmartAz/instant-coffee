# Phase D1: Session Metadata Extension

## Metadata

- **Category**: Database
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Low
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: None

## Goal

Extend the session metadata to track Orchestrator routing decisions (product type, complexity, skill selected, doc tier, model choices).

## Detailed Tasks

### Task 1: Add Routing Decision Fields to Session

**Description**: Add new fields to the sessions table to track routing decisions made by the Orchestrator.

**Implementation Details**:
- [ ] Add `product_type` column (enum/varchar: ecommerce, booking, dashboard, landing, card, invitation)
- [ ] Add `complexity` column (enum/varchar: simple, medium, complex)
- [ ] Add `skill_id` column (varchar: references the selected skill)
- [ ] Add `doc_tier` column (enum/varchar: checklist, standard, extended)
- [ ] Add `style_reference_mode` column (enum/varchar: full_mimic, style_only)

**Files to modify/create**:
- `packages/backend/app/db/models.py` (or equivalent ORM models)

**Acceptance Criteria**:
- [ ] All new fields are added to the sessions table
- [ ] Fields are nullable (for backward compatibility with existing sessions)
- [ ] Migration script is created

### Task 2: Add Model Usage Tracking

**Description**: Track which models were used for different roles in the generation process.

**Implementation Details**:
- [ ] Add `model_classifier` column (varchar: model ID used for classification)
- [ ] Add `model_writer` column (varchar: model ID used for generation)
- [ ] Add `model_expander` column (varchar: model ID used for expansion)
- [ ] Add `model_validator` column (varchar: model ID used for validation)
- [ ] Add `model_style_refiner` column (varchar: model ID used for style refinement)

**Files to modify/create**:
- `packages/backend/app/db/models.py`

**Acceptance Criteria**:
- [ ] All model tracking columns are added
- [ ] Fields are nullable (for backward compatibility)

### Task 3: Create Migration Script

**Description**: Create a migration script to add the new columns to existing databases.

**Implementation Details**:
- [ ] Use Alembic or equivalent migration tool
- [ ] Include ALTER TABLE statements for new columns
- [ ] Include default values for existing rows

**Files to modify/create**:
- `packages/backend/app/db/migrations/versions/xxx_add_routing_metadata.py`

**Acceptance Criteria**:
- [ ] Migration runs successfully on existing databases
- [ ] Existing sessions remain valid (new columns are null/empty)

## Technical Specifications

### Database Schema Changes

```sql
ALTER TABLE sessions ADD COLUMN product_type VARCHAR(50);
ALTER TABLE sessions ADD COLUMN complexity VARCHAR(20);
ALTER TABLE sessions ADD COLUMN skill_id VARCHAR(100);
ALTER TABLE sessions ADD COLUMN doc_tier VARCHAR(20);
ALTER TABLE sessions ADD COLUMN style_reference_mode VARCHAR(50);

ALTER TABLE sessions ADD COLUMN model_classifier VARCHAR(100);
ALTER TABLE sessions ADD COLUMN model_writer VARCHAR(100);
ALTER TABLE sessions ADD COLUMN model_expander VARCHAR(100);
ALTER TABLE sessions ADD COLUMN model_validator VARCHAR(100);
ALTER TABLE sessions ADD COLUMN model_style_refiner VARCHAR(100);
```

### Pydantic Models

```python
class RoutingMetadata(BaseModel):
    product_type: Optional[str] = None
    complexity: Optional[str] = None
    skill_id: Optional[str] = None
    doc_tier: Optional[str] = None
    style_reference_mode: Optional[str] = None

class ModelUsage(BaseModel):
    classifier: Optional[str] = None
    writer: Optional[str] = None
    expander: Optional[str] = None
    validator: Optional[str] = None
    style_refiner: Optional[str] = None
```

## Testing Requirements

- [ ] Unit tests for model changes
- [ ] Migration test on empty database
- [ ] Migration test on existing database with data

## Notes & Warnings

- All new fields should be nullable for backward compatibility
- Consider adding indexes on frequently queried fields (product_type, complexity)
- Model IDs may be large (for URLs), ensure VARCHAR length is sufficient
