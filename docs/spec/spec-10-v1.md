# Spec v1.0: 生成可靠性 + 对话智能 + 前端升级 + 部署导出 + 数据分析

**Version**: v1.0
**Status**: Planned
**Date**: 2026-02-13
**Predecessor**: v0.9 (Soul Agentic Loop)

---

## 1. Motivation

### 1.1 Current State

v0.9 (Soul Agentic Loop) 将 LangGraph 替换为 tool-calling loop，核心引擎已就位。然而，用户反馈的核心痛点仍然存在：

- **生成经常失败/不完整** — token 计算不精确、HTML 生成缺乏结构化校验、并行操作无原子性保障
- **对话体验不够智能** — 缺少跨 session 记忆、interview 超时无优雅降级、上下文注入不够丰富
- **前端架构有待升级** — ProjectPage 573 行、props drilling 严重、缺少状态管理
- **部署导出能力缺失** — 预览到上线最后一公里未打通
- **Data Tab 未真正投入使用** — 缺少访问分析和页面数据收集

### 1.2 Target State

v1.0 是第一个"大版本"，目标是让产品从"能用"变成"好用"：

- **生成可靠性提升** — 精确 token 计算、结构化 HTML 工具、原子多文件操作、model fallback、结构化 compaction
- **对话更智能** — interview 超时优雅降级、进度指示器、跨 session 记忆、更丰富的上下文注入、对话搜索
- **前端架构现代化** — Zustand 状态管理、ProjectPage 拆分、Dark Mode、键盘快捷键、错误恢复
- **部署导出能力** — 一键部署、QR 码分享、导出增强、版本关联部署
- **Data Tab 数据分析** — 页面访问追踪、数据存储、仪表盘、交互数据收集、数据导出

### 1.3 Benefits

| Dimension | v0.9 (current) | v1.0 (target) |
|-----------|----------------|----------------|
| Token 计算 | `len(text) // 3` 误差 20-30% | tiktoken 精确计算 |
| HTML 生成 | 原始 HTML 写入，缺乏校验 | 结构化 JSON + 内置校验 |
| 文件操作 | 单个文件写入，无事务 | BatchFileWrite 原子操作 |
| Model fallback | 单模型，无备选 | Provider fallback 链 |
| Interview 超时 | 无超时机制 | 5 分钟超时 + 优雅降级 |
| 跨 session 记忆 | 无 | 用户偏好持久化 |
| 前端状态 | props drilling | Zustand 全局状态 |
| ProjectPage | 573 行 | < 100 行 (拆分后) |
| 部署 | 手动复制 | 一键部署 + QR 分享 |
| 数据分析 | 空白 | 完整访问分析仪表盘 |

### 1.4 References

