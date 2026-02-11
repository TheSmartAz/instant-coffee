# Instant Coffee E2E 测试文档

> **版本**: v1.0
> **生成时间**: 2026-02-10
> **覆盖范围**: 前端 + 后端端到端测试

---

## 目录

1. [测试架构](#测试架构)
2. [测试环境配置](#测试环境配置)
3. [后端 E2E 测试用例](#后端-e2e-测试用例)
4. [前端 E2E 测试用例](#前端-e2e-测试用例)
5. [集成测试场景](#集成测试场景)
6. [测试数据准备](#测试数据准备)
7. [运行测试](#运行测试)
8. [CI/CD 集成](#cicd-集成)

---

## 测试架构

### 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 后端 E2E | pytest + pytest-asyncio | Python 异步测试 |
| 前端 E2E | Playwright | 浏览器自动化测试 |
| API 测试 | FastAPI TestClient | HTTP 层测试 |
| Mock 工具 | pytest fixtures + monkeypatch | 测试数据模拟 |

### 目录结构

```
instant-coffee/
├── packages/
│   ├── backend/
│   │   └── tests/
│   │       ├── e2e/                    # 后端 E2E 测试
│   │       │   ├── conftest.py         # 共享 fixtures
│   │       │   ├── test_full_generation_e2e.py
│   │       │   ├── test_orchestrator_routing_e2e.py
│   │       │   ├── test_product_doc_tiers_e2e.py
│   │       │   ├── test_style_reference_e2e.py
│   │       │   ├── test_chat_images_e2e.py
│   │       │   ├── test_data_protocol_e2e.py
│   │       │   ├── test_aesthetic_scoring_e2e.py
│   │       │   ├── test_multi_model_routing_e2e.py
│   │       │   └── test_model_fallback_e2e.py
│   │       └── test_*.py                # 单元测试
│   └── web/
│       └── src/
│           └── e2e/                    # 前端 E2E 测试
│               ├── PreviewBridge.spec.ts
│               ├── DataTab.spec.ts
│               ├── ImageUpload.spec.ts
│               ├── AssetUpload.spec.ts
│               └── v08DataTabOverhaul.spec.ts
└── docs/
    └── e2e-test-plan.md                 # 本文档
```

---

## 测试环境配置

### 后端测试 Fixtures (packages/backend/tests/e2e/conftest.py)

```python
@pytest.fixture()
def test_settings(monkeypatch, tmp_path):
    """临时测试环境配置"""
    # 临时输出目录
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 临时数据库
    db_path = tmp_path / "test.db"

    # Mock 环境变量
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEFAULT_KEY", "test-key")
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    # ...

@pytest.fixture()
def test_client(test_db, test_settings):
    """FastAPI TestClient"""
    app = create_app()
    return TestClient(app)
```

### 前端测试 Mock 工具

```typescript
// API Mock 设置
const setupApiMocks = async (page: Page, options: MockOptions) => {
  // Mock /api/settings
  await page.route('**/api/settings', (route) =>
    route.fulfill({ status: 200, body: JSON.stringify(mockSettings) })
  )
  // Mock /api/sessions/{id}
  // Mock /api/sessions/{id}/messages
  // ...
}
```

---

## 后端 E2E 测试用例

### B1. 完整生成流程 (test_full_generation_e2e.py)

#### B1.1 电商站点完整生成

```python
def test_ecommerce_flow_generation(test_db, test_settings, output_dir, monkeypatch):
    """
    验证从用户输入到生成完整电商站点的流程

    验收标准:
    1. Product Doc 正确生成并持久化
    2. HTML 预览生成
    3. State Contract 正确生成
    4. 共享脚本 (data-store.js, data-client.js) 生成
    """
```

**测试步骤**:
1. 创建测试 Session
2. Mock ProductDocAgent.generate() 返回电商结构化数据
3. Mock AgentOrchestrator._run_generation_pipeline()
4. 运行 orchestrator.stream_responses()
5. 验证:
   - `preview_html` 非空
   - `state-contract.json` 存在且包含 `shared_state_key`, `schema`
   - `data-store.js` 和 `data-client.js` 存在

#### B1.2 多页状态共享

```python
def test_multi_page_state_sharing(test_db, test_settings, output_dir, monkeypatch):
    """
    验证多页面之间的状态共享机制

    验收标准:
    1. shared/data-store.js 包含 InstantCoffeeDataStore
    2. shared/data-client.js 包含数据客户端
    3. 正确的 storage key 配置
    """
```

---

### B2. 编排路由 (test_orchestrator_routing_e2e.py)

#### B2.1 电商分类路由

```python
def test_ecommerce_classification_routing(test_db, test_settings):
    """
    验证用户意图识别和技能路由

    验收标准:
    1. 产品类型识别为 ecommerce
    2. 置信度 >= 0.5
    3. skill_id 包含 ecommerce
    4. doc_tier 在 {checklist, standard, extended} 中
    5. guardrails 包含至少 3 条硬约束
    6. Session metadata 正确更新
    """
```

#### B2.2 着陆页路由到 checklist

```python
def test_landing_page_routes_to_checklist(test_db, test_settings):
    """
    验证简单场景使用轻量级文档层级

    验收标准:
    1. product_type == "landing"
    2. skill_id == "static-landing-v1"
    3. doc_tier == "checklist"
    """
```

#### B2.3 页面提及解析

```python
def test_page_mentions_resolve_targets(test_db, test_settings):
    """
    验证 @Page 语法正确解析目标页面

    验收标准:
    1. @Home 正确解析到 home 页面
    2. @About 不会被包含在目标中
    """
```

---

### B3. Product Doc 文档层级 (test_product_doc_tiers_e2e.py)

#### B3.1 Checklist 层级

```python
def test_checklist_tier_minimal_structured(test_db, test_settings):
    """
    验证 checklist 层级生成最小化结构化输出

    验收标准:
    1. 只包含基础字段 (project_name, product_type)
    2. 不包含详细的设计方向
    3. 不包含完整的状态契约
    """
```

#### B3.2 Standard 层级

```python
def test_standard_tier_full_structured(test_db, test_settings):
    """
    验证 standard 层级生成完整结构化输出

    验收标准:
    1. 包含所有基础字段
    2. 包含设计方向
    3. 包含完整的 pages 列表
    4. 包含状态契约和数据流
    """
```

#### B3.3 Extended 层级

```python
def test_extended_tier_with_all_features(test_db, test_settings):
    """
    验证 extended 层级生成扩展功能

    验收标准:
    1. 包含所有 standard 层级内容
    2. 包含 SEO 元数据
    3. 包含国际化配置
    4. 包含高级交互模式
    """
```

---

### B4. 风格参考 (test_style_reference_e2e.py)

#### B4.1 图片风格提取

```python
def test_image_style_extraction(test_db, test_settings, sample_style_reference_image):
    """
    验证从参考图片提取设计风格

    验收标准:
    1. 成功解析图片
    2. 提取颜色信息 (主色、辅助色、背景色)
    3. 提取字体信息
    4. 提取布局特征
    5. 生成的 global_style 包含提取的信息
    """
```

#### B4.2 风格应用到生成

```python
def test_style_applied_to_generation(test_db, test_settings, sample_style_reference_image):
    """
    验证提取的风格应用到生成的 HTML

    验收标准:
    1. 生成的 HTML 包含提取的颜色
    2. CSS 样式与参考图片一致
    3. 字体大小和间距符合参考
    """
```

---

### B5. 聊天图片处理 (test_chat_images_e2e.py)

#### B5.1 单图片上传

```python
def test_single_image_upload(test_client, sample_png_base64):
    """
    验证单图片上传和处理

    验收标准:
    1. 图片成功上传
    2. 返回图片 URL
    3. Orchestrator 接收到图片信息
    """
```

#### B5.2 多图片限制

```python
def test_max_three_images_enforced(test_client, sample_png_base64):
    """
    验证最多 3 张图片的限制

    验收标准:
    1. 1-3 张图片正常处理
    2. 第 4 张图片被拒绝
    3. 返回明确的错误消息
    """
```

#### B5.3 图片大小限制

```python
def test_image_size_limit_enforced(test_client):
    """
    验证 10MB 图片大小限制

    验收标准:
    1. < 10MB 图片正常处理
    2. > 10MB 图片被拒绝
    3. 返回明确的错误消息
    """
```

---

### B6. 数据协议 (test_data_protocol_e2e.py)

#### B6.1 电商状态契约生成

```python
def test_ecommerce_state_contract_generation(test_db, test_settings, output_dir):
    """
    验证电商场景的状态契约生成

    验收标准:
    1. cart 状态定义正确
    2. items 数组结构正确
    3. 事件定义包含 add_to_cart, remove_from_cart, update_quantity
    """
```

#### B6.2 数据存储脚本注入

```python
def test_data_store_script_injection(test_db, test_settings, output_dir):
    """
    验证数据存储脚本正确注入到 HTML

    验收标准:
    1. data-store.js 脚本注入到 <head>
    2. data-client.js 脚本注入到 <body> 末尾
    3. 初始化参数正确传递
    """
```

#### B6.3 场景覆盖

```python
@pytest.mark.parametrize("scenario", [
    "ecommerce",
    "travel",
    "manual",
    "dashboard",
    "landing"
])
def test_all_scenario_contracts(test_db, test_settings, output_dir, scenario):
    """
    验证所有场景的状态契约生成
    """
```

---

### B7. 审美评分 (test_aesthetic_scoring_e2e.py)

#### B7.1 视觉评分计算

```python
def test_aesthetic_score_calculation(test_db, test_settings):
    """
    验证页面视觉质量评分

    验收标准:
    1. 返回 0-100 的分数
    2. 分数基于多个维度 (对比度、对齐、留白、颜色和谐度)
    3. 返回详细的改进建议
    """
```

#### B7.2 评分阈值触发

```python
def test_score_threshold_triggers_refinement(test_db, test_settings):
    """
    验证低分触发自动优化

    验收标准:
    1. 分数 < 60 时触发 StyleRefiner
    2. 优化后分数提升
    3. 优化过程不超过 2 轮
    """
```

---

### B8. 多模型路由 (test_multi_model_routing_e2e.py)

#### B8.1 按角色路由

```python
def test_role_based_routing(test_db, test_settings):
    """
    验证按 Agent 角色路由到不同模型

    验收标准:
    1. Interview Agent 使用轻量级模型
    2. Generation Agent 使用中等模型
    3. Refinement Agent 使用重量级模型
    """
```

#### B8.2 模型失败回退

```python
def test_model_fallback_on_failure(test_db, test_settings):
    """
    验证模型失败时的回退机制

    验收标准:
    1. 主模型失败时自动切换到备用模型
    2. 最多尝试 3 次
    3. 失败记录正确
    """
```

---

## 前端 E2E 测试用例

### F1. 数据标签页 (DataTab.spec.ts)

#### F1.1 基础渲染

```typescript
test('1. Component renders in Preview panel', async ({ page }) => {
  /**
   * 验收标准:
   * 1. Data Tab 在 Preview Panel 中可见
   * 2. 三个子区域 (State, Events, Records) 默认可见
   * 3. 每个区域可折叠
   * 4. 空状态正确显示
   */
})
```

#### F1.2 JSON 格式化

```typescript
test('5. JSON formatted and readable', async ({ page }) => {
  /**
   * 验收标准:
   * 1. JSON 数据格式化显示
   * 2. 支持大对象折叠展开
   * 3. 复制按钮工作正常
   */
})
```

#### F1.3 事件排序

```typescript
test('8. Events display in reverse chronological order', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 事件按时间倒序显示
   * 2. 时间戳格式化为人可读
   * 3. 自动滚动到最新事件
   */
})
```

#### F1.4 记录导出

```typescript
test('13. Export downloads JSON', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 点击导出按钮下载 JSON 文件
   * 2. 文件名包含时间戳
   * 3. 数据格式正确
   */
})
```

---

### F2. 图片上传 (ImageUpload.spec.ts)

#### F2.1 文件选择器

```typescript
test('1. Image button opens file picker', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 点击图片按钮打开文件选择器
   * 2. 只接受图片类型
   */
})
```

#### F2.2 拖拽上传

```typescript
test('2. Drag-and-drop works on textarea', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 支持拖拽上传
   * 2. 显示上传进度
   * 3. 上传完成后显示缩略图
   */
})
```

#### F2.3 数量限制

```typescript
test('5. Max 3 images enforced', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 最多 3 张图片
   * 2. 超过限制时显示错误
   * 3. 可以删除已上传图片
   */
})
```

#### F2.4 大小限制

```typescript
test('7. Files > 10MB rejected', async ({ page }) => {
  /**
   * 验收标准:
   * 1. > 10MB 文件被拒绝
   * 2. 显示明确的错误消息
   */
})
```

---

### F3. 页面提及 (@Page Mention)

#### F3.1 下拉菜单

```typescript
test('8. Dropdown appears after @ with filtering', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 输入 @ 显示页面列表
   * 2. 支持输入过滤
   * 3. 无匹配时显示空状态
   */
})
```

#### F3.2 键盘导航

```typescript
test('9. Keyboard navigation and click-to-select work', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 上下箭头导航
   * 2. Enter 选择
   * 3. Escape 关闭
   */
})
```

#### F3.3 光标位置插入

```typescript
test('10. @Page inserted at cursor position', async ({ page }) => {
  /**
   * 验收标准:
   * 1. @Page 插入到光标位置
   * 2. 不是文本末尾
   */
})
```

---

### F4. 预览消息桥接 (PreviewBridge.spec.ts)

#### F4.1 状态更新

```typescript
test('1. Hook returns current state, events, and records', async ({ page }) => {
  /**
   * 验收标准:
   * 1. Hook 返回当前状态
   * 2. 返回事件列表
   * 3. 返回提交记录
   * 4. 返回连接状态和时间戳
   */
})
```

#### F4.2 消息过滤

```typescript
test('3. Messages filtered by type guard', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 只处理 instant-coffee:update 消息
   * 2. 忽略未知类型消息
   * 3. 格式错误消息不会崩溃
   */
})
```

#### F4.3 防抖处理

```typescript
test('5. Debounced updates for non-submit events', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 非提交事件使用防抖
   * 2. 快速连续更新不会过载 UI
   * 3. 提交事件立即更新
   */
})
```

---

### F5. 资产上传 (AssetUpload.spec.ts)

#### F5.1 资产类型选择

```typescript
test('1. Asset type selector renders all options', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 显示所有资产类型: logo, style_ref, background, product_image
   * 2. 点击类型后打开文件选择器
   */
})
```

#### F5.2 上传流程

```typescript
test('2. Upload flow renders asset thumbnail', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 显示上传进度
   * 2. 上传完成后显示缩略图
   * 3. 缩略图包含资产 ID
   */
})
```

---

### F6. v08 数据标签页重构 (v08DataTabOverhaul.spec.ts)

#### F6.1 顶级标签页

```typescript
test('shows Data as top-level workbench tab', async ({ page }) => {
  /**
   * 验收标准:
   * 1. Data 是顶级 Workbench 标签
   * 2. 与 Preview、Code、Product Doc 并列
   */
})
```

#### F6.2 表格视图

```typescript
test('table view renders tables, rows and pagination', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 显示所有表标签
   * 2. 显示数据行
   * 3. 分页工作正常
   */
})
```

#### F6.3 仪表板视图

```typescript
test('dashboard view renders summaries and distributions', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 显示表摘要
   * 2. 显示数值聚合
   * 3. 显示布尔分布
   */
})
```

#### F6.4 实时刷新

```typescript
test('refreshes table data when receiving postMessage refresh signal', async ({ page }) => {
  /**
   * 验收标准:
   * 1. 接收到 data_changed 消息时刷新
   * 2. 刷新时显示加载状态
   * 3. 新数据正确显示
   */
})
```

---

## 集成测试场景

### 场景 1: 完整用户旅程 - 电商站点

```python
def test_full_ecommerce_user_journey():
    """
    从零开始创建电商站点的完整用户旅程

    步骤:
    1. 创建新会话
    2. 发送 "创建一个在线商店" 消息
    3. 回答 Interview 问题 (3-5 轮)
    4. 等待生成完成
    5. 验证 Product Doc
    6. 验证 HTML 预览
    7. 验证数据协议脚本
    8. 发送 "添加产品详情页" 消息
    9. 验证新页面生成
    10. 验证页面间链接正确
    """
```

### 场景 2: 多页面协作

```python
def test_multi_page_collaboration():
    """
    创建包含多个页面的站点并验证页面间协作

    步骤:
    1. 创建会话
    2. 生成首页 + 产品页 + 购物车页
    3. 在首页添加产品
    4. 验证购物车状态更新
    5. 提交订单
    6. 验证记录创建
    """
```

### 场景 3: 风格参考应用

```python
def test_style_reference_application():
    """
    上传参考图片并验证风格应用

    步骤:
    1. 创建会话
    2. 上传风格参考图片
    3. 发送 "使用这个风格创建着陆页" 消息
    4. 验证生成的 HTML 使用参考图片的风格
    """
```

### 场景 4: 版本控制与回滚

```python
def test_version_control_and_rollback():
    """
    验证版本控制和回滚功能

    步骤:
    1. 生成初始页面
    2. 修改页面 (版本 2)
    3. 再次修改 (版本 3)
    4. 验证版本历史
    5. 回滚到版本 2
    6. 验证内容正确恢复
    """
```

### 场景 5: 构建与预览

```python
def test_build_and_preview():
    """
    验证 React SSG 构建流程

    步骤:
    1. 生成多页面站点
    2. 触发构建
    3. 监听构建事件流
    4. 验证构建产物
    5. 验证预览 URL
    """
```

### 场景 6: 错误恢复

```python
def test_error_recovery():
    """
    验证各种错误场景的恢复

    步骤:
    1. LLM 调用失败 -> 重试
    2. 数据库写入失败 -> 回滚
    3. 文件系统错误 -> 使用备用路径
    4. 网络超时 -> 使用备用模型
    """
```

---

## 测试数据准备

### 示例图片

```python
@pytest.fixture()
def sample_png_base64():
    """1x1 像素透明 PNG 用于测试"""
    return "data:image/png;base64,iVBORw0KGgo..."

@pytest.fixture()
def sample_style_reference_image(tmp_path):
    """风格参考图片"""
    # 创建临时图片文件
    path = tmp_path / "style-ref.png"
    # ...
    return path
```

### 示例会话数据

```python
@pytest.fixture()
def sample_session():
    """示例会话数据"""
    return {
        "id": "test-session-123",
        "title": "Test Ecommerce Site",
        "product_type": "ecommerce",
        "doc_tier": "standard",
    }
```

### 示例 Product Doc

```python
@pytest.fixture()
def sample_product_doc():
    """示例产品文档"""
    return {
        "project_name": "Test Store",
        "product_type": "ecommerce",
        "pages": [
            {"slug": "home", "title": "Home", "role": "catalog"},
            {"slug": "cart", "title": "Cart", "role": "checkout"},
        ],
        "state_contract": {
            "cart": {"items": []},
        },
    }
```

---

## 运行测试

### 后端 E2E 测试

```bash
# 运行所有后端 E2E 测试
cd packages/backend
pytest tests/e2e/ -v

# 运行特定测试文件
pytest tests/e2e/test_full_generation_e2e.py -v

# 运行特定测试用例
pytest tests/e2e/test_full_generation_e2e.py::TestFullGenerationFlowE2E::test_ecommerce_flow_generation -v

# 带覆盖率报告
pytest tests/e2e/ --cov=app --cov-report=html

# 并行运行 (需要 pytest-xdist)
pytest tests/e2e/ -n auto
```

### 前端 E2E 测试

```bash
# 运行所有前端 E2E 测试
cd packages/web
pnpm test:e2e

# 运行特定测试文件
pnpm test:e2e DataTab.spec.ts

# 运行特定测试用例
pnpm test:e2e --grep "Component renders"

# 调试模式 (打开浏览器窗口)
pnpm test:e2e --debug

# 生成测试报告
pnpm test:e2e --reporter=html
```

### API 集成测试

```bash
# 启动测试服务器
cd packages/backend
uvicorn app.main:app --reload --port 8001

# 运行集成测试
pytest tests/integration/ --base-url=http://localhost:8001
```

---

## CI/CD 集成

### GitHub Actions 配置示例

```yaml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  backend-e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          cd packages/backend
          pip install -e ".[test]"
      - name: Run E2E tests
        run: |
          cd packages/backend
          pytest tests/e2e/ -v --cov=app

  frontend-e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - name: Install dependencies
        run: |
          cd packages/web
          pnpm install
      - name: Install Playwright
        run: |
          cd packages/web
          pnpm exec playwright install --with-deps
      - name: Run E2E tests
        run: |
          cd packages/web
          pnpm test:e2e
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: packages/web/playwright-report/
```

---

## 测试覆盖率目标

| 层级 | 目标覆盖率 | 当前状态 |
|------|-----------|----------|
| 后端 API 层 | 80%+ | 🟡 |
| 后端 Service 层 | 85%+ | 🟢 |
| 后端 Agent 层 | 70%+ | 🟡 |
| 前端组件 | 75%+ | 🟡 |
| 前端 Hooks | 80%+ | 🟡 |
| E2E 场景覆盖 | 90%+ | 🟡 |

---

## 待补充的测试用例

### 后端待补充

- [ ] B9: Run Service 完整流程
- [ ] B10: App Data Store 集成测试
- [ ] B11: Thread Service 多线程管理
- [ ] B12: Background Task 异步执行
- [ ] B13: Page Diff 服务

### 前端待补充

- [ ] F7: Chat Panel 完整交互流程
- [ ] F8: Product Doc Panel 更新交互
- [ ] F9: Version Panel 版本比较
- [ ] F10: Workbench Panel 标签切换
- [ ] F11: Background Tasks Panel 任务监控
- [ ] F12: Page Diff Viewer 差异可视化

### 集成场景待补充

- [ ] S7: 并发多会话处理
- [ ] S8: 长时间会话稳定性
- [ ] S9: 大量页面性能测试
- [ ] S10: 跨会话资产共享

---

## 测试最佳实践

### 1. 测试隔离

```python
# 每个测试使用独立的数据库和输出目录
@pytest.fixture()
def test_settings(monkeypatch, tmp_path):
    # 使用临时路径
    output_dir = tmp_path / "output"
    db_path = tmp_path / "test.db"
    # ...
```

### 2. Mock 外部依赖

```python
# Mock LLM 调用以避免实际 API 消耗
monkeypatch.setattr(ProductDocAgent, "generate", _fake_product_doc_generate)
```

### 3. 明确的断言

```python
# 使用具体的断言而不是通用的
assert decision.product_type == "ecommerce"
assert decision.confidence >= 0.5
# 而不是
assert decision is not None
```

### 4. 测试数据命名

```python
# 使用描述性的测试数据名称
sample_ecommerce_product_doc
sample_landing_page_html
sample_style_reference_image
```

### 5. 等待策略

```typescript
// 使用明确的等待而不是固定延迟
await expect(page.locator('[data-testid="data-tab"]')).toBeVisible()
// 而不是
await page.waitForTimeout(1000)
```

---

## 附录: 测试命令速查

```bash
# 后端
pytest tests/e2e/ -v                    # 所有 E2E
pytest tests/e2e/ -k "ecommerce" -v     # 关键词过滤
pytest tests/e2e/ --maxfail=1           # 首次失败停止
pytest tests/e2e/ -x -v                 # 同上

# 前端
pnpm test:e2e                           # 所有 E2E
pnpm test:e2e --grep "Data Tab"         # 正则过滤
pnpm test:e2e --project=chromium        # 特定浏览器
pnpm test:e2e --headed                  # 有头模式
```

---

*本文档随项目演进持续更新*
