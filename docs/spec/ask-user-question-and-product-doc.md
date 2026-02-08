# AskUserQuestion Tool & Product Doc Workflow

## 1. Overview

Add an `AskUserQuestion` tool to the IC agent that presents multiple-choice
questions (with free-text fallback) to gather requirements from the user.
Collected answers feed into a **Product Doc** — a structured, human-readable
Markdown document that serves as the **single source of truth** for what the
agent should build.

### Core Flow

```
User prompt
    → Agent decides: enough info?
        → YES → build/update Product Doc → approve → generate code
        → NO  → AskUserQuestion (2-5 questions per round, adaptive)
                 → user answers
                 → loop back to "enough info?"
```

---

## 2. AskUserQuestion Tool

### 2.1 Behavior

- **Blocking**: pauses the agentic loop, waits for user answer, then resumes
  with the answer injected into context.
- **LLM-generated**: the agent generates both questions and choice options
  dynamically based on conversation context. No predefined question bank.
- **2-5 questions per round**, adaptive rounds — agent decides when it has
  enough information. Could be 0 rounds (if prompt is detailed) or 3+ rounds.

### 2.2 Tool Schema

```json
{
  "name": "ask_user",
  "description": "Ask the user one or more multiple-choice questions to clarify requirements. Each question includes options the user can pick from, plus free-text input. Use this when the user's request lacks detail needed to build a good product doc.",
  "parameters": {
    "type": "object",
    "properties": {
      "questions": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "question": { "type": "string", "description": "The question text" },
            "options": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "label": { "type": "string" },
                  "description": { "type": "string" }
                },
                "required": ["label"]
              },
              "minItems": 2,
              "maxItems": 5
            },
            "allow_multiple": { "type": "boolean", "default": false }
          },
          "required": ["question", "options"]
        },
        "minItems": 1,
        "maxItems": 5
      }
    },
    "required": ["questions"]
  }
}
```

### 2.3 User Interaction (CLI)

Rendered as a numbered list with free-text option:

```
┌─ Agent needs more info ──────────────────────────┐
│                                                   │
│  1. What type of page are you building?           │
│                                                   │
│     [1] Landing page - Single scroll page         │
│     [2] Multi-page site - With navigation         │
│     [3] Dashboard - Data-heavy layout             │
│     [4] Other (type your answer)                  │
│                                                   │
│  Answer (number, text, or Enter to skip): _       │
│                                                   │
│  Type /go to skip remaining questions             │
└───────────────────────────────────────────────────┘
```

**Skip behavior:**
- **Individual skip**: press Enter with no input → agent picks a sensible
  default for that question.
- **Global escape**: type `/go` or `/build` at any point → stop interview,
  proceed with whatever info has been collected so far.

### 2.4 Abstract Interface (for Web Migration)

The tool communicates through a `UserIO` interface, not directly to the
terminal. This allows the web app to render the same questions as proper UI
components (radio buttons, checkboxes, text fields).

```python
class UserIO(Protocol):
    """Abstract interface for user interaction."""

    async def present_questions(
        self, questions: list[Question]
    ) -> list[Answer]:
        """Present questions and collect answers."""
        ...

    async def confirm(self, message: str) -> bool:
        """Ask for yes/no confirmation."""
        ...
```

**CLI implementation**: numbered list + text input via prompt_toolkit.
**Web implementation** (future): renders as form components via WebSocket/SSE.

---

## 3. Product Doc

### 3.1 Purpose

The Product Doc is a Markdown file stored in the project workspace that
captures the full specification of what the agent should build. It is:

- **Human-readable**: users can read and manually edit it
- **Sectioned**: divided into independent blocks for incremental updates
- **Source of truth**: the agent generates code FROM this doc, not from raw
  conversation history
- **Persistent**: saved with the project, survives across sessions

### 3.2 Location

```
~/.ic/projects/{id}/
├── PRODUCT.md          ← the product doc
├── workspace/
│   └── index.html      ← generated code
├── meta.json
└── context.jsonl
```

### 3.3 Sections

The product doc has 7 standard sections. Each section is independently
updatable — when the user requests a change, the agent updates only the
affected section(s), not the entire document.