- **tiktoken**: OpenAI 的快速 token 计数库
- **Zustand**: React 轻量级状态管理
- **recharts**: React 数据可视化库
- **Netlify API / Vercel CLI**: 静态站点部署方案

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Theme 1: 生成可靠性                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐ │
│  │ 精确 Token 计算  │  │ 结构化 HTML 工具 │  │ 原子多文件 │ │
│  │ (tiktoken)     │  │ (generate_html)  │  │ (Batch)    │ │
│  └────────┬────────┘  └────────┬────────┘  └─────┬──────┘ │
│           │                    │                   │         │
│  ┌────────▼────────────────────▼───────────────────▼──────┐ │
│  │              Provider Fallback 链                      │ │
│  │  主模型失败 → 备选模型1 → 备选模型2 → 错误            │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                 │
│                  ┌───────▼────────┐                        │
│                  │ 结构化 Compaction │                       │
│                  │ (保留关键状态)    │                        │
│                  └─────────────────┘                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Theme 2: 对话智能 & 记忆                        │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ AskUser 超时 │  │ Interview   │  │ 跨 Session     │  │
│  │ + 优雅降级   │  │ 进度指示器   │  │ 记忆           │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                  │                    │            │
│  ┌──────▼──────────────────▼────────────────────▼────────┐ │
│  │              更丰富的上下文注入                          │ │
│  │  - 设计 token 提取                                      │ │
│  │  - 页面结构摘要                                        │ │
│  │  - 资源清单                                            │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                  │
│              ┌───────────▼───────────┐                     │
│              │ /api/messages/search  │                     │
│              └───────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Theme 3: 前端架构升级                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Zustand Store Slices                   │   │
│  │  session | chat | preview | pages | productDoc     │   │
│  │         build | version | settings                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Project   │  │ Chat     │  │Workbench │  │ Version  │  │
│  │Layout    │  │Container │  │Container │  │Sidebar   │  │
│  │(<100行)  │  │          │  │          │  │          │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                          │                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                │
│  │ Dark     │  │ 键盘     │  │ 错误恢复  │                │
│  │ Mode     │  │ 快捷键   │  │ + 重试    │                │
│  └──────────┘  └──────────┘  └──────────┘                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Theme 4: 部署 & 导出                           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ 一键部署     │  │ QR 码分享    │  │ 导出增强       │  │
│  │ (Netlify/   │  │              │  │ (ZIP/Next.js/ │  │
│  │  Vercel)    │  │              │  │  Astro)        │  │
│  └──────────────┘  └──────────────┘  └────────────────┘  │
│                          │                                  │
│              ┌───────────▼───────────┐                     │
│              │ 版本关联部署          │                     │
│              │ (回滚同步部署)        │                     │
│              └───────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Theme 5: Data Tab 数据分析                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              追踪脚本注入 (< 2KB)                    │   │
│  │  PV | UV | 设备类型 | 屏幕尺寸 | 停留时间 | 滚动深度  │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│  ┌──────────────┐  ┌─────────────────────────────────┐    │
│  │ 数据存储      │  │ Data Tab 仪表盘                 │    │
│  │ (page_       │  │ (趋势图 | 饼图 | 排名 | 实时)   │    │
│  │  analytics)  │  │                                 │    │
│  └──────────────┘  └─────────────────────────────────┘    │
│                          │                                  │
│  ┌──────────────┐  ┌──────────────┐                       │
│  │ 页面交互收集  │  │ 数据导出     │                       │
│  │ (点击/表单/  │  │ (CSV/JSON)  │                       │
│  │  热力图)     │  │              │                       │
│  └──────────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Phase Breakdown

### Phase 1: 精确 Token 计算

**Priority**: P0 (Theme 1)
**Complexity**: Medium
**Depends On**: Nothing
**Blocks**: Phase 3

#### Step 1a: tiktoken 集成

**修改文件**:

| File | Changes |
|------|---------|
| `packages/agent/src/ic/soul/context.py` | 替换 `len(text) // 3` 为 tiktoken 计数 |

**实现细节**:

- 安装 `tiktoken` 依赖
- 创建 `TokenCounter` 类，支持按模型名称选择编码：
  - `gpt-4*`, `o3*` → `cl100k_base`
  - 其他模型 → `cl100k_base`
- 替换 `estimate_tokens()` 方法：
  ```python
  def estimate_tokens(self, text: str) -> int:
      encoding = tiktoken.get_encoding("cl100k_base")
      return len(encoding.encode(text))
  ```
- 性能优化：缓存编码器实例，避免重复初始化

#### Acceptance Criteria

- [ ] `estimate_tokens()` 返回精确 token 数（误差 < 5%）
- [ ] compaction 触发时机正确
- [ ] 无新增外部依赖导致的性能问题

---

### Phase 2: 结构化 HTML 生成工具

**Priority**: P0 (Theme 1)
**Complexity**: High
**Depends On**: Phase 1
**Blocks**: Phase 3

#### Step 2a: generate_html 工具

**新增文件**:

| File | Purpose |
|------|---------|
| `packages/agent/src/ic/tools/generate_html.py` | 新工具：返回结构化 JSON |

**工具定义**:

