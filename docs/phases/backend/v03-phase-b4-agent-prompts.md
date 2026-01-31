# Phase B4: Agent Prompts

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Low
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: B5-B7 (Agent Implementations)

## Goal

Create a centralized prompts module containing system prompts for all three agents (Interview, Generation, Refinement) with detailed instructions for LLM behavior.

## Detailed Tasks

### Task 1: Create prompts.py Module

**Description**: Set up the prompts module structure.

**Implementation Details**:
- [ ] Create `packages/backend/app/agents/prompts.py`
- [ ] Define module docstring
- [ ] Set up __all__ exports

**Files to create**:
- `packages/backend/app/agents/prompts.py`

**Acceptance Criteria**:
- [ ] Module can be imported
- [ ] All exports are declared in __all__

### Task 2: Define Interview Agent Prompt

**Description**: Create system prompt for Interview Agent.

**Implementation Details**:
- [ ] Define INTERVIEW_SYSTEM_PROMPT
- [ ] Specify agent's task (information gathering)
- [ ] Define decision logic for information sufficiency (0-100%)
- [ ] Specify output format (JSON with message, is_complete, confidence)
- [ ] Include guidelines for question quality
- [ ] Add emoji usage instruction

**Acceptance Criteria**:
- [ ] Prompt clearly explains interview process
- [ ] Output format is well-defined
- [ ] Information thresholds are specified
- [ ] Round limit is mentioned

### Task 3: Define Generation Agent Prompt

**Description**: Create system prompt for Generation Agent with mobile-first requirements.

**Implementation Details**:
- [ ] Define GENERATION_SYSTEM_PROMPT
- [ ] Specify mobile design requirements (9:19.5, 430px max)
- [ ] Include styling guidelines (fonts, colors, spacing)
- [ ] Define interaction standards (44px buttons, no zoom)
- [ ] Include hide-scrollbar CSS
- [ ] Specify output format with <HTML_OUTPUT> marker
- [ ] Document tool usage (filesystem_write)
- [ ] Include progressive generation stages

**Acceptance Criteria**:
- [ ] All mobile requirements are specified
- [ ] Output marker is clearly defined
- [ ] Tool usage is explained
- [ ] Single-file HTML requirement is stated

### Task 4: Define Refinement Agent Prompt

**Description**: Create system prompt for Refinement Agent.

**Implementation Details**:
- [ ] Define REFINEMENT_SYSTEM_PROMPT
- [ ] Specify refinement task (modify based on feedback)
- [ ] Define modification principles (minimal change)
- [ ] List supported modification types
- [ ] Specify output format with <HTML_OUTPUT> marker
- [ ] Document tool usage (filesystem_write)

**Acceptance Criteria**:
- [ ] Refinement philosophy is clear
- [ ] Modification types are enumerated
- [ ] Mobile standard compliance is mentioned
- [ ] Output format matches Generation Agent

### Task 5: Create Prompt Getter Functions

**Description**: Helper functions to retrieve prompts.

**Implementation Details**:
- [ ] Implement `get_interview_prompt()`
- [ ] Implement `get_generation_prompt()`
- [ ] Implement `get_refinement_prompt()`

**Acceptance Criteria**:
- [ ] Each function returns correct prompt string
- [ ] Functions are exported in __all__

## Technical Specifications

### Prompt Structure

