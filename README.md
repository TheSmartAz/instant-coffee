# Instant Coffee ☕

> 像速溶咖啡一样快速生成移动端页面的 AI CLI 工具

## 项目简介

**Instant Coffee** 是一个通过命令行对话生成移动端优化页面的 AI 工具。零技术门槛，通过自然语言对话，快速生成高质量的移动端 HTML 页面。

### 核心特性

- ☕ **快速生成** - 像速溶咖啡一样，几分钟内生成页面
- 💬 **对话式创造** - 自然语言交互，无需技术背景
- 📱 **移动端优先** - 完美适配 9:19.5 比例现代手机
- 🎯 **双模式支持** - 快速模式 + 深度定制模式
- 📝 **版本管理** - 自动保存历史，支持回滚
- 💰 **成本透明** - Token 消耗统计，完全透明

## 技术栈

- **CLI**: TypeScript + Node.js + Commander.js
- **Backend**: Python + FastAPI + Claude AI
- **Database**: SQLite + SQLAlchemy
- **AI**: Claude Sonnet 4 (Anthropic)

## 快速开始

### 环境要求

- Node.js 18.0+
- Python 3.11+
- Anthropic API Key

### 安装

```bash
# 1. 克隆项目
git clone https://github.com/[your-org]/instant-coffee.git
cd instant-coffee

# 2. 安装后端依赖
cd packages/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，添加你的 ANTHROPIC_API_KEY

# 4. 初始化数据库
python -m app.db.migrations

# 5. 启动后端服务
uvicorn app.main:app --reload

# 6. 安装 CLI (新终端)
cd packages/cli
npm install
npm run dev

# 7. 使用 CLI
npx instant-coffee chat
```

## 使用示例

```bash
$ instant-coffee chat

☕ Instant Coffee - 快速生成移动端页面
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

你: 帮我做一个活动报名页面

AI: 好的！我想了解几个细节：
    1️⃣ 活动类型是什么？
    2️⃣ 需要收集哪些信息？
    3️⃣ 活动有截止日期吗？

你: 线下聚会，需要姓名电话和备注，下周六截止

AI: 明白了！开始生成...
    ━━━━━━━━━━━━━━━━ 100%
    ✅ 生成完成！

    📂 预览: file:///Users/.../instant-coffee-output/index.html

(自动打开浏览器预览)
```

## 主要命令

```bash
# 启动对话生成页面
instant-coffee chat

# 查看会话历史
instant-coffee history

# 继续之前的会话
instant-coffee chat --continue <session-id>

# 回滚到指定版本
instant-coffee rollback <session-id> <version>

# 导出代码
instant-coffee export <session-id> --output ./my-page

# 查看 Token 消耗统计
instant-coffee stats
```

## 项目结构

```
instant-coffee/
├── packages/
│   ├── cli/              # TypeScript CLI 工具
│   └── backend/          # Python FastAPI 后端
├── docs/
│   ├── spec/             # 产品规格说明
│   └── phases/           # 开发阶段文档
├── CLAUDE.md             # Claude 项目指南
└── README.md             # 本文件
```

## 开发指南

### 开发阶段

项目分为 9 个开发阶段，详见 `docs/phases/INDEX.md`

### 并行开发

支持 3 个开发者并行工作：
- **Agent 1**: Database + Backend Core (关键路径)
- **Agent 2**: Frontend CLI (用户界面)
- **Agent 3**: Backend Services (辅助功能)

详细开发路线请查看 `docs/phases/INDEX.md`

### 贡献

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 文档

- 📋 [产品规格说明](docs/spec/spec-01.md)
- 🗺️ [开发路线图](docs/phases/INDEX.md)
- 🤖 [Claude 项目指南](CLAUDE.md)
- 🔧 [API 文档](http://localhost:8000/docs) (后端运行后访问)

## 路线图

### v0.1 (当前)
- [x] 产品规格定义
- [x] 开发阶段拆分
- [ ] 数据库设计
- [ ] Agent 系统实现
- [ ] CLI 框架搭建

### v0.2 (未来)
- [ ] 模板系统
- [ ] 分享链接
- [ ] 语音输入
- [ ] 多页面生成

## 许可证

[MIT License](LICENSE)

## 联系方式

- Issues: https://github.com/[your-org]/instant-coffee/issues
- Email: [your-email]

---

**当前版本**: v0.1-alpha
**状态**: 开发中
**最后更新**: 2025-01-30
