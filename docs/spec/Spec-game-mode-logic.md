# Instant Coffee - Game Mode Logic 技术规格说明书 (Spec v0.4)

**项目名称**: Instant Coffee (速溶咖啡)
**版本**: v0.4 - Game Mode Logic
**日期**: 2026-02-01
**文档类型**: Technical Specification Document (TSD)

---

## 文档变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v0.4 | 2026-02-01 | 新增 Game Mode 逻辑与运行时规范 | Planning |

---

## 设计决策访谈记录 (2026-02-01)

本节记录 spec-game-mode-logic 的关键决策与边界。

### 核心决策

| 问题 | 决策 | 说明 |
|------|------|------|
| 是否默认开启 Game Mode | 否，需用户明确表达游戏需求 | 保持原有页面生成体验稳定 |
| 游戏输出形式 | 分级输出（单文件/多文件） | 简单游戏单文件，复杂游戏多文件 |
| 引擎策略 | 2D: 原生 Canvas 优先；复杂需求允许 CDN 引擎 | 推币机/FPS 需要物理与 3D 引擎 |
| 资产策略 | 轻量内联 + 可选 assets/ 输出 | 兼顾可移植与可扩展 |
| 游戏复杂度上限 | v0.4 支持 2D 与简化 3D Demo | 真正 FPS/Minecraft 仅 Demo 级别 |

### 详细问答

**Q: 是否需要改变现有 Generation Prompt 规则？**
> A: 新增 Game Mode 分支 prompt，不影响默认页面模式。

**Q: 推币机/物理类游戏必须依赖引擎吗？**
> A: 复杂物理优先 Matter.js/Planck.js；无引擎时只能做简化 Demo。

**Q: Game Mode 输出结构如何控制？**
> A: 引入 GameSpec，作为生成统一输入，控制模板与输出模式。

---

## 目录