```markdown
# Product Doc: {Project Title}

## 1. Overview & Purpose
- Page type (landing, multi-page, dashboard, etc.)
- Target audience
- Core purpose / key message
- Business goal

## 2. Page Structure
- Header / navigation
- Hero section
- Content sections (ordered list)
- Footer
- Page flow / routing (if multi-page)

## 3. Visual Style
- Color palette (primary, secondary, accent, background)
- Typography (heading font, body font, sizes)
- Visual mood (modern, classic, playful, corporate, etc.)
- Imagery style (photos, illustrations, icons, abstract)

## 4. Content & Copy
- Headlines and subheadlines
- Body text / descriptions
- Call-to-action text
- Placeholder content notes

## 5. Interactions & Features
- Buttons and their actions
- Forms and input fields
- Modals / dialogs
- Animations and transitions
- User flows (click X → happens Y)

## 6. Assets & Media
- Image descriptions / placeholders
- Icon style (outline, filled, emoji)
- Font sources (Google Fonts, system, custom)
- External resources (CDN links, APIs)

## 7. Technical Constraints
- Mobile-first (viewport, max-width)
- Responsive breakpoints
- Performance targets
- Accessibility requirements
- Browser support
```

### 3.4 Lifecycle

```
1. User sends initial prompt
2. Agent interviews (AskUserQuestion, adaptive rounds)
3. Agent builds PRODUCT.md from collected info
4. Agent shows PRODUCT.md to user for approval
5. User approves (or requests edits → go to step 3)
6. Agent generates code from PRODUCT.md
7. User requests changes → agent updates relevant section(s)
   of PRODUCT.md → regenerates (smart scope)
```

**Key rule**: the agent NEVER generates code without an approved Product Doc.
The doc is always created/updated first.

### 3.5 Incremental Updates

When the user requests a change:

1. Agent identifies which section(s) are affected
2. Agent updates ONLY those sections (not the full doc)
3. Agent uses the `edit_file` tool to surgically update the section
4. This keeps the doc stable and avoids unnecessary rewrites

Example: "change the color to blue" → only updates `## 3. Visual Style`.

---

## 4. Refinement: Smart Scope Regeneration

After updating the Product Doc, the agent decides the regeneration scope:

| Change Type | Example | Action |
|---|---|---|
| **Cosmetic** | Color, font size, text content | Surgical edit on existing HTML |
| **Component** | Add a button, change a modal | Edit specific section of HTML |
| **Structural** | Add new page section, change layout | Full regeneration from doc |
| **Full rewrite** | User explicitly requests rebuild | Full regeneration from doc |

The agent makes this decision based on which Product Doc sections changed
and the magnitude of the change.

---

## 5. Implementation Plan

### Phase 1: AskUserQuestion Tool
- [ ] Create `UserIO` protocol in `ic/ui/io.py`
- [ ] Implement `CLIUserIO` using prompt_toolkit (numbered list + text)
- [ ] Create `AskUser` tool in `ic/tools/ask/__init__.py`
- [ ] Wire tool into engine: detect `ask_user` tool call → pause loop →
      present to user → inject answer → resume
- [ ] Add skip (Enter) and global escape (`/go`) support

### Phase 2: Product Doc
- [ ] Create `ProductDoc` class in `ic/doc/__init__.py`
  - Parse/serialize Markdown with sections
  - `update_section(name, content)` for incremental updates
  - `to_markdown()` / `from_markdown()` round-trip
- [ ] Update system prompt to instruct agent about Product Doc workflow
- [ ] Add `/doc` slash command to view current Product Doc
- [ ] Add `/doc edit` to open Product Doc in `$EDITOR`

### Phase 3: Doc-First Workflow
- [ ] Update engine to enforce: interview → doc → approve → generate
- [ ] Add approval gate: after doc creation, agent calls `confirm()`
      via UserIO before proceeding to generation
- [ ] Implement smart scope: agent analyzes doc diff to decide
      surgical edit vs full regen

### Phase 4: Integration
- [ ] Update `App.run()` to support the new workflow
- [ ] Persist Product Doc with project (auto-save after each update)
- [ ] Load Product Doc when resuming a project
- [ ] Test end-to-end: prompt → interview → doc → approve → generate
      → refine → update doc → regenerate

---

## 6. Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Tool blocking | Blocking (pause & wait) | Agent needs answers before proceeding |
| Choice generation | Fully LLM-generated | Maximum flexibility per context |
| Answer storage | Product Doc (source of truth) | Structured, persistent, human-editable |
| Question rounds | Adaptive, 2-5 per round | Agent judges info sufficiency |
| Doc format | Markdown with sections | Human-readable + incrementally updatable |
| Doc lifecycle | Doc → approve → generate | No wasted generation on wrong assumptions |
| CLI UX | Numbered list + text | Simple, portable, works everywhere |
| Skip behavior | Individual skip + global escape | Maximum user control |
| Refinement | Smart scope (agent decides) | Balance of speed and consistency |
| Web migration | Abstract UserIO interface now | Minimal cost, big payoff later |