```python
class GenerateHtmlInput(BaseModel):
    slug: str          # 页面 slug
    title: str         # 页面标题
    description: str  # 页面描述
    data_model: Optional[dict] = None  # 数据模型
    design_system_css: Optional[str] = None  # 设计系统 CSS

class GenerateHtmlOutput(BaseModel):
    slug: str
    title: str
    html: str          # 生成的 HTML
    css: str           # 页面特定 CSS
    validation: dict   # 内置校验结果
```

**校验逻辑**:

- Viewport meta 存在
- max-width 430px 约束
- 触摸目标最小 44px
- 滚动条隐藏
- 字体大小合规

**修改文件**:

| File | Changes |
|------|---------|
| `packages/agent/src/ic/tools/__init__.py` | 注册新工具 |
| `packages/backend/app/engine/db_tools.py` | 后端版本工具 |

#### Step 2b: 替换 write_file 调用

- 在 `engine.py` 中，将所有 `write_file` 写 HTML 的调用替换为 `generate_html`
- 确保 LLM 收到结构化输出后可进行二次校验

#### Acceptance Criteria

- [ ] `generate_html` 返回 `{slug, title, html, css, validation}`
- [ ] 校验失败时阻止写入
- [ ] LLM 可看到完整的 HTML 结构

---

### Phase 3: 原子多文件操作

**Priority**: P0 (Theme 1)
**Complexity**: High
**Depends On**: Phase 2
**Blocks**: Nothing (独立功能)

#### Step 3a: BatchFileWrite 工具

**新增文件**:

| File | Purpose |
|------|---------|
| `packages/backend/app/engine/batch_tools.py` | 原子多文件操作 |

**工具定义**:

```python
class BatchFileWriteInput(BaseModel):
    operations: list[FileOperation]
    
class FileOperation(BaseModel):
    operation: Literal["write", "edit", "delete"]
    path: str
    content: Optional[str] = None
    old_content: Optional[str] = None  # for edit
    # ... other params

class BatchFileWriteOutput(BaseModel):
    success: bool
    results: list[OperationResult]
    error: Optional[str] = None
```

**事务机制**:

1. 收集所有操作
2. 验证所有操作可执行
3. 依次执行
4. 如果任何失败，rollback 已执行的操作
5. 返回结果

**修改文件**:

| File | Changes |
|------|---------|
| `packages/backend/app/engine/db_tools.py` | 新增 BatchFileWrite |
| `packages/agent/src/ic/tools/` | Agent 端版本 |

#### Acceptance Criteria

- [ ] 所有操作成功 → 全部提交
- [ ] 任何操作失败 → rollback 全部
- [ ] 并发 sub-agent 写入不导致不一致

---

### Phase 4: Provider Fallback 链

**Priority**: P0 (Theme 1)
**Complexity**: Medium
**Depends On**: Nothing
**Blocks**: Nothing (独立功能)

#### Step 4a: AgentConfig 扩展

**修改文件**:

| File | Changes |
|------|---------|
| `packages/agent/src/ic/config.py` | 新增 `model_fallback: list[str]` |

```python
class AgentConfig(BaseModel):
    # ... existing fields
    model_fallback: list[str] = []  # 备选模型列表
```

#### Step 4b: engine.py 实现 fallback

**修改文件**:

| File | Changes |
|------|---------|
| `packages/agent/src/ic/soul/engine.py` | `_step()` 中实现 fallback |

**fallback 逻辑**:

```python
async def _step(self, messages: list[dict]) -> StepResult:
    models = [self.config.model] + self.config.model_fallback
    
    for model in models:
        try:
            response = await self._call_llm(messages, model)
            return StepResult(success=True, response=response)
        except (TimeoutError, RateLimitError) as e:
            self.logger.warning(f"Model {model} failed: {e}")
            continue
    
    return StepResult(success=False, error="All models failed")
```

#### Acceptance Criteria

- [ ] 主模型超时自动切换备选
- [ ] 限流时自动切换备选
- [ ] 所有模型失败时返回明确错误

---

### Phase 5: 结构化 Compaction

**Priority**: P1 (Theme 1)
**Complexity**: High
**Depends On**: Phase 1
**Blocks**: Nothing (优化功能)

