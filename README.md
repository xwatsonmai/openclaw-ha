# openclaw-ha

`openclaw-ha` is an integration layer that brings Home Assistant awareness and control-adjacent capabilities into OpenClaw agents.

它的目标不是替代 Home Assistant，也不是单独做一个新的设备控制平台，而是作为一层集成能力，把 Home Assistant 的状态感知、事件变化、摘要缓存能力接入 OpenClaw，让智能助手具备更强的家庭理解能力。

## 它解决的问题

传统做法往往是：
- 用户一问
- Agent 临时查 HA
- 再现场组织回答

这会带来：
- 延迟高
- 结果不稳定
- 事件噪音大
- 用户自己在 HA App 里操作后，Agent 感知滞后

`openclaw-ha` 的思路是：

> 先把 Home Assistant 状态接入 OpenClaw Agent 的感知链路，再通过事件驱动、状态摘要、缓存读取，提升助手的响应速度与家庭上下文理解能力。

## 当前能力

- Home Assistant 全量状态快照
- 结构化摘要 `summary.json`
- 简版回答摘要 `answer_brief.json`
- 文本回答卡 `answer_card.md`
- 主设备清单（focus entities）
- 设备别名映射（aliases）
- 事件监听（WebSocket）
- 定时轮询兜底
- 事件降噪规则
- focus-first 触发策略
- per-entity debounce + batching
- bootstrap / healthcheck 脚本
- systemd user service 模板

## 能力定位

`openclaw-ha` 当前更像：
- OpenClaw 的 Home Assistant 感知接入层
- 面向智能助手的家庭状态上下文层
- 回答前置缓存与事件驱动更新层

而不是：
- 单纯的状态同步器
- 单纯的缓存工具
- 单纯的设备控制脚本集

## 依赖

- Python 3
- Node.js 18+（用于 WebSocket 监听）
- Home Assistant（需要 long-lived access token）

## 目录结构

```text
openclaw-ha/
├── README.md
├── docs/
├── src/
├── scripts/
├── config/
├── systemd/
├── data/        # runtime output, ignored by git
├── logs/        # runtime logs, ignored by git
└── .gitignore
```

## 初始化

### 1. 复制配置模板

推荐直接运行：

```bash
cd openclaw-ha
./scripts/bootstrap.sh
```

如果你想手动复制，也可以：

```bash
cd openclaw-ha
cp config/cache_rules.example.json config/cache_rules.json
cp config/focus_entities.example.json config/focus_entities.json
cp config/entity_aliases.example.json config/entity_aliases.json
cp config/ws_noise_rules.example.json config/ws_noise_rules.json
cp config/ha.example.json config/ha.json
```

### 2. 填写 HA 配置

编辑 `config/ha.json`：

```json
{
  "url": "http://homeassistant.local:8123",
  "token": "YOUR_LONG_LIVED_ACCESS_TOKEN"
}
```

你也可以不用 `config/ha.json`，改用环境变量：

```bash
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="YOUR_LONG_LIVED_ACCESS_TOKEN"
```

### 3. 配置重点实体与别名

你至少需要根据自己的 HA 实体，调整：
- `config/focus_entities.json`
- `config/entity_aliases.json`

这两份配置会决定：
- 哪些设备属于“重点设备”
- 回答时显示什么人类可读名称

## 运行

### 1. 单次同步

```bash
cd openclaw-ha
./scripts/run_once.sh
```

### 2. 循环刷新

```bash
cd openclaw-ha
REFRESH_INTERVAL=60 ./scripts/run_loop.sh
```

### 3. 事件监听

```bash
cd openclaw-ha
./scripts/run_ws_listener.sh
```

### 4. 读取缓存

```bash
cd openclaw-ha
python3 src/read_cache.py brief
python3 src/read_cache.py summary
python3 src/read_cache.py card
```

### 5. 健康检查

```bash
cd openclaw-ha
./scripts/healthcheck.sh
```

healthcheck 会检查：
- 配置文件是否存在
- 缓存文件是否存在且最近是否有更新
- WebSocket listener service 是否 active / enabled
- 最近日志与事件数量

## systemd user service

参考：
- `docs/systemd.md`
- `systemd/openclaw-ha-ws.service`

## Git 策略

这个项目推荐采用：
- **一个项目目录**
- **代码入 git**
- **本地配置 / 运行数据 / 日志不入 git**

`.gitignore` 已默认忽略：
- `data/`
- `logs/`
- `config/*.json`

并保留：
- `config/*.example.json`

## 与 OpenClaw skill 的关系

`openclaw-ha` 本身可以独立运行；OpenClaw 集成是推荐用法之一，但不是唯一用法。

在 OpenClaw 中，当前推荐采用：
- **继续保留一个 `home-assistant` skill**
- 由该 skill 学会如何使用 `openclaw-ha`

也就是说：
- `openclaw-ha` 负责提供能力层
- `home-assistant` skill 负责告诉 agent 什么时候读取缓存、什么时候实时查询、什么时候刷新

### 推荐职责划分

#### `openclaw-ha` 负责
- 状态同步
- 事件监听
- 缓存生成
- 回答摘要生成
- 本地运行与服务管理

#### `home-assistant` skill 负责
- 判断用户问题是“家庭感知”还是“实时控制”
- 对高频状态问答优先使用缓存
- 对控制类请求和高风险状态优先走实时 HA
- 在缓存过期时触发刷新
- 在 `openclaw-ha` 不可用时回退到传统 HA 路径

### 为什么当前不新增第二个 skill

因为当前阶段更重要的是：
- 保持 agent 路由简单
- 保持能力边界清楚
- 先让现有 `home-assistant` skill 升级成“实时控制 + 感知接入”的统一入口

只有在后续缓存感知逻辑显著复杂化时，再考虑是否拆出第二个 skill。

更多说明见：
- `docs/skill-integration-design.md`
- `docs/home-assistant-skill-draft.md`

## 当前状态

这是一个**可运行原型**，适合作为：
- OpenClaw × Home Assistant integration layer
- 智能家居 Agent 的家庭状态上下文层
- 后续扩展事件批处理、局部缓存更新、统一 Agent 接口的基础

## 局部缓存更新

当前 `sync_snapshot.py` 已支持两种模式：

- **full**：拉取 `/api/states` 全量重建
- **partial**：当监听器传入变更实体且本地已有 `raw_states.json` 时，仅拉取变更实体，再在本地重建摘要

说明：
- 摘要仍然会整体重算
- 但对 Home Assistant 的 API 拉取已经从“全量”收敛到“按变更实体拉取”
- 如果局部拉取失败，会自动回退到全量模式

## 后续可演进方向

- 更通用的安装流程
- 更细粒度事件 batching / debounce
- 多房间模板
- 更标准的 agent adapter interface
- OpenClaw skill 适配文档