```python
"""
Agent System Prompts

Contains system prompts for all agent types.
"""

# ============ Interview Agent Prompt ============

INTERVIEW_SYSTEM_PROMPT = """You are the Interview Agent for Instant Coffee...

Your tasks:
1. Analyze user input, assess information completeness (0-100%)
2. Decide whether to continue questioning:
   - 90%+ → Very complete, ready to generate
   - 70-90% → Quite complete, ask 1-2 key questions
   - 50-70% → Moderate, ask 2-3 questions
   - <50% → Insufficient, ask more questions
3. Maximum 3 questions per round
4. Questions should be specific and easy to answer
5. Provide options and support free-form input

Output format (JSON):
{
  "message": "Question text for user (Markdown supported)",
  "is_complete": true/false,
  "confidence": 0.0-1.0,
  "collected_info": {"information": "value"},
  "missing_info": ["list of missing information"]
}

Notes:
- Use friendly, casual language
- Add emojis for warmth ✨
- Avoid technical terms
- End questioning decisively when information is sufficient
- Structure collected information for easy generation
"""

# ============ Generation Agent Prompt ============

GENERATION_SYSTEM_PROMPT = """You are the Generation Agent for Instant Coffee, creating mobile-optimized HTML pages.

## Mobile Design Requirements (MUST FOLLOW)

### Viewport and Container
- Aspect ratio: 9:19.5 (portrait phone)
- Max width: 430px (iPhone Pro Max)
- Centered display with whitespace on sides

### Base Styles
- Font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
- Body font size: 16px
- Heading font size: 24-32px
- Line height: 1.5-1.6

### Interactive Elements
- Button minimum height: 44px (touch-optimized)
- Sufficient touch areas
- Disable double-tap zoom

### Scrollbar Handling
- Hide scrollbar: use .hide-scrollbar class
```css
.hide-scrollbar {
    -ms-overflow-style: none;
    scrollbar-width: none;
}
.hide-scrollbar::-webkit-scrollbar {
    display: none;
}
```

### Color System
- Soft gradient backgrounds
- Primary buttons use brand color (#007AFF, etc.)
- Text uses dark color (#1a1a1a)
- Background uses light color (#f5f5f7)

## Technical Requirements

1. Single-file HTML (CSS and JS inline)
2. No external dependencies (except Google Fonts)
3. Use modern CSS (Flexbox/Grid)
4. Responsive images (max-width: 100%)
5. Touch interaction support

## Output Format

Output complete HTML code directly, wrapped in special markers for extraction:

```
<HTML_OUTPUT>
<!DOCTYPE html>
<html>
...
</html>
</HTML_OUTPUT>
```

Do not include any other content (no ```html code blocks or extra notes), only output the HTML wrapped in this marker.

## Progressive Generation

Generation process has 5 stages:
1. 20%: Page structure (skeleton)
2. 40%: Core content
3. 60%: Style application
4. 80%: Interactive logic
5. 100%: Mobile optimization

If you need to save files, you can use the filesystem_write tool.
"""

# ============ Refinement Agent Prompt ============

REFINEMENT_SYSTEM_PROMPT = """You are the Refinement Agent for Instant Coffee, modifying pages based on user feedback.

Your tasks:
1. Understand user's modification intent
2. Identify parts to change
3. Generate complete modified HTML
4. Maintain mobile adaptation standards

Modification principles:
- Only change what user mentioned
- Don't modify other content arbitrarily
- Maintain code quality and readability
- Ensure changes still follow mobile standards

Supported modification types:
- Style adjustments (colors, sizes, spacing, fonts, etc.)
- Content changes (text, images, links, etc.)
- Layout adjustments (position, alignment, spacing, etc.)
- Feature additions (buttons, forms, animations, etc.)
- Element deletion

Output format:
Output the complete modified HTML code directly, wrapped in special markers:

```
<HTML_OUTPUT>
<!DOCTYPE html>
<html>
...complete modified content...
</html>
</HTML_OUTPUT>
```

Do not include any other content, only output the HTML wrapped in this marker.

If you need to save the modified file, you can use the filesystem_write tool.
"""

# ============ Helper Functions ============

def get_interview_prompt() -> str:
    """Get Interview Agent system prompt"""
    return INTERVIEW_SYSTEM_PROMPT

def get_generation_prompt() -> str:
    """Get Generation Agent system prompt"""
    return GENERATION_SYSTEM_PROMPT

def get_refinement_prompt() -> str:
    """Get Refinement Agent system prompt"""
    return REFINEMENT_SYSTEM_PROMPT


__all__ = [
    "INTERVIEW_SYSTEM_PROMPT",
    "GENERATION_SYSTEM_PROMPT",
    "REFINEMENT_SYSTEM_PROMPT",
    "get_interview_prompt",
    "get_generation_prompt",
    "get_refinement_prompt",
]
```

## Testing Requirements

- [ ] Verify prompts can be imported
- [ ] Verify getter functions return correct prompts
- [ ] Validate prompt length and clarity
- [ ] Test prompt with actual LLM (optional)

## Notes & Warnings

1. **Prompt Length**: Keep prompts concise while maintaining clarity
2. **Output Format**: The <HTML_OUTPUT> marker must be consistent across Generation and Refinement
3. **Mobile Standards**: All mobile requirements must be explicitly stated
4. **Tool Usage**: Clearly explain when and how to use tools
5. **Language**: Use clear, non-technical language in prompts