#### Step 5a: 结构化压缩算法

**修改文件**:

| File | Changes |
|------|---------|
| `packages/agent/src/ic/soul/context.py` | 替换 `compact_with_llm` |

**保留信息结构**:

```python
class ProjectState(BaseModel):
    """压缩后保留的项目状态"""
    product_doc_summary: str          # Product Doc 摘要
    file_change_history: list[FileChange]  # 文件变更历史
    design_decisions: list[str]       # 设计决策
    pending_requirements: list[str]    # 待处理需求
    page_summaries: dict[str, str]   # 页面摘要
```

**压缩提示词**:

```
请压缩对话历史，保留以下结构化信息：
1. Product Doc 当前状态（类型、页面、风格）
2. 文件变更历史（创建/修改了哪些文件）
3. 设计决策（颜色、布局、组件选择）
4. 待处理需求（用户要求但未完成的功能）
5. 页面摘要（每个页面的核心功能）
```

#### Acceptance Criteria

- [ ] compaction 后保留关键状态
- [ ] LLM 可基于压缩后的上下文继续工作
- [ ] 压缩使用 FAST-tier 模型

---

### Phase 6: AskUser 超时 + 优雅降级

**Priority**: P0 (Theme 2)
**Complexity**: Medium
**Depends On**: Nothing
**Blocks**: Phase 8

#### Step 6a: WebUserIO 超时机制

**修改文件**:

| File | Changes |
|------|---------|
| `packages/backend/app/engine/web_user_io.py` | 新增超时逻辑 |

```python
class WebUserIO:
    async def present_questions(
        self,
        questions: list[QuestionItem],
        timeout_seconds: int = 300,  # 默认 5 分钟
    ) -> list[Answer]:
        try:
            return await asyncio.wait_for(
                self._wait_for_answers(questions),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            # 优雅降级：用默认值继续
            defaults = self._generate_defaults(questions)
            await self._emit_timeout_event()
            return defaults
```

**默认值推导逻辑**:

- 从 Product Doc 推断
- 从项目类型默认值
- 从历史 session 偏好

#### Step 6b: 超时事件

**新增事件**:

| Event | Payload |
|-------|---------|
| `interview_timeout` | `{session_id, questions, defaults}` |

**前端行为**:

- 显示"等待超时，使用默认值继续..."
- 显示应用的默认值供用户确认

#### Acceptance Criteria

- [ ] 5 分钟无响应触发超时
- [ ] 超时后自动生成默认值
- [ ] 前端显示超时提示

---

### Phase 7: Interview 进度指示器

**Priority**: P1 (Theme 2)
**Complexity**: Low
**Depends On**: Phase 6
**Blocks**: Phase 8

#### Step 7a: ask_user metadata 扩展

**修改文件**:

| File | Changes |
|------|---------|
| `packages/agent/src/ic/tools/ask_user.py` | 新增 metadata |

```python
class AskUserInput(BaseModel):
    questions: list[QuestionItem]
    round_number: Optional[int] = None      # 当前轮次
    estimated_total_rounds: Optional[int] = None  # 预计总轮次
```

#### Step 7b: 前端进度指示器

**修改文件**:

| File | Changes |
|------|---------|
| `packages/web/src/components/custom/InterviewWidget.tsx` | 新增进度显示 |

**UI 示例**:

```
第 2 步 / 共 3 步: 视觉风格
━━━━━━━━━━━━━━━━━━━━━━●
```

#### Acceptance Criteria

- [ ] LLM 可设置 round_number
- [ ] 前端显示进度指示器
- [ ] 用户知道当前所处阶段

---

### Phase 8: 跨 Session 记忆

**Priority**: P0 (Theme 2)
**Complexity**: High
**Depends On**: Nothing
**Blocks**: Phase 9

#### Step 8a: 扩展 ProjectMemory

**修改文件**:

| File | Changes |
|------|---------|
| `packages/backend/app/db/models.py` | 新增偏好字段 |
| `packages/backend/app/services/project_memory.py` | 新增偏好服务 |