1. [版本概述](#1-版本概述)
2. [核心目标](#2-核心目标)
3. [功能范围](#3-功能范围)
4. [Game Mode 逻辑流程](#4-game-mode-逻辑流程)
5. [运行时架构](#5-运行时架构)
6. [模板与组件库](#6-模板与组件库)
7. [输出与打包策略](#7-输出与打包策略)
8. [工具与扩展](#8-工具与扩展)
9. [安全与性能边界](#9-安全与性能边界)
10. [数据结构](#10-数据结构)
11. [文件变更清单](#11-文件变更清单)
12. [验收标准](#12-验收标准)

---

## 1. 版本概述

### 1.1 版本定位

**Spec v0.4** 在 v0.3 基础上新增 **Game Mode 逻辑与运行时规范**，让 Instant Coffee 能够稳定产出“小游戏级别”的前端作品，并具备扩展到简化 3D Demo 的能力。

**核心升级**:
- 🎮 Game Mode 路由与游戏类型识别
- 🧩 统一 GameSpec 数据结构
- 🧠 游戏模板 + 组件化模块
- 📦 分级输出（单文件 / 多文件 / 资产包）
- 🧪 游戏逻辑验证与基础性能约束

### 1.2 与 v0.3 的关系

| v0.3 (已完成) | v0.4 (本版本) |
|--------------|--------------|
| 页面生成逻辑 | 页面 + 游戏双模式 |
| HTML 规则固定 | Game Mode 允许 Canvas/WebGL |
| 单文件输出为主 | 复杂游戏允许多文件 |
| 无模板库 | 新增游戏模板库 |

---

## 2. 核心目标

1. **不破坏原有页面生成体验**：Game Mode 必须是显式触发。
2. **可复用的游戏逻辑模块**：输入、物理、渲染、状态机等统一模块化。
3. **复杂度分级**：明确支持范围，避免“幻觉式完整游戏”。
4. **可维护输出结构**：复杂游戏默认多文件输出。
5. **一致的生成规范**：统一 GameSpec 驱动生成。

---

## 3. 功能范围

### 3.1 目标支持的游戏类型 (v0.4)

- 2D 网格类：扫雷、贪吃蛇
- 2D 反射类：反弹球、打砖块
- 2D 平台跳 Demo
- 物理类 Demo：推币机（简化物理，默认引擎）
- 3D Demo：简化 FPS / Minecraft 风格（仅 Demo 级）

### 3.2 明确不做

- 大型 3D 世界（真实 FPS / Minecraft 完整实现）
- 网络联机、多人同步
- 重资产美术制作
- 复杂商业化系统

---

## 4. Game Mode 逻辑流程

### 4.1 触发条件

- 用户显式表达“游戏/小游戏/玩法/关卡”等需求
- 或在访谈中明确游戏类型 (扫雷/推币机/反弹球/俄罗斯方块)

### 4.2 逻辑流程

```
用户输入
    ↓
Interview Agent (识别游戏意图)
    ↓
Game Mode Router
    ↓
构建 GameSpec (类型/规则/复杂度/输出模式)
    ↓
选择模板 (或混合模板 + 组件库)
    ↓
Generation Agent (Game Mode Prompt)
    ↓
输出文件 (single/multi + assets)
```

### 4.3 复杂度分级规则

| 等级 | 触发条件 | 输出模式 | 示例 |
|------|----------|----------|------|
| L1 | 规则简单、无物理 | 单文件 | 扫雷、贪吃蛇 |
| L2 | 有基础碰撞 | 单文件/多文件 | 反弹球、打砖块 |
| L3 | 复杂物理或 3D | 多文件 + 资产 | 推币机、FPS Demo |

---

## 5. 运行时架构

### 5.1 核心模块

- **GameLoop**: 固定时间步更新 + 渲染
- **InputManager**: 键盘/触摸/摇杆抽象
- **Physics**: AABB/圆形碰撞 + 可选引擎
- **Renderer**: Canvas2D / WebGL
- **StateMachine**: Menu/Play/Pause/Win/Lose
- **AudioManager**: 简易音效加载与播放
- **AssetManager**: 图片/音频/地图数据缓存

### 5.2 推荐依赖策略

- 2D 轻量：原生 Canvas2D
- 2D 物理：Matter.js / Planck.js (可选)
- 3D Demo：Three.js (可选)

---

## 6. 模板与组件库

### 6.1 模板列表 (v0.4)

| 模板 | 说明 | 复杂度 |
|------|------|--------|
| minesweeper | 扫雷 | L1 |
| snake | 贪吃蛇 | L1 |
| bounce | 反弹球 | L2 |
| brick-breaker | 打砖块 | L2 |
| platformer-demo | 平台跳 Demo | L2 |
| coin-pusher-demo | 推币机 Demo | L3 |
| fps-demo | FPS Demo | L3 |
| voxel-demo | Minecraft 风格 Demo | L3 |

### 6.2 组件库 (可复用)

- InputManager
- Physics2D
- CollisionResolver
- SpriteRenderer
- UIOverlay (HUD/score)
- MapLoader (网格/实体)

---

## 7. 输出与打包策略

### 7.1 输出模式

- **single-file**: `index.html` 内联 CSS/JS
- **multi-file**: `index.html` + `game.js` + `styles.css`
- **assets**: `assets/` 目录输出图片/音效

### 7.2 输出规则

- L1 默认 single-file
- L2 默认 single-file，可升级 multi-file
- L3 必须 multi-file + assets

---

## 8. 工具与扩展

### 8.1 新增 Tool (建议)

- `asset_pack`: 统一管理资源打包/内联策略
- `validate_game`: 静态检查游戏输出 (循环/事件/帧率)
- `generate_map`: 按模板生成初始关卡

### 8.2 现有 Tool 扩展

- `filesystem_write`: 支持写入多文件结构
- `validate_html`: 支持检测 Canvas/WebGL 结构

---

## 9. 安全与性能边界

- **FPS 目标**: 30+ (移动端)
- **渲染预算**: 每帧 16ms 内完成
- **资源上限**: 5MB 以内 (v0.4 默认)
- **外部依赖**: 仅允许白名单 CDN
- **禁止**: 远程脚本动态执行、无限循环

---

## 10. 数据结构

### 10.1 GameSpec (核心结构)

```json
{
  "mode": "game",
  "title": "扫雷",
  "game_type": "minesweeper",
  "complexity": "L1",
  "engine": "native_canvas",
  "controls": ["tap", "long_press"],
  "rules": {
    "grid": [9, 9],
    "mines": 10
  },
  "output": {
    "format": "single-file",
    "assets": false
  },
  "style": {
    "theme": "retro",
    "palette": ["#1a1a1a", "#f5f5f7"]
  }
}
```

### 10.2 GameSpec 生成来源

- Interview Agent 收集关键信息
- Game Mode Router 补全默认值
- 用户最后消息可直接覆盖字段

---

## 11. 文件变更清单

### 11.1 新建文件

| 文件路径 | 描述 |
|---------|------|
| `packages/backend/app/agents/game_mode.py` | Game Mode 路由与 GameSpec 构建 |
| `packages/backend/app/agents/prompts_game.py` | Game Mode 专用 Prompt |
| `packages/backend/app/game/templates/` | 游戏模板目录 |
| `packages/backend/app/game/runtime/` | 游戏运行时模块 |
| `docs/spec/Spec-game-mode-logic.md` | 本文档 |

### 11.2 修改文件

| 文件路径 | 变更内容 |
|---------|---------|
| `packages/backend/app/agents/orchestrator.py` | 支持 Game Mode 分支 |
| `packages/backend/app/agents/prompts.py` | 新增入口逻辑 |
| `packages/backend/app/agents/generation.py` | 支持多文件输出 |
| `packages/backend/app/services/filesystem.py` | 支持 assets/ 写入 |

---

## 12. 验收标准

### 12.1 功能验收

- [ ] 能正确识别游戏意图并进入 Game Mode
- [ ] GameSpec 构建完整且可覆盖
- [ ] L1/L2 游戏可生成并运行
- [ ] L3 Demo 可生成并运行
- [ ] 多文件与 assets 输出正常

### 12.2 质量验收

- [ ] 生成结果可复用/可维护
- [ ] 模板与组件库可独立测试
- [ ] Game Mode 不影响页面模式
- [ ] 输出文件符合安全限制

### 12.3 性能验收

- [ ] L1/L2 游戏在移动端达到 30 FPS+
- [ ] L3 Demo 在桌面达到 30 FPS+

---

**文档版本**: v0.4
**最后更新**: 2026-02-01
**状态**: 待实现

