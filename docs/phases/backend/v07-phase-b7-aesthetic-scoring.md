# Phase B7: Aesthetic Scoring

## Metadata

- **Category**: Backend
- **Priority**: P1 (Optional but Important)
- **Estimated Complexity**: High
- **Parallel Development**: ✅ Can develop in parallel with B4
- **Dependencies**:
  - **Blocked by**: None (optional feature)
  - **Blocks**: None (can be disabled independently)

## Goal

Implement optional visual quality assessment that scores pages across 6 dimensions and provides optimization suggestions.

## Detailed Tasks

### Task 1: Define Aesthetic Scoring Schema

**Description**: Create Pydantic models for scores, dimensions, and suggestions

**Implementation Details**:
- [ ] Create `packages/backend/app/schemas/aesthetic.py`
- [ ] Define AestheticScore, AestheticDimension, AestheticSuggestion classes
- [ ] Add severity enum (info/warning/critical)
- [ ] Define passThreshold and thresholds per product type

**Files to create**:
- `packages/backend/app/schemas/aesthetic.py`

**Acceptance Criteria**:
- [ ] Schema matches spec section 12.4
- [ ] All 6 dimensions covered
- [ ] Thresholds configurable per scenario

---

### Task 2: Implement AestheticScorerAgent

**Description**: Create LLM-based scoring agent with Vision API support

**Implementation Details**:
- [ ] Create `packages/backend/app/services/aesthetic_scorer.py`
- [ ] Implement AestheticScorerAgent class
- [ ] Add SCORING_PROMPT with 6 dimension criteria
- [ ] Implement score(page_schema, rendered_html, style_tokens) -> AestheticScore
- [ ] Add _parse_score(response) helper

**Files to create**:
- `packages/backend/app/services/aesthetic_scorer.py`

**Acceptance Criteria**:
- [ ] Returns scores for all 6 dimensions
- [ ] Generates actionable suggestions
- [ ] Parses LLM JSON response correctly

---

### Task 3: Implement Auto-fix Suggestions

**Description**: Create functions to automatically apply fixable suggestions

**Implementation Details**:
- [ ] Add auto_fix_suggestions(page_schema, suggestions) function
- [ ] Implement fix_touch_targets() for mobile adaptation
- [ ] Implement fix_spacing() for spacing consistency
- [ ] Support dimension-specific fixes

**Files to modify**:
- `packages/backend/app/services/aesthetic_scorer.py`

**Acceptance Criteria**:
- [ ] Auto-fixable suggestions actually modify schema
- [ ] Changes reflected in next build
- [ ] Non-fixable suggestions returned for manual review

---

### Task 4: Create Aesthetic Scorer Node

**Description**: Implement aesthetic_scorer_node for LangGraph conditional execution

**Implementation Details**:
- [ ] Create `packages/backend/app/graph/nodes/aesthetic_scorer.py`
- [ ] Implement aesthetic_scorer_node(state) function
- [ ] Check should_score_aesthetic condition
- [ ] Call AestheticScorerAgent.score()
- [ ] Update state with scores and suggestions
- [ ] Route back to check_refine

**Files to create**:
- `packages/backend/app/graph/nodes/aesthetic_scorer.py`

**Acceptance Criteria**:
- [ ] Node only runs for Landing/Card/Invitation when enabled
- [ ] State updates with scores and suggestions
- [ ] Pass/fail threshold correctly evaluated

---

### Task 5: Add Feature Flag Control

**Description**: Ensure scoring can be disabled via configuration

**Implementation Details**:
- [ ] Update `packages/backend/app/config.py`
- [ ] Add ENABLE_AESTHETIC_SCORING flag (default false)
- [ ] Check flag in should_score_aesthetic function
- [ ] Document flag in .env.example

**Files to modify**:
- `packages/backend/app/config.py`

**Acceptance Criteria**:
- [ ] Flag defaults to false
- [ ] Setting true enables scoring
- [ ] Frontend can query flag state

