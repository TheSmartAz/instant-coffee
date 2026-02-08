# Phase B5: Mobile Shell Auto-fix

## Metadata

- **Category**: Backend
- **Priority**: P0 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel with B4
- **Dependencies**:
  - **Blocked by**: None (can start anytime)
  - **Blocks**: None (standalone service)

## Goal

Implement HTML post-processing to ensure all generated pages meet mobile compatibility requirements including viewport, app container, and touch target standards.

## Detailed Tasks

### Task 1: Create ensure_mobile_shell Function

**Description**: Implement the core mobile shell injection function using BeautifulSoup

**Implementation Details**:
- [ ] Create `packages/backend/app/services/mobile_shell.py`
- [ ] Implement ensure_mobile_shell(html: str) -> str
- [ ] Add viewport meta tag injection
- [ ] Add #app.page container creation
- [ ] Inject mobile CSS constraints

**Files to create**:
- `packages/backend/app/services/mobile_shell.py`

**Acceptance Criteria**:
- [ ] Viewport meta tag present with correct content
- [ ] #app.page container exists
- [ ] max-width: min(430px, 100%) applied
- [ ] Touch targets minimum 44px
- [ ] Scrollbar hidden

---

### Task 2: Implement Mobile Validation Rules

**Description**: Create validation check functions for each mobile requirement

**Implementation Details**:
- [ ] Add MOBILE_VALIDATION_RULES list
- [ ] Implement viewport, app_container, max_width, touch_targets checks
- [ ] Create auto_fix flags for each rule
- [ ] Add check_touch_targets helper

**Files to modify**:
- `packages/backend/app/services/mobile_shell.py`

**Acceptance Criteria**:
- [ ] Each rule has id, description, check, auto_fix
- [ ] Returns validation report with pass/fail
- [ ] Auto-fix rules actually fix issues

---

### Task 3: Integrate with Render Pipeline

**Description**: Wire mobile shell processing after Vite build

**Implementation Details**:
- [ ] Modify `packages/backend/app/renderer/builder.py`
- [ ] After build completes, iterate through dist/*.html
- [ ] Apply ensure_mobile_shell to each file
- [ ] Write fixed content back

**Files to modify**:
- `packages/backend/app/renderer/builder.py`

**Acceptance Criteria**:
- [ ] All HTML files processed after build
- [ ] Mobile shell CSS appended to head
- [ ] Original content preserved with shell injected

---

### Task 4: Create CLI/Testing Tool

**Description**: Create standalone script for testing mobile shell on HTML

**Implementation Details**:
- [ ] Create `packages/backend/app/cli/mobile_shell_cli.py`
- [ ] Accept HTML file path as input
- [ ] Output validation report
- [ ] Support --fix flag for in-place modification

**Files to create**:
- `packages/backend/app/cli/mobile_shell_cli.py`

**Acceptance Criteria**:
- [ ] CLI validates HTML correctly
- [ ] Report shows all rule results
- [ ] --fix applies auto-fix rules

## Technical Specifications

### ensure_mobile_shell Function

```python
from bs4 import BeautifulSoup

def ensure_mobile_shell(html: str) -> str:
    """
    自动修复 HTML 以确保移动端兼容性

    修复项：
    1. viewport meta 标签
    2. #app.page 根容器
    3. 基础 CSS 约束
    """
    soup = BeautifulSoup(html, 'html.parser')

    # 1. 确保 viewport meta
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    if not viewport:
        viewport = soup.new_tag('meta')
        viewport['name'] = 'viewport'
        head = soup.find('head') or soup.new_tag('head')
        if not soup.find('head'):
            soup.html.insert(0, head)
        head.insert(0, viewport)
    viewport['content'] = 'width=device-width, initial-scale=1, viewport-fit=cover, maximum-scale=1'

    # 2. 确保 #app.page 容器
    body = soup.find('body')
    if body:
        app_container = soup.find(id='app')
        if not app_container:
            app_container = soup.new_tag('div')
            app_container['id'] = 'app'
            app_container['class'] = ['page']
            for child in list(body.children):
                app_container.append(child.extract())
            body.append(app_container)
        elif 'page' not in app_container.get('class', []):
            app_container['class'] = app_container.get('class', []) + ['page']

    # 3. 注入基础 CSS
    mobile_css = """
    <style id="mobile-shell">
      * { box-sizing: border-box; }
      html, body {
        margin: 0;
        padding: 0;
        min-height: 100dvh;
        -webkit-font-smoothing: antialiased;
      }
      #app.page {
        max-width: min(430px, 100%);
        width: 100%;
        margin: 0 auto;
        min-height: 100dvh;
        overflow-x: hidden;
        position: relative;
      }
      /* 隐藏滚动条 */
      ::-webkit-scrollbar { display: none; }
      * { scrollbar-width: none; }
      /* 触摸优化 */
      button, a, [role="button"] {
        min-height: 44px;
        touch-action: manipulation;
      }
    </style>
    """
    existing_shell = soup.find('style', id='mobile-shell')
    if not existing_shell:
        head = soup.find('head')
        if head:
            head.append(BeautifulSoup(mobile_css, 'html.parser'))

    return str(soup)
```

### Validation Rules

```python
MOBILE_VALIDATION_RULES = [
    {
        "id": "viewport",
        "description": "必须包含正确的 viewport meta",
        "check": lambda soup: soup.find('meta', attrs={'name': 'viewport'}) is not None,
        "auto_fix": True
    },
    {
        "id": "app_container",
        "description": "必须包含 #app.page 容器",
        "check": lambda soup: soup.find(id='app') is not None,
        "auto_fix": True
    },
    {
        "id": "max_width",
        "description": "#app 容器必须设置 max-width",
        "check": lambda soup: (
            soup.find('style', id='mobile-shell') and 'max-width' in soup.find('style', id='mobile-shell').text
        ) or (
            soup.find(id='app') and 'max-width' in str(soup.find(id='app').get('style', ''))
        ),
        "auto_fix": True
    },
    {
        "id": "touch_targets",
        "description": "可点击元素最小高度 44px",
        "check": check_touch_targets,
        "auto_fix": False
    }
]
```

## Testing Requirements

- [ ] Unit test: ensure_mobile_shell with raw HTML
- [ ] Unit test: Validation rules with various HTML
- [ ] Integration test: Build pipeline mobile shell integration
- [ ] Test edge cases: malformed HTML, missing elements
- [ ] Verify 100% validation pass rate

## Notes & Warnings

- BeautifulSoup4 required for HTML parsing
- CSS injection order matters (should be in head)
- #app.page with space in class is intentional
- 9:19.5 ratio is for Preview only, not enforced in generated HTML
