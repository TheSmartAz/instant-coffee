# Instant Coffee CLI - Vibe Coding 实施计划

**项目名称**: Instant Coffee (速溶咖啡)
**版本**: v1.0 - CLI First Approach
**核心理念**: 像和朋友聊天一样生成移动端页面
**日期**: 2025-01-30

---

## 目录

1. [项目概述](#1-项目概述)
2. [核心功能](#2-核心功能)
3. [技术架构](#3-技术架构)
4. [移动端适配要求](#4-移动端适配要求)
5. [Token 消耗记录](#5-token-消耗记录)
6. [项目结构](#6-项目结构)
7. [实施路线图](#7-实施路线图)
8. [Agent 系统设计](#8-agent-系统设计)

---

## 1. 项目概述

### 1.1 项目定位

**Instant Coffee** = 快速生成移动端页面的 AI 工具

核心理念：
- ✅ 对话式生成 (Vibe Coding)
- ✅ 移动端优先 (9:19.5 比例适配)
- ✅ 免费、无用户分级
- ✅ 透明的 Token 消耗记录

### 1.2 项目路径

```
Qoder-Project/instant-coffee/
├── packages/
│   ├── cli/
│   └── backend/
├── docs/
└── README.md
```

### 1.3 与 Zaoya 的关系

- **Zaoya**: 原来的产品概念（包含移动端 App、模板系统）
- **Instant Coffee**: 简化后的 CLI 工具，聚焦核心功能验证

---

## 2. 核心功能

### 2.1 CLI 命令

```bash
# 启动对话
$ instant-coffee chat

# 查看历史会话
$ instant-coffee history

# 查看统计信息
$ instant-coffee stats

# 导出代码
$ instant-coffee export <session-id> --output ./dist
```

### 2.2 使用流程

```bash
$ instant-coffee chat

☕ Instant Coffee - 快速生成移动端页面
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

你: 帮我做一个活动报名页面

AI: 好的！我想了解几个细节：

    1️⃣ 这个活动是什么类型的？
       📍 线下聚会
       📍 在线讲座
       📍 商业活动

    2️⃣ 需要收集哪些信息？
       ✅ 姓名、电话
       ✅ 邮箱地址
       ✅ 留言备注

    你可以告诉我，或者点选这些选项 😊

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 本次消耗: 128 tokens (输入: 86, 输出: 42)
📊 累计消耗: 3,456 tokens
```

### 2.3 输出物

生成的 HTML 文件特点：
- ✅ 移动端优先 (9:19.5 比例适配)
- ✅ 隐藏滚动条 (页面过长时)
- ✅ 单文件 (HTML + CSS + JS)
- ✅ 无外部依赖 (除 Google Fonts)

---

## 3. 技术架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────┐
│              CLI 工具 (TypeScript)                │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ 命令行界面   │  │ 浏览器启动   │  │ 统计显示 │ │
│  └─────────────┘  └─────────────┘  └──────────┘ │
└─────────────────────────────────────────────────┘
                      ↓ HTTP API
┌─────────────────────────────────────────────────┐
│            FastAPI 后端 (Python)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ Chat API    │  │ Agent 系统   │  │ 统计服务 │ │
│  └─────────────┘  └─────────────┘  └──────────┘ │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│              Agent 系统                          │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ Interview   │  │ Generation  │  │Refinement│ │
│  │ Agent       │  │ Agent       │  │ Agent    │ │
│  └─────────────┘  └─────────────┘  └──────────┘ │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│              Claude API                          │
└─────────────────────────────────────────────────┘
```

### 3.2 核心组件

**CLI (TypeScript)**:
```typescript
@instant-coffee/cli/
├── src/
│   ├── commands/
│   │   ├── chat.ts       # 主命令
│   │   ├── history.ts    # 历史命令
│   │   └── stats.ts      # 统计命令
│   ├── utils/
│   │   ├── logger.ts     # 彩色输出
│   │   └── browser.ts    # 浏览器打开
│   └── index.ts
└── package.json
```

**Backend (Python)**:
```python
backend/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── api/
│   │   └── chat.py          # Chat API
│   ├── agents/
│   │   ├── base.py          # Agent 基类
│   │   ├── interview.py     # Interview Agent
│   │   ├── generation.py    # Generation Agent
│   │   └── refinement.py    # Refinement Agent
│   ├── generators/
│   │   └── mobile_html.py   # 移动端 HTML 生成器
│   ├── services/
│   │   ├── token_tracker.py # Token 消耗记录
│   │   └── session.py       # 会话管理
│   └── db/
│       └── database.py      # SQLite 数据库
└── requirements.txt
```

---

## 4. 移动端适配要求

### 4.1 设计规范

**移动端视口比例**: 9:19.5 (现代手机标准)

```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
```

### 4.2 CSS 要求

**生成的 HTML 必须包含**:

```css
/* 移动端重置 */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html, body {
    height: 100%;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    -webkit-font-smoothing: antialiased;
}

/* 移动端容器 */
.container {
    max-width: 430px;        /* iPhone Pro Max 宽度 */
    margin: 0 auto;
    padding: 20px;
    min-height: 100vh;
}

/* 隐藏滚动条但保留滚动功能 */
.hide-scrollbar {
    -ms-overflow-style: none;      /* IE and Edge */
    scrollbar-width: none;          /* Firefox */
}

.hide-scrollbar::-webkit-scrollbar {
    display: none;                  /* Chrome, Safari, Opera */
}

/* 触摸优化 */
button, a, input, textarea {
    touch-action: manipulation;     /* 优化触摸响应 */
}
```

### 4.3 Generation Agent 输出规范

**生成的 HTML 模板**:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>{页面标题}</title>
    <style>
        /* 移动端适配样式 */
        {内联 CSS}
    </style>
</head>
<body>
    <div class="container">
        <!-- 页面内容 -->
    </div>

    <script>
        // 交互逻辑
    </script>
</body>
</html>
```

### 4.4 Agent 提示词

**System Prompt 必须包含**:

```python
MOBILE_FIRST_SYSTEM_PROMPT = """
你是 Instant Coffee 的 Generation Agent，负责生成移动端优先的 HTML 页面。

移动端设计要求：
1. 视口比例：9:19.5（现代手机标准）
2. 最大宽度：430px（iPhone Pro Max）
3. 隐藏滚动条：使用 .hide-scrollbar 类
4. 触摸优化：按钮最小高度 44px
5. 字体大小：正文 16px，标题 24-32px
6. 间距：使用 8px 网格系统

技术要求：
- 单文件 HTML（CSS 和 JS 内联）
- 无外部依赖（除 Google Fonts）
- 使用 CSS Grid/Flexbox 布局
- 图片使用响应式（max-width: 100%）

输出格式：
直接输出完整的 HTML 代码，不要任何解释。
"""
```

---

## 5. Token 消耗记录

### 5.1 记录内容

每次 API 调用记录：

```python
class TokenUsage(BaseModel):
    session_id: str
    timestamp: datetime
    agent_type: str           # "interview", "generation", "refinement"
    model: str                # "claude-sonnet-4-20250514"
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float           # USD 成本
```

### 5.2 统计展示

**CLI 实时显示**:

```bash
AI: 好的！我来帮你做一个活动报名页面...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 本次消耗: 256 tokens
   输入: 180 tokens
   输出: 76 tokens
   成本: $0.00064

📊 累计消耗: 1,245 tokens ($0.0031)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 5.3 统计命令

```bash
$ instant-coffee stats

📊 Token 使用统计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

今日消耗:
  Tokens: 3,456
  成本: $0.0086

本周消耗:
  Tokens: 12,345
  成本: $0.0309

总计消耗:
  Tokens: 45,678
  成本: $0.1142

会话统计:
  总会话数: 23
  生成页面: 18
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 5.4 成本计算

**Claude Sonnet 4 定价** (2025-01):
- Input: $3 / million tokens
- Output: $15 / million tokens

```python
def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """计算 USD 成本"""
    input_cost = (input_tokens / 1_000_000) * 3.0
    output_cost = (output_tokens / 1_000_000) * 15.0
    return input_cost + output_cost
```

### 5.5 数据库存储

**SQLite 表结构**:

```sql
CREATE TABLE token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    agent_type TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX idx_session_tokens ON token_usage(session_id);
CREATE INDEX idx_timestamp ON token_usage(timestamp);
```

---

## 6. 项目结构

### 6.1 完整目录结构

```
instant-coffee/
├── packages/
│   ├── cli/                      # CLI 工具 (TypeScript)
│   │   ├── src/
│   │   │   ├── commands/
│   │   │   │   ├── chat.ts       # 主命令
│   │   │   │   ├── history.ts    # 历史命令
│   │   │   │   └── stats.ts      # 统计命令
│   │   │   ├── utils/
│   │   │   │   ├── logger.ts     # 彩色输出
│   │   │   │   └── browser.ts    # 浏览器打开
│   │   │   └── index.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   │
│   └── backend/                  # 后端服务 (Python)
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py              # FastAPI 入口
│       │   ├── config.py            # 配置管理
│       │   │
│       │   ├── api/
│       │   │   ├── __init__.py
│       │   │   └── chat.py          # Chat API
│       │   │
│       │   ├── agents/
│       │   │   ├── __init__.py
│       │   │   ├── base.py          # Agent 基类
│       │   │   ├── interview.py     # Interview Agent
│       │   │   ├── generation.py    # Generation Agent
│       │   │   └── refinement.py    # Refinement Agent
│       │   │
│       │   ├── generators/
│       │   │   ├── __init__.py
│       │   │   └── mobile_html.py   # 移动端 HTML 生成器
│       │   │
│       │   ├── services/
│       │   │   ├── __init__.py
│       │   │   ├── token_tracker.py # Token 消耗记录
│       │   │   ├── session.py       # 会话管理
│       │   │   └── claude.py        # Claude API 封装
│       │   │
│       │   └── db/
│       │       ├── __init__.py
│       │       ├── database.py      # 数据库连接
│       │       └── models.py        # 数据模型
│       │
│       ├── requirements.txt
│       ├── pyproject.toml
│       └── .env.example
│
├── docs/
│   ├── implementation-plan.md     # 本文档
│   └── api-spec.md               # API 规范
│
├── .env.example
├── .gitignore
├── package.json                  # Monorepo 根配置
├── README.md
└── LICENSE
```

### 6.2 配置文件

**`.env.example`**:
```bash
# Claude API
ANTHROPIC_API_KEY=your_api_key_here

# Server
BACKEND_PORT=8000
BACKEND_HOST=http://localhost

# Output
OUTPUT_DIR=./instant-coffee-output

# Database
DATABASE_URL=sqlite:///./instant-coffee.db
```

---

## 7. 实施路线图

### Phase 1: 核心 CLI (1-2 周)

**目标**: 基本的对话式生成 + 移动端适配

**功能清单**:
- [x] 项目结构搭建
- [x] CLI 框架 (Commander.js)
- [x] 基础命令 (`instant-coffee chat`)
- [x] Interview Agent (简单提问)
- [x] Generation Agent (移动端 HTML)
- [x] Token 消耗记录
- [x] 浏览器自动打开

**验收标准**:
```bash
$ instant-coffee chat
你: 帮我做一个个人介绍页面

AI: 好的！我想了解几个细节...

(几轮对话后)

AI: ✅ 生成完成！
    💰 本次消耗: 234 tokens
    📂 预览: file:///.../index.html

(自动打开浏览器，显示移动端适配的页面)
```

### Phase 2: 反馈循环 (1-2 周)

**目标**: 支持用户反馈和迭代优化

**功能清单**:
- [x] Refinement Agent
- [x] 用户反馈处理
- [x] 增量更新
- [x] 历史会话保存
- [x] `history` 和 `stats` 命令

### Phase 3: 优化体验 (1 周)

**功能清单**:
- [x] 更好的 Interview Agent (多轮提问)
- [x] 更丰富的移动端组件
- [x] 错误处理和重试
- [x] 进度提示
- [x] 更美观的 CLI 输出

---

## 8. Agent 系统设计

### 8.1 Interview Agent

**职责**: 通过对话了解用户需求

**触发条件**:
- 用户首次输入
- 信息不足以生成页面

**输出格式**:
```python
class InterviewResponse(BaseModel):
    message: str           # 展示给用户的问题
    is_complete: bool      # 是否可以进入生成阶段
    context: dict          # 收集到的信息
```

**示例对话**:
```
AI: 好的！我想了解几个细节：

    1️⃣ 这个页面是什么类型的？
       📄 个人介绍
       📄 活动报名
       📄 产品介绍

    2️⃣ 需要包含哪些内容？

    你可以告诉我，或者点选这些选项 😊
```

### 8.2 Generation Agent

**职责**: 生成移动端适配的 HTML

**输入**: Interview Agent 收集的信息

**输出**:
```python
class GenerationResult(BaseModel):
    html: str              # 完整的 HTML
    preview_url: str       # 预览 URL
    filepath: str          # 文件路径
    token_usage: TokenUsage
```

**移动端生成要点**:
1. **容器最大宽度**: 430px
2. **viewport 设置**: 9:19.5 比例
3. **隐藏滚动条**: `.hide-scrollbar` 类
4. **触摸优化**: 按钮最小 44px
5. **响应式图片**: `max-width: 100%`

### 8.3 Refinement Agent

**职责**: 根据用户反馈优化页面

**示例**:
```
用户: 把标题颜色改成红色

AI: 好的，修改中...
    ✅ 修改完成！刷新浏览器查看
    💰 本次消耗: 89 tokens
```

---

## 9. Token Tracker 服务

### 9.1 服务实现

```python
# backend/app/services/token_tracker.py

from datetime import datetime
from typing import List
from db.models import TokenUsage
from db.database import get_db

class TokenTracker:
    def __init__(self):
        self.db = get_db()

    def record_usage(
        self,
        session_id: str,
        agent_type: str,
        input_tokens: int,
        output_tokens: int
    ) -> TokenUsage:
        """记录 Token 消耗"""

        total_tokens = input_tokens + output_tokens
        cost = self._calculate_cost(input_tokens, output_tokens)

        usage = TokenUsage(
            session_id=session_id,
            timestamp=datetime.now(),
            agent_type=agent_type,
            model="claude-sonnet-4-20250514",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost
        )

        self.db.add(usage)
        self.db.commit()

        return usage

    def get_session_stats(self, session_id: str) -> dict:
        """获取会话统计"""
        usages = self.db.query(TokenUsage).filter(
            TokenUsage.session_id == session_id
        ).all()

        total_tokens = sum(u.total_tokens for u in usages)
        total_cost = sum(u.cost_usd for u in usages)

        return {
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "api_calls": len(usages)
        }

    def get_today_stats(self) -> dict:
        """获取今日统计"""
        today = datetime.now().date()
        usages = self.db.query(TokenUsage).filter(
            TokenUsage.timestamp >= today
        ).all()

        return {
            "tokens": sum(u.total_tokens for u in usages),
            "cost": sum(u.cost_usd for u in usages),
            "calls": len(usages)
        }

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """计算成本 (USD)"""
        input_cost = (input_tokens / 1_000_000) * 3.0
        output_cost = (output_tokens / 1_000_000) * 15.0
        return input_cost + output_cost
```

### 9.2 CLI 展示

```typescript
// cli/src/utils/stats.ts

export function formatTokenStats(stats: TokenStats): string {
    const lines = [
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '💰 本次消耗:',
        `   Tokens: ${stats.total_tokens}`,
        `   输入: ${stats.input_tokens}`,
        `   输出: ${stats.output_tokens}`,
        `   成本: $${stats.cost.toFixed(5)}`,
        '',
        '📊 累计消耗:',
        `   Tokens: ${stats.cumulative_tokens}`,
        `   成本: $${stats.cumulative_cost.toFixed(4)}`,
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
    ];

    return lines.join('\n');
}
```

---

## 10. 下一步行动

### 10.1 立即开始 (本周)

1. **搭建项目结构**
   ```bash
   cd instant-coffee
   mkdir -p packages/{cli,backend}
   ```

2. **初始化 CLI (TypeScript)**
   ```bash
   cd packages/cli
   npm init -y
   npm install commander chalk ora axios open
   ```

3. **初始化 Backend (Python)**
   ```bash
   cd packages/backend
   python -m venv venv
   source venv/bin/activate
   pip install fastapi uvicorn anthropic python-dotenv
   ```

4. **实现基础 Agent**
   - Interview Agent
   - Generation Agent (移动端 HTML)
   - Token Tracker

### 10.2 第一个迭代目标

**2 周内实现可工作的 CLI**:

```bash
$ npm install -g @instant-coffee/cli
$ instant-coffee chat

☕ Instant Coffee - 快速生成移动端页面

你: 帮我做一个活动报名页面

AI: 好的！我想了解几个细节...

(生成完成)

✅ 生成完成！
💰 本次消耗: 234 tokens
📂 预览: file:///.../index.html

(自动打开浏览器，显示移动端适配的页面)
```

---

## 11. 成功指标

### 11.1 技术指标

| 指标 | 目标 |
|------|------|
| 生成时间 | < 30 秒 |
| Interview 轮次 | 2-5 轮 |
| 移动端适配 | 100% (所有生成页面) |
| Token 效率 | < 500 tokens/页面 |

### 11.2 验收标准

- ✅ 生成的页面在手机上显示正常
- ✅ 滚动条正确隐藏
- ✅ Token 消耗正确记录
- ✅ 统计命令准确显示

---

**文档版本**: v1.0
**最后更新**: 2025-01-30
**项目**: Instant Coffee

---

## 总结

**Instant Coffee** 是一款专注于快速生成移动端页面的 CLI 工具：

**核心特性**:
1. ✅ 对话式生成 (Vibe Coding)
2. ✅ 移动端优先 (9:19.5 比例)
3. ✅ 隐藏滚动条 (美观体验)
4. ✅ 免费使用
5. ✅ 透明 Token 记录

**下一步**: 开始搭建项目结构
