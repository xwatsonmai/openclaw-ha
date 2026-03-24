# OpenClaw skill integration design

## 目标

在 OpenClaw 中，继续保留 **一个 `home-assistant` skill**，而不是新增第二个技能。

该 skill 升级后同时具备两类能力：

1. **实时控制 / 实时查询能力**
2. **基于 `openclaw-ha` 的家庭状态感知能力**

也就是：
- `openclaw-ha` 负责提供能力层
- `home-assistant` skill 负责指导 agent 如何使用这层能力

---

## 当前建议

当前推荐架构是：

> **一个 skill + 一个独立项目**

即：
- OpenClaw 中继续使用一个 `home-assistant` skill
- `openclaw-ha` 作为独立项目存在
- skill 学会何时调用 `openclaw-ha`

不推荐当前阶段额外拆分成第二个 skill，因为会增加路由和边界复杂度。

---

## 分工

### `openclaw-ha` 负责

- Home Assistant 状态同步
- WebSocket 事件订阅
- 定时轮询兜底
- 本地状态缓存生成
- 回答摘要生成
- 本地服务运行（systemd / listener）

### `home-assistant` skill 负责

- 判断用户问题属于“状态感知”还是“实时控制”
- 对高频状态问答优先读缓存
- 对高风险状态或明确实时请求走实时查询
- 在缓存过期时触发刷新
- 在控制动作后触发必要刷新
- 当 `openclaw-ha` 不可用时回退到传统 HA 实时路径

---

## Skill 决策规则

### 1. 优先读缓存的场景

适合优先使用 `openclaw-ha`：

- 家里现在什么情况
- 哪些灯开着
- 空调开没开
- 有没有异常设备
- 某个重点设备现在什么状态
- 最近家庭状态概览

优先读取：
- `data/answer_brief.json`
- `data/summary.json`
- `data/answer_card.md`

### 2. 优先实时调用的场景

这些请求不应只靠缓存：

- 打开 / 关闭设备
- 调节空调温度 / 模式
- 执行动作类请求
- 用户明确要求“实时”“立刻刷新”“马上查”
- 门锁 / 安防 / 电源等高风险状态确认
- 缓存结果和用户反馈不一致时

### 3. 缓存过期时

如果缓存超过 freshness 规则：
- 先触发一次刷新
- 再回答

### 4. 控制后行为

如果 agent 刚刚执行了设备控制：
- 应优先刷新相关缓存
- 避免回答仍停留在旧状态

---

## 技能需要知道的运行入口

### 缓存读取入口
- `python3 src/read_cache.py brief`
- `python3 src/read_cache.py summary`
- `python3 src/read_cache.py card`

### 刷新入口
- `./scripts/run_once.sh`

### 常驻监听
- `./scripts/run_ws_listener.sh`
- 或 `systemctl --user status openclaw-ha-ws.service`

---

## 当前落地状态

现有 `home-assistant` skill 已按该思路升级，核心新增内容包括：

- 明确区分“缓存优先回答”与“实时 HA 调用”
- 将 `openclaw-ha` 视为增强层，而非单点依赖
- 写入缓存入口、刷新入口、监听状态检查入口
- 增加缓存缺失 / 过期时的回退策略

---

## Skill 的退化策略

如果 `openclaw-ha` 出现以下情况：
- 项目不存在
- 配置缺失
- 缓存文件不存在
- 监听器未运行
- 刷新失败

则 `home-assistant` skill 应退回：
- 原本的 Home Assistant 实时查询 / 控制能力

也就是说：

> `openclaw-ha` 是增强层，不是单点依赖。

---

## 推荐演进顺序

### 当前阶段
- 继续只保留一个 `home-assistant` skill
- 让 skill 学会调用 `openclaw-ha`

### 后续阶段
如果缓存感知能力进一步复杂化，再考虑是否拆成独立第二 skill。

但在当前阶段，没有必要提前拆分。