**存储结构**:

```python
class UserPreference(BaseModel):
    session_id: str
    color_scheme: Optional[str]      # "dark" | "light"
    font_family: Optional[str]
    layout_mode: Optional[str]       # "single" | "multi"
    favorite_components: list[str]
    created_at: datetime
```

#### Step 8b: 启动时注入

**修改文件**:

| File | Changes |
|------|---------|
| `packages/backend/app/engine/orchestrator.py` | 启动时加载偏好 |
| `packages/backend/app/engine/prompts.py` | 注入偏好到 system prompt |

**注入提示词**:

```
## 用户偏好（从历史 session 记忆）
- 偏好深色模式
- 常用字体: Inter
- 喜欢的组件: card, list, button
```

#### Acceptance Criteria

- [ ] 新 session 可看到历史偏好
- [ ] 偏好自动注入到 system prompt
- [ ] 偏好可被当前 session 覆盖

---

### Phase 9: 更丰富的上下文注入

**Priority**: P1 (Theme 2)
**Complexity**: Medium
**Depends On**: Phase 8
**Blocks**: Nothing

#### Step 9a: ContextInjector 扩展

**修改文件**:

| File | Changes |
|------|---------|
| `packages/agent/src/ic/soul/context_injector.py` | 新增注入项 |

**新增注入项**:

1. **设计 token 提取**
   - 从设计系统 CSS 提取颜色变量
   - 提取字体、间距值

2. **页面结构摘要**
   - 每个页面的 sections 列表
   - 组件使用情况

3. **资源清单**
   - 已上传图片列表及用途
   - 外部资源引用

#### Acceptance Criteria

- [ ] 设计 token 正确提取
- [ ] 页面结构摘要准确
- [ ] 资源清单完整

---

### Phase 10: Zustand 状态管理

**Priority**: P0 (Theme 3)
**Complexity**: High
**Depends On**: Nothing
**Blocks**: Phase 11

#### Step 10a: 安装 Zustand

```bash
cd packages/web
npm install zustand
```

#### Step 10b: 创建 Store Slices

**新增文件**:

| File | Purpose |
|------|---------|
| `packages/web/src/store/sessionStore.ts` | session 状态 |
| `packages/web/src/store/chatStore.ts` | chat 状态 |
| `packages/web/src/store/previewStore.ts` | preview 状态 |
| `packages/web/src/store/pagesStore.ts` | pages 状态 |
| `packages/web/src/store/productDocStore.ts` | productDoc 状态 |
| `packages/web/src/store/buildStore.ts` | build 状态 |
| `packages/web/src/store/versionStore.ts` | version 状态 |
| `packages/web/src/store/index.ts` | 统一导出 |

**Store 结构示例**:

```typescript
interface SessionStore {
  session: Session | null;
  loading: boolean;
  error: string | null;
  setSession: (session: Session) => void;
  updateSession: (updates: Partial<Session>) => void;
  // ...
}
```

#### Step 10c: 改造现有 Hooks

**修改文件**:

| File | Changes |
|------|---------|
| `packages/web/src/hooks/useSession.ts` | 改为 store selector |
| `packages/web/src/hooks/usePages.ts` | 改为 store selector |
| `packages/web/src/hooks/useChat.ts` | 改为 store selector |
| `packages/web/src/hooks/` | 其他 hooks 同理 |

**改造示例**:

```typescript
// 之前
export function useSession() {
  const [session, setSession] = useState(null);
  // ... 重复的状态逻辑
}

// 之后
export const useSession = () => useSessionStore((state) => state.session);
export const useSetSession = () => useSessionStore((state) => state.setSession);
```

#### Acceptance Criteria

- [ ] 所有 store slices 创建完成
- [ ] 现有 hooks 改为薄封装
- [ ] ProjectPage 可从 store 读取状态

---

### Phase 11: 拆分 ProjectPage

**Priority**: P0 (Theme 3)
**Complexity**: High
**Depends On**: Phase 10
**Blocks**: Phase 12

