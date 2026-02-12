# Phase v10-B8: Cross-Session Memory

## Metadata

- **Category**: Backend
- **Priority**: P0
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v10-D1 (Memory Schema)
  - **Blocks**: None (enables richer features)

## Goal

Implement persistent user preferences across sessions with automatic injection into new sessions.

## Detailed Tasks

### Task 1: Create UserPreferenceService

**Description**: Service for managing user preferences.

**Implementation Details**:
- [ ] Create packages/backend/app/services/user_preference.py
- [ ] Implement save_preference()
- [ ] Implement get_preferences()
- [ ] Implement update_preference()

**Files to create**:
- `packages/backend/app/services/user_preference.py`

**Acceptance Criteria**:
- [ ] Preferences persist across sessions

---

### Task 2: Integrate with orchestrator

**Description**: Load preferences at session start.

**Implementation Details**:
- [ ] Modify packages/backend/app/engine/orchestrator.py
- [ ] Load preferences before starting agent
- [ ] Pass preferences to prompt builder

**Files to modify**:
- `packages/backend/app/engine/orchestrator.py`

**Acceptance Criteria**:
- [ ] Preferences loaded on session start

---

### Task 3: Inject into system prompt

**Description**: Add preferences to system prompt generation.

**Implementation Details**:
- [ ] Modify packages/backend/app/engine/prompts.py
- [ ] Add user_preferences section
- [ ] Format as structured prompt

**Implementation**:
```
## 用户偏好（从历史 session 记忆）
- 偏好深色模式
- 常用字体: Inter
- 喜欢的组件: card, list, button
```

**Files to modify**:
- `packages/backend/app/engine/prompts.py`

**Acceptance Criteria**:
- [ ] Agent sees preference context

---

### Task 4: Auto-update preferences

**Description**: Learn preferences from user behavior.

**Implementation Details**:
- [ ] Track user choices during session
- [ ] Update preferences automatically
- [ ] Allow session to override

**Files to modify**:
- `packages/backend/app/services/user_preference.py`

**Acceptance Criteria**:
- [ ] Preferences improve over time

## Technical Specifications

### Preference Storage

```python
class UserPreference(BaseModel):
    session_id: str
    color_scheme: Optional[str] = "light"
    font_family: Optional[str] = "Inter"
    layout_mode: Optional[str] = "single"
    favorite_components: list[str] = []
    created_at: datetime
    updated_at: datetime
```

### Prompt Injection Format

```
## 用户偏好（从历史 session 记忆）
- 偏好深色模式
- 常用字体: Inter
- 喜欢的组件: card, list, button
```

## Testing Requirements

- [ ] Test preference persistence
- [ ] Test prompt injection
- [ ] Test override behavior

## Notes & Warnings

- Feature flag: USE_CROSS_SESSION_MEMORY
- Privacy: Only store preferences, not content
- Default to off for privacy
