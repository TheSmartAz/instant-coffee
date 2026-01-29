# Instant Coffee - Claude 项目指南

## 项目概述

**Instant Coffee (速溶咖啡)** 是一个通过命令行对话生成移动端优化页面的 AI 工具。

- **核心理念**: 像速溶咖啡一样快速便捷地生成移动端页面
- **技术栈**: TypeScript (CLI) + Python/FastAPI (Backend) + Claude AI
- **目标**: 零技术门槛，通过自然对话生成高质量移动端页面

## 项目结构

```
instant-coffee/
├── packages/
│   ├── cli/              # TypeScript CLI 工具
│   │   └── src/
│   │       ├── commands/  # 命令实现
│   │       └── utils/     # 工具函数
│   │
│   └── backend/          # Python FastAPI 后端
│       └── app/
│           ├── agents/    # AI Agent 系统
│           ├── api/       # API 端点
│           ├── db/        # 数据库层
│           └── services/  # 业务逻辑
│
├── docs/
│   ├── spec/             # 产品规格说明
│   └── phases/           # 开发阶段文档
│       ├── database/
│       ├── backend/
│       ├── frontend/
│       └── INDEX.md      # 开发路线总览
│
├── .env.example          # 环境变量示例
└── README.md
```

## 核心功能 (P0)

### 1. 对话式生成
- Interview Agent: 自适应提问 (3-5轮)
- Generation Agent: 渐进式生成移动端 HTML
- Refinement Agent: 根据反馈修改页面

### 2. 会话管理
- 自动保存所有会话
- 版本控制和回滚
- 历史会话查看和继续

### 3. 移动端优先
- 9:19.5 视口比例
- 最大宽度 430px (iPhone Pro Max)
- 隐藏滚动条，触摸优化

### 4. 成本透明
- Token 消耗记录
- 统计命令查看消耗
- 不在对话中打断用户

## 技术要点

### CLI (TypeScript)
- **框架**: Commander.js
- **样式输出**: Chalk, Ora
- **HTTP 客户端**: Axios
- **浏览器启动**: Open

### Backend (Python)
- **框架**: FastAPI
- **AI**: Claude Sonnet 4 (Anthropic API)
- **数据库**: SQLite + SQLAlchemy
- **数据验证**: Pydantic

### 数据库表
- `sessions`: 会话信息
- `messages`: 对话消息
- `versions`: 页面版本
- `token_usage`: Token 消耗记录

## 开发阶段

项目分为 **9 个开发阶段**，详见 `docs/phases/INDEX.md`

### 关键路径 (必须按顺序)
```
D1 (数据库) → B1 (Chat API) → B2 (会话管理) → B4 (导出) → F3 (历史命令)
```

### 可并行开发
- Wave 1: D1 + F1 (立即开始)
- Wave 2: B1 + B3 (D1 完成后)
- Wave 3: B2 + F2 (B1 完成后)
- Wave 5: F3 + F4 (B2, B4 完成后)

## 开发指南

### 首次设置

1. **后端设置**:
```bash
cd packages/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 添加 ANTHROPIC_API_KEY
```

2. **CLI 设置**:
```bash
cd packages/cli
npm install
npm run dev
```

3. **数据库初始化**:
```bash
cd packages/backend
python -m app.db.migrations
```

### 开发流程

1. **查看当前阶段**: 阅读 `docs/phases/INDEX.md`
2. **选择阶段**: 根据依赖关系选择可开始的阶段
3. **阅读阶段文档**: `docs/phases/{category}/phase-{id}-{name}.md`
4. **实现功能**: 按照文档中的任务清单开发
5. **编写测试**: 每个阶段都包含测试要求
6. **验收标准**: 确保所有 Acceptance Criteria 通过

### 代码规范

**Python (Backend)**:
- 使用 Black 格式化
- 类型提示 (Type Hints)
- Docstrings (Google 风格)
- 异步优先 (async/await)

**TypeScript (CLI)**:
- 使用 Prettier 格式化
- 严格类型检查
- 函数式编程风格
- 错误处理完善

## Agent 系统

### Interview Agent
- **职责**: 理解用户需求，自适应提问
- **输入**: 用户消息 + 对话历史
- **输出**: 问题 OR 生成信号
- **提问策略**: 根据信息充分度决定 0-5 轮提问

### Generation Agent
- **职责**: 生成移动端优化的 HTML
- **输入**: Interview Agent 收集的需求
- **输出**: 单文件 HTML (内联 CSS/JS)
- **生成方式**: 渐进式 (5 个阶段: 20%, 40%, 60%, 80%, 100%)

### Refinement Agent
- **职责**: 根据用户反馈修改页面
- **输入**: 用户修改意图 + 当前 HTML
- **输出**: 修改后的 HTML
- **原则**: 只修改用户指定的部分，保持移动端标准

## 重要约束

### 移动端规范 (必须遵守)
- 视口: 9:19.5 比例
- 容器: max-width 430px
- 按钮: 最小高度 44px
- 字体: 正文 16px, 标题 24-32px
- 滚动条: 必须隐藏 (使用 .hide-scrollbar)
- 单文件: HTML + CSS + JS 内联

### API 限制
- Claude API 有 token 限制
- 实现重试机制 (3 次，指数退避)
- 管理对话历史长度
- 记录所有 token 消耗

### 数据安全
- 所有数据本地存储 (~/.instant-coffee/)
- 不依赖云端服务
- 用户完全掌控数据
- Session ID 使用 UUID4

## 测试策略

### 单元测试
- 每个 Agent 类
- 每个 Service 类
- 数据库模型

### 集成测试
- Agent 之间的协作
- API 端点
- CLI 命令

### E2E 测试
- 完整对话流程 (interview → generation → refinement)
- 会话保存和继续
- 版本回滚
- 导出功能

## 常见问题

### Q: 如何调试 Agent 行为？
A: 在 BaseAgent 中启用详细日志，查看发送给 Claude 的完整 prompt。

### Q: 生成的 HTML 不符合移动端规范？
A: 检查 Generation Agent 的 system prompt，确保包含所有移动端要求。

### Q: Token 消耗过高？
A: 优化 prompt，减少对话历史长度，使用更高效的提问策略。

### Q: 如何添加新的 CLI 命令？
A: 在 `packages/cli/src/commands/` 创建新文件，然后在 `commands/index.ts` 注册。

## 环境变量

```bash
# Backend (.env)
ANTHROPIC_API_KEY=sk-ant-xxx     # Claude API 密钥 (必需)
DATABASE_URL=sqlite:///~/.instant-coffee/instant-coffee.db
BACKEND_PORT=8000
OUTPUT_DIR=~/instant-coffee-output

# CLI (.env)
BACKEND_URL=http://localhost:8000
```

## 参考文档

- **产品规格**: `docs/spec/spec-01.md`
- **开发路线**: `docs/phases/INDEX.md`
- **API 文档**: 后端运行后访问 http://localhost:8000/docs
- **Claude API**: https://docs.anthropic.com/

## 贡献指南

1. 阅读相关阶段文档
2. 创建功能分支
3. 实现功能 + 测试
4. 确保所有测试通过
5. 提交 PR 并描述变更

## 支持

- **Issues**: https://github.com/[your-org]/instant-coffee/issues
- **文档**: `docs/` 目录
- **阶段文档**: `docs/phases/`

---

**项目版本**: v0.1
**最后更新**: 2025-01-30
**当前状态**: 初始化阶段

开始开发请查看: `docs/phases/INDEX.md`