## Technical Specifications

### Scoring Dimensions

| 维度 | 权重 | 说明 | 评分标准 |
|------|------|------|---------|
| **视觉层次** | 25% | 信息层级清晰度 | 标题/正文/辅助文字的对比度 |
| **色彩和谐** | 20% | 色彩搭配协调性 | 主色/辅色/强调色的搭配 |
| **间距一致性** | 20% | 元素间距的规律性 | 符合 8px 栅格系统 |
| **对齐规范** | 15% | 元素对齐方式 | 左对齐/居中/右对齐一致 |
| **可读性** | 10% | 文字可读性 | 字号、行高、对比度 |
| **移动端适配** | 10% | 移动端体验 | 触摸目标、滚动体验 |

### Score Thresholds

| 场景 | 通过阈值 | 建议阈值 |
|------|---------|---------|
| Landing | 70 | 85 |
| Card | 65 | 80 |
| 其他 | 60 | 75 |

### AestheticScore Schema

```python
from typing import List, Optional
from pydantic import BaseModel

class AestheticScore(BaseModel):
    overall: int              # 总分 0-100
    dimensions: dict          # 各维度分数
    suggestions: List['AestheticSuggestion']
    passThreshold: bool      # 是否通过阈值

class AestheticSuggestion(BaseModel):
    dimension: str            # 所属维度
    severity: str            # "info" | "warning" | "critical"
    message: str             # 建议内容
    location: Optional[str]   # 涉及的组件/位置
    autoFixable: bool        # 是否可自动修复

class AestheticScorerAgent:
    SCORING_PROMPT = """
    分析这个页面的视觉设计质量，从以下维度评分（0-100）：

    1. **视觉层次 (Visual Hierarchy)**: 信息层级是否清晰？
    2. **色彩和谐 (Color Harmony)**: 色彩搭配是否协调？
    3. **间距一致性 (Spacing Consistency)**: 元素间距是否规律？
    4. **对齐规范 (Alignment)**: 元素对齐方式是否一致？
    5. **可读性 (Readability)**: 文字是否易读？
    6. **移动端适配 (Mobile Adaptation)**: 触摸目标是否足够大？

    返回 JSON 格式：
    ```json
    {
      "overall": 75,
      "dimensions": {
        "visualHierarchy": 80,
        "colorHarmony": 70,
        "spacingConsistency": 75,
        "alignment": 85,
        "readability": 72,
        "mobileAdaptation": 68
      },
      "suggestions": [
        {
          "dimension": "mobileAdaptation",
          "severity": "warning",
          "message": "底部按钮高度不足 44px，建议增加到 48px",
          "location": "button-primary",
          "autoFixable": true
        }
      ]
    }
    ```
    """

    async def score(
        self,
        page_schema: dict,
        rendered_html: Optional[str],
        style_tokens: dict
    ) -> AestheticScore:
        # Implementation
        pass
```

### Auto-fix Functions

```python
async def auto_fix_suggestions(
    page_schema: dict,
    suggestions: List[AestheticSuggestion]
) -> dict:
    """自动应用可修复的建议"""
    for suggestion in suggestions:
        if not suggestion.autoFixable:
            continue

        if suggestion.dimension == "mobileAdaptation":
            fix_touch_targets(page_schema, suggestion)
        elif suggestion.dimension == "spacingConsistency":
            fix_spacing(page_schema, suggestion)
        # ... 其他修复逻辑

    return page_schema
```

## Testing Requirements

- [ ] Unit test: Score parsing from LLM response
- [ ] Unit test: Threshold evaluation
- [ ] Integration test: Full scoring workflow
- [ ] Test auto-fix suggestion application
- [ ] Performance test: Scoring latency < 15 seconds

## Notes & Warnings

- Feature is optional and disabled by default
- Requires Vision API for HTML-based scoring
- When HTML not available, score based on schema + tokens
- Suggestions should be actionable, not vague
- Auto-fix should have dry-run mode option