#### Step 11a: 创建 Container 组件

**修改文件**:

| File | Changes |
|------|---------|
| `packages/web/src/pages/ProjectPage.tsx` | 拆分组件 |

**拆分结构**:

```
ProjectPage (main)
├── ProjectLayout (< 100 行)
│   └── Navigation
├── ChatContainer
│   ├── ChatPanel
│   └── InterviewWidget
├── WorkbenchContainer
│   ├── PreviewPanel
│   ├── CodePanel
│   ├── ProductDocPanel
│   └── DataTab
└── VersionSidebar
```

**实现**:

```typescript
// ProjectPage.tsx (目标 < 100 行)
export default function ProjectPage() {
  const session = useSession();
  
  return (
    <ProjectLayout>
      <div className="flex-1 flex">
        <ChatContainer />
        <WorkbenchContainer />
      </div>
      <VersionSidebar />
    </ProjectLayout>
  );
}
```

#### Acceptance Criteria

- [ ] ProjectPage < 100 行
- [ ] 每个 container 独立工作
- [ ] 状态从 Zustand store 读取

---

### Phase 12: 一键部署

**Priority**: P0 (Theme 4)
**Complexity**: High
**Depends On**: Phase 11 (前端就绪)
**Blocks**: Phase 13

#### Step 12a: 部署服务

**新增文件**:

| File | Purpose |
|------|---------|
| `packages/backend/app/services/deploy.py` | 部署服务 |

**部署方法**:

1. **Netlify API**
   - 创建 site
   - 上传文件
   - 返回 URL

2. **Vercel CLI**
   - 调用 vercel deploy
   - 返回 URL

```python
class DeployService:
    async def deploy(
        self,
        session_id: str,
        provider: Literal["netlify", "vercel"] = "netlify",
    ) -> DeployResult:
        # 1. 收集文件
        files = await self._collect_files(session_id)
        
        # 2. 调用部署 API
        if provider == "netlify":
            result = await self._deploy_netlify(files)
        else:
            result = await self._deploy_vercel(files)
        
        # 3. 保存部署 URL
        await self._save_deploy_url(session_id, result.url)
        
        return result
```

#### Step 12b: 部署 API

**新增端点**:

| Path | Method | Purpose |
|------|--------|---------|
| `/api/deploy` | POST | 触发部署 |

**请求体**:

```json
{
  "session_id": "xxx",
  "provider": "netlify"  // or "vercel"
}
```

**响应**:

```json
{
  "deploy_url": "https://xxx.netlify.app",
  "status": "ready"
}
```

#### Step 12c: 前端 Deploy 按钮

**修改文件**:

| File | Changes |
|------|---------|
| `packages/web/src/components/custom/WorkbenchPanel.tsx` | 新增 Deploy 按钮 |

**UI**:

```
┌─────────────────────────────────┐
│  Workbench          [Deploy ▼] │
├─────────────────────────────────┤
│                                 │
└─────────────────────────────────┘
```

#### Acceptance Criteria

- [ ] 一键部署成功
- [ ] 返回可访问的 URL
- [ ] URL 存入 session

---

## 4. Execution Order & Dependency Graph

