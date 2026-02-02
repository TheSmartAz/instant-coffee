# Phase B3: ProductDoc Agent

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B1 (ProductDoc Service)
  - **Blocks**: B5, B8

## Goal

Implement the ProductDocAgent that generates and updates Product Doc based on user requirements, serving as the source of truth for all page generation.

## Detailed Tasks

### Task 1: Create ProductDocAgent Class

**Description**: Implement the ProductDocAgent extending BaseAgent.

**Implementation Details**:
- [ ] Create ProductDocAgent class extending BaseAgent
- [ ] Implement `generate()` method for initial ProductDoc creation
- [ ] Implement `update()` method for modifying existing ProductDoc
- [ ] Configure LLM parameters (model, temperature, max_tokens)
- [ ] Add token tracking for both methods

**Files to modify/create**:
- `packages/backend/app/agents/product_doc.py` (new)

**Acceptance Criteria**:
- [ ] Agent generates valid ProductDoc structure
- [ ] Agent updates existing ProductDoc correctly
- [ ] Token usage tracked

---

### Task 2: Design Generate Prompt

**Description**: Create the system prompt and user prompt templates for ProductDoc generation.

**Implementation Details**:
- [ ] Create system prompt defining ProductDoc structure and requirements
- [ ] Include examples of good ProductDoc output
- [ ] Define the structured JSON schema in prompt
- [ ] Handle optional interview context integration
- [ ] Ensure prompt guides toward mobile-first design
- [ ] Add language handling (Chinese/English)

**Files to modify/create**:
- `packages/backend/app/agents/prompts.py`

**Acceptance Criteria**:
- [ ] Generated ProductDoc follows schema
- [ ] Output is both Markdown content and structured JSON
- [ ] Design direction reflects mobile-first principles

---

### Task 3: Design Update Prompt

**Description**: Create prompts for ProductDoc updates based on user feedback.

**Implementation Details**:
- [ ] Create update prompt that receives current ProductDoc and user message
- [ ] Ensure minimal changes (only modify what user requested)
- [ ] Track which pages are affected by changes
- [ ] Generate change summary for user confirmation
- [ ] Output affected_pages list for downstream processing

**Files to modify/create**:
- `packages/backend/app/agents/prompts.py`

**Acceptance Criteria**:
- [ ] Updates preserve unchanged parts
- [ ] Change summary is accurate and helpful
- [ ] affected_pages correctly identifies impacted pages

---

### Task 4: Implement Output Parsing

**Description**: Parse LLM output into ProductDoc format.

**Implementation Details**:
- [ ] Parse Markdown content from response
- [ ] Parse structured JSON from response
- [ ] Handle parsing errors gracefully
- [ ] Validate structured JSON against schema
- [ ] Extract message for user from response

**Files to modify/create**:
- `packages/backend/app/agents/product_doc.py`
- `packages/backend/app/schemas/product_doc.py`

**Acceptance Criteria**:
- [ ] Parsing handles various LLM output formats
- [ ] Invalid JSON is detected and reported
- [ ] Missing required fields are flagged

---

### Task 5: Integrate with ProductDocService

**Description**: Connect agent output to service for persistence.

**Implementation Details**:
- [ ] After generate(), call ProductDocService.create()
- [ ] After update(), call ProductDocService.update()
- [ ] Emit appropriate events (product_doc_generated, product_doc_updated)
- [ ] Return complete response including message for chat

**Files to modify/create**:
- `packages/backend/app/agents/product_doc.py`

**Acceptance Criteria**:
- [ ] ProductDoc persisted correctly
- [ ] Events emitted after persistence
- [ ] Response includes user-facing message

---

## Technical Specifications

### ProductDocAgent Interface

```python
class ProductDocAgent(BaseAgent):
    """Agent for generating and updating Product Doc."""

    async def generate(
        self,
        session_id: UUID,
        user_message: str,
        interview_context: dict | None = None,
        history: List[Message] = []
    ) -> ProductDocGenerateResult:
        """Generate initial ProductDoc from user requirements."""
        pass

    async def update(
        self,
        session_id: UUID,
        current_doc: ProductDoc,
        user_message: str,
        history: List[Message] = []
    ) -> ProductDocUpdateResult:
        """Update existing ProductDoc based on user feedback."""
        pass

@dataclass
class ProductDocGenerateResult:
    content: str  # Markdown content
    structured: dict  # Structured JSON
    message: str  # Message for user
    tokens_used: int

@dataclass
class ProductDocUpdateResult:
    content: str
    structured: dict
    change_summary: str
    affected_pages: List[str]  # List of affected page slugs
    message: str
    tokens_used: int
```

### Generate Prompt Template

```python
PRODUCT_DOC_GENERATE_SYSTEM = """You are a product document specialist. Your job is to create a comprehensive product document that will serve as the source of truth for generating a mobile-first website.

Output Requirements:
1. Markdown content with clear sections
2. Structured JSON data following the schema below

JSON Schema:
{
  "project_name": "string",
  "description": "string (1-2 sentences)",
  "target_audience": "string",
  "goals": ["string (max 5)"],
  "features": [
    {"name": "string", "description": "string", "priority": "must|should|nice"}
  ],
  "design_direction": {
    "style": "string (e.g., modern, minimal, playful)",
    "color_preference": "string",
    "tone": "string (e.g., professional, friendly)",
    "reference_sites": ["string (optional)"]
  },
  "pages": [
    {"title": "string", "slug": "string", "purpose": "string", "sections": ["string"], "required": boolean}
  ],
  "constraints": ["string"]
}

Mobile-First Requirements:
- All designs must target mobile viewport (max 430px)
- Buttons minimum 44px height
- Font sizes: body 16px, headings 24-32px
- Touch-friendly interactions

Output Format:
---MARKDOWN---
[Your Markdown content here]
---JSON---
[Your JSON here]
---MESSAGE---
[Your message to the user]
"""

PRODUCT_DOC_GENERATE_USER = """Based on the following requirements, create a product document:

User Request: {user_message}

{interview_context_section}

Create a comprehensive product document that captures:
1. The project's purpose and goals
2. Target audience
3. Required features and their priorities
4. Design direction
5. Page structure (at minimum, include an index page)
6. Any constraints or special requirements

Remember to output in the specified format with MARKDOWN, JSON, and MESSAGE sections."""
```

### Update Prompt Template

```python
PRODUCT_DOC_UPDATE_SYSTEM = """You are updating an existing product document based on user feedback.

Rules:
1. Only modify what the user explicitly requests
2. Preserve all other content unchanged
3. Track which pages are affected by changes
4. Provide a clear change summary

Output Format:
---MARKDOWN---
[Updated Markdown content]
---JSON---
[Updated JSON]
---AFFECTED_PAGES---
[Comma-separated list of affected page slugs, or "none"]
---CHANGE_SUMMARY---
[Brief summary of changes made]
---MESSAGE---
[Your message to the user]
"""

PRODUCT_DOC_UPDATE_USER = """Current Product Document:

{current_content}

Current Structured Data:
{current_json}

User's Change Request: {user_message}

Update the product document according to the user's request. Only modify what's necessary."""
```

## Testing Requirements

- [ ] Unit tests for generate() with various inputs
- [ ] Unit tests for update() with various change types
- [ ] Unit tests for output parsing
- [ ] Unit tests for affected_pages detection
- [ ] Integration test with mock LLM
- [ ] Integration test with ProductDocService

## Notes & Warnings

- **Output Format Consistency**: LLM may vary output format; parsing must be robust
- **Affected Pages Detection**: Critical for determining what needs regeneration
- **Token Limits**: Monitor token usage; ProductDoc can be lengthy
- **Language Handling**: Support both Chinese and English based on user input language
- **Error Recovery**: If LLM output is invalid, provide helpful error message rather than crashing