```
Wave 1 (并行):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Phase 1  (Token 计算)          → Phase 5 (结构化 Compaction)
  Phase 4  (Provider Fallback)
  Phase 6  (AskUser 超时)        → Phase 7 (Interview 进度)
  Phase 10 (Zustand 状态管理)
  Phase 8  (跨 Session 记忆)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Wave 2:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Phase 2  (结构化 HTML 工具)    ← 依赖 Phase 1
        ↓
  Phase 3  (原子多文件操作)      ← 依赖 Phase 2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Wave 3:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Phase 11 (拆分 ProjectPage)    ← 依赖 Phase 10
        ↓
  Phase 12 (一键部署)           ← 依赖 Phase 11
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Wave 4 (后续 Phase):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Phase 9  (上下文注入)
  Phase 13+ (QR 码、导出、Data Tab 等)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Wave Execution Plan

| Wave | Phases | Can Parallel? |
|------|--------|---------------|
| Wave 1 | 1, 4, 6, 8, 10 | Yes — all independent |
| Wave 2 | 2, 3 | After Phase 1 |
| Wave 3 | 11, 12 | After Phase 10 |
| Wave 4 | 5, 7, 9 | After earlier phases |
| Wave 5 | 13+ (QR, Export, Analytics) | After Wave 3 |

---

## 5. Files Summary

### New Files (约 25)

| File | Phase |
|------|-------|
| `packages/agent/src/ic/tools/generate_html.py` | 2 |
| `packages/backend/app/engine/batch_tools.py` | 3 |
| `packages/web/src/store/sessionStore.ts` | 10 |
| `packages/web/src/store/chatStore.ts` | 10 |
| `packages/web/src/store/previewStore.ts` | 10 |
| `packages/web/src/store/pagesStore.ts` | 10 |
| `packages/web/src/store/productDocStore.ts` | 10 |
| `packages/web/src/store/buildStore.ts` | 10 |
| `packages/web/src/store/versionStore.ts` | 10 |
| `packages/web/src/store/index.ts` | 10 |
| `packages/web/src/components/layout/ProjectLayout.tsx` | 11 |
| `packages/web/src/components/container/ChatContainer.tsx` | 11 |
| `packages/web/src/components/container/WorkbenchContainer.tsx` | 11 |
| `packages/web/src/components/container/VersionSidebar.tsx` | 11 |
| `packages/backend/app/services/deploy.py` | 12 |
| `packages/backend/app/api/deploy.py` | 12 |
| `packages/backend/app/services/analytics.py` | Theme 5 |
| `packages/backend/app/api/analytics.py` | Theme 5 |
| `packages/backend/app/services/project_memory.py` | Theme 2 |
| ... | |

### Modified Files (约 30)

| File | Phase | Changes |
|------|-------|---------|
| `packages/agent/src/ic/soul/context.py` | 1, 5 | token 计算、compaction |
| `packages/agent/src/ic/soul/engine.py` | 4 | fallback 逻辑 |
| `packages/agent/src/ic/config.py` | 4 | model_fallback |
| `packages/agent/src/ic/tools/__init__.py` | 2 | 注册 generate_html |
| `packages/backend/app/engine/db_tools.py` | 2, 3 | 批量工具 |
| `packages/backend/app/engine/web_user_io.py` | 6 | 超时机制 |
| `packages/backend/app/engine/orchestrator.py` | 8 | 偏好注入 |
| `packages/backend/app/engine/prompts.py` | 8 | 偏好提示词 |
| `packages/backend/app/db/models.py` | 8, Theme 5 | 偏好字段、analytics 表 |
| `packages/web/src/pages/ProjectPage.tsx` | 11 | 拆分 |
| `packages/web/src/hooks/useSession.ts` | 10 | store selector |
| `packages/web/src/hooks/usePages.ts` | 10 | store selector |
| `packages/web/src/hooks/useChat.ts` | 10 | store selector |
| `packages/web/src/components/custom/InterviewWidget.tsx` | 7 | 进度指示器 |
| `packages/web/src/components/custom/WorkbenchPanel.tsx` | 12 | Deploy 按钮 |
| ... | | |

### Dependencies Added

| Package | Purpose | Phase |
|---------|---------|-------|
| `tiktoken` | Token 计算 | 1 |
| `zustand` | 状态管理 | 10 |
| `recharts` | 图表 (Theme 5) | - |
| `qrcode` | QR 码生成 (Theme 4) | - |

---

## 6. Verification Plan

### 6.1 Theme 1: 生成可靠性

```bash
# 连续 10 次生成测试
cd packages/agent
python -c "
from ic.soul.context import TokenCounter
counter = TokenCounter()
# 验证 token 计算精确度
"
```

**验收标准**:

- [ ] 连续 10 次生成任务，成功率 > 90%
- [ ] compaction 后上下文不丢失关键信息
- [ ] Provider fallback 正确切换

### 6.2 Theme 2: 对话智能

**验收标准**:

- [ ] 创建新 session 时能看到上一个 session 的偏好注入
- [ ] interview 超时后自动继续（使用默认值）
- [ ] Interview 进度指示器显示正确

### 6.3 Theme 3: 前端架构

```bash
cd packages/web
npm run build
# 检查 bundle 大小
# 检查 ProjectPage 行数
```

**验收标准**:

- [ ] ProjectPage < 100 行
- [ ] dark mode 切换无闪烁
- [ ] 键盘快捷键可用

### 6.4 Theme 4: 部署

**验收标准**:

- [ ] 从 WorkbenchPanel 一键部署，获得可访问的 URL
- [ ] QR 码可扫描
- [ ] 导出 ZIP/Next.js/Astro 成功

### 6.5 Theme 5: Data Tab

**验收标准**:

- [ ] 部署页面产生访问数据后，Data Tab 显示趋势图
- [ ] 设备分布饼图正确
- [ ] CSV/JSON 导出成功

---

## 7. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| tiktoken 性能问题 | 生成变慢 | 缓存编码器实例 |
| Zustand 迁移破坏现有功能 | 前端崩溃 | 逐步迁移，保持向后兼容 |
| 部署 API 失败率高 | 部署不可用 | 备选 provider (Netlify ↔ Vercel) |
| Analytics 数据量过大 | 存储成本上升 | 聚合表定期清理 |
| 跨 session 记忆泄露隐私 | 用户投诉 | 偏好存储匿名化，仅存储偏好不存内容 |

---

## 8. Migration Strategy

### 8.1 渐进式迁移

1. **Phase 1-5 (Wave 1)**: Agent 端改进，无前端影响
2. **Phase 10-11 (Wave 2)**: Zustand 迁移，前端兼容模式
3. **Phase 12 (Wave 3)**: 部署功能，默认关闭，用户手动开启
4. **Theme 5 (Wave 4)**: Analytics，逐步推广

### 8.2 特性开关

| Feature | Env Variable | Default |
|---------|---------------|---------|
| 精确 token 计算 | `USE_TIKTOKEN` | `true` |
| Provider fallback | `USE_MODEL_FALLBACK` | `true` |
| 跨 session 记忆 | `USE_CROSS_SESSION_MEMORY` | `false` |
| Zustand 状态管理 | `USE_ZUSTAND` | `false` (过渡期) |
| 一键部署 | `USE_DEPLOY` | `false` |
| Analytics | `USE_ANALYTICS` | `false` |

### 8.3 数据兼容性

- **Sessions**: 新增字段向后兼容
- **Product Doc**: 无变化
- **Messages**: 对话搜索不改变现有结构
- **Pages**: 无变化

---

## 9. Parallel Development Guide

可以运行 **3 个 Claude Code 实例并行**:

1. **Agent 可靠性 Agent**: Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
2. **前端架构 Agent**: Phase 10 → Phase 11 → Phase 12 → Dark Mode → 快捷键
3. **对话智能 Agent**: Phase 6 → Phase 7 → Phase 8 → Phase 9 → 对话搜索

**关键路径**: Phase 1 → Phase 2 → Phase 3 → Phase 10 → Phase 11 → Phase 12

**独立工作**: Phase 4 (Provider Fallback), Phase 5 (Compaction), Phase 6 (超时)

---

## 10. Quick Start Commands

```bash
# Phase 1: Token 计算
# 修改: packages/agent/src/ic/soul/context.py

# Phase 10: Zustand
cd packages/web
npm install zustand

# Phase 12: 部署
# 新建: packages/backend/app/services/deploy.py
# 新建: packages/backend/app/api/deploy.py

# 运行测试
cd packages/agent
pytest tests/test_context.py -q

cd packages/web
npm run build
```

---

**Document Version**: v1.0
**Last Updated**: 2026-02-13
**Total New Files**: ~25
**Total Modified Files**: ~30
**Total Phases**: 12+ (含 Theme 4/5 后续 Phase)
