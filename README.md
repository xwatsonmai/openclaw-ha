# openclaw-ha

`openclaw-ha` 是一个给 **OpenClaw Agent 接入 Home Assistant** 用的集成层。

它的重点不是单独做一个 HA 工具箱，而是让 Agent 具备这两类能力：

- **智能家居控制**：开关灯、调空调、查设备状态
- **家庭状态感知**：提前同步 HA 状态，生成摘要缓存，让 Agent 更快回答“家里现在什么情况”这类问题

一句话说：

> `openclaw-ha` 负责把 Home Assistant 的状态同步、事件监听、摘要缓存这层能力准备好，让 OpenClaw 中的 Agent 可以直接接入并使用。

---

## 它解决什么问题

传统 Agent 接 HA 的方式通常是：
- 用户提问
- Agent 临时查 HA
- 再现场组织回答

这样的问题是：
- 延迟高
- 状态不稳定
- 用户在 HA App 里改了东西，Agent 感知滞后
- 很难形成“家庭状态摘要”

`openclaw-ha` 提供的是另一条路：

- 先同步 Home Assistant 状态
- 再监听事件变化
- 再生成缓存摘要
- 最后让 Agent 优先用缓存回答高频问题，必要时再实时查 HA

---

## 快速开始

这里给两套入口：

- **给 Agent 的快速开始**：适合直接把一句话 + git 链接丢给 Agent
- **给人类手动安装的快速开始**：适合自己手动部署

### 给 Agent 的快速开始

如果你想把这件事直接交给 Agent，最短可复制版可以直接用这个：

```text
请阅读该项目说明，并完成安装与接入：
https://github.com/xwatsonmai/openclaw-ha

目标：
- 拉取这个 git 项目到当前 OpenClaw 工作区
- 按 README 完成安装
- 配置 Home Assistant URL / token
- 配置重点设备和别名
- 运行首次同步
- 启动 WebSocket listener
- 运行 healthcheck
- 如果当前工作区已有 home-assistant skill，则把它接到 openclaw-ha
- 最后输出安装结果、服务状态、缓存状态、剩余待补配置

要求：
- 不要把真实 token 提交进 git
- 本地 config / data / logs 不入库
- 首次安装时只把 HA URL / token 作为必需输入
- `focus_entities` / `entity_aliases` / 规则配置优先自动生成或后补
- Agent 默认不拥有 HA URL / token
- 如果当前工作区里没有现成 HA 配置，必须先询问用户
- 如用户没有 token，需先指导用户在 Home Assistant 中生成 long-lived access token
```

### 快速开始（如果你是 Agent）

1. 拉取本项目

```bash
cd /path/to/openclaw-workspace
git clone https://github.com/xwatsonmai/openclaw-ha.git
cd openclaw-ha
```

2. 阅读 README，并按快速开始执行

3. 运行 bootstrap 初始化配置

```bash
./scripts/bootstrap.sh
```

4. 配置 HA URL 和 token
- 优先写入 `config/ha.json`
- 或使用环境变量 `HA_URL` / `HA_TOKEN`
- 这是首次安装唯一必需的配置输入
- Agent 默认不应假设自己已经知道这些值
- 如果当前工作区未发现现有 HA 配置，则必须先询问用户

5. 对其余配置采用“先默认、后补充”策略
- `focus_entities.json` 可由 Agent 先生成初始版本
- `entity_aliases.json` 可先直接使用 HA friendly_name
- `cache_rules.json` / `ws_noise_rules.json` 默认先用项目内置规则
- 这些都不应阻塞首次安装

6. 运行首次同步

```bash
./scripts/run_once.sh
```

7. 启动 listener
- 先手动验证 `./scripts/run_ws_listener.sh`
- 长期运行优先配置 `systemd --user`

8. 运行 healthcheck

```bash
./scripts/healthcheck.sh
```

9. 如果工作区已有 `skills/home-assistant`
- 不要重复造第二套 skill
- 直接把现有 `home-assistant` skill 接到 `openclaw-ha`
- 初始化过程中，除 `ha.json` 外，其余配置优先自动生成初始版本或延后补齐
- 让它形成：
  - home overview 优先读缓存
  - 控制类请求走实时 HA
  - 控制后做 delayed + throttled partial refresh

10. 最后汇报
- 改了哪些文件
- 当前服务是否运行
- 缓存是否生成成功
- 还缺什么配置

### 给人类手动安装的快速开始

如果你的目标是：

> 让 OpenClaw 里的 Agent 尽快接入 HA，并获得“控制 + 家庭状态感知”能力

按下面做就行。

#### 第 1 步：准备项目

```bash
cd /path/to/your/openclaw-workspace
git clone https://github.com/xwatsonmai/openclaw-ha.git
cd openclaw-ha
./scripts/bootstrap.sh
```

这一步会准备配置文件模板。

但在首次安装时，你只需要优先关心：
- `config/ha.json`

其他配置文件先不用急着改，可以后补。

#### 第 2 步：填写唯一必需配置：HA 配置

首次安装时，**唯一必需的配置就是**：

```bash
config/ha.json
```

但要注意：
- Agent 默认通常并不知道你的 HA URL 和 token
- 如果工作区里不存在现有配置，就需要先向用户询问
- 如果用户还没有 token，需要先引导用户去 Home Assistant 生成

内容示例：

```json
{
  "url": "http://homeassistant.local:8123",
  "token": "YOUR_LONG_LIVED_ACCESS_TOKEN"
}
```

也可以不用文件，直接用环境变量：

```bash
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="YOUR_LONG_LIVED_ACCESS_TOKEN"
```

### 如何获取 HA URL 和 token

#### HA URL
通常会是以下几种之一：
- `http://homeassistant.local:8123`
- `http://<局域网IP>:8123`
- 你自己配置的 Home Assistant 域名

#### Long-lived access token
在 Home Assistant Web 页面中：

1. 打开 Home Assistant
2. 点击左下角用户头像 / Profile
3. 找到 **Long-Lived Access Tokens**
4. 创建一个新的 token
5. 复制后填入 `config/ha.json` 或环境变量

注意：
- token 通常只显示一次
- 不要提交进 git
- 不要发到公开仓库或公开聊天记录里

#### 第 3 步：先直接运行，不必先配其他文件

除了 `config/ha.json` 之外，其他配置都不再视为首次安装门槛：

- `config/focus_entities.json`
- `config/entity_aliases.json`
- `config/cache_rules.json`
- `config/ws_noise_rules.json`

这些文件都可以：
- 先使用默认值
- 在初始化过程中由 Agent 自动生成初始版本
- 在后续使用中逐步补充和调整

也就是说，**第一次安装时，先把 `ha.json` 配好就可以继续往下走。**

#### 第 4 步：先跑一次同步

```bash
./scripts/run_once.sh
```

成功后会生成：
- `data/raw_states.json`
- `data/summary.json`
- `data/answer_brief.json`
- `data/answer_card.md`

#### 第 5 步：启动事件监听

先手动跑：

```bash
./scripts/run_ws_listener.sh
```

长期运行建议使用 systemd user service：

```bash
mkdir -p ~/.config/systemd/user
cp ./systemd/openclaw-ha-ws.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-ha-ws.service
systemctl --user status openclaw-ha-ws.service
```

#### 第 6 步：检查健康状态

```bash
./scripts/healthcheck.sh
```

---

## 给 Agent 的一段可复制提示词

如果你希望“把事情交给 Agent 自己做”，下面给两种版本：

- **最小可复制版**：适合直接一句话丢给 Agent
- **执行型版本**：适合希望 Agent 严格按步骤完成安装和接入

### 版本 A：最小可复制版

```text
请帮我把当前 OpenClaw 工作区接入 Home Assistant，并安装配置 openclaw-ha，让 Agent 具备智能家居控制和家庭状态感知能力。

要求你直接完成：
- 初始化 openclaw-ha
- 配置 HA URL 和 long-lived token
- 配置重点设备和别名
- 首次同步并生成缓存摘要
- 启动 WebSocket listener
- 跑 healthcheck 确认正常
- 如果当前工作区已有 home-assistant skill，就把它接到 openclaw-ha，不要重复造第二套

要求：
- 不要把真实 token 提交进 git
- 本地 config / data / logs 不入库
- 缺少必要信息时再问我
- 最后给我一份结果汇报
```

### 版本 B：执行型版本

```text
请帮我把当前工作区接入 Home Assistant，并配置 openclaw-ha，让 Agent 具备智能家居控制与家庭状态感知能力。

目标：
1. 在当前 OpenClaw 工作区中接入 openclaw-ha
2. 初始化所需配置文件
3. 配置 Home Assistant URL 和 long-lived token
4. 配置 focus_entities 和 entity_aliases
5. 先跑一次同步，生成 summary / answer_brief / answer_card
6. 启动或配置 WebSocket listener（优先用 systemd user service）
7. 运行 healthcheck，确认整体状态正常
8. 如果工作区里已有 home-assistant skill，则把 skill 接到 openclaw-ha：
   - 家庭状态问答优先读缓存
   - 控制类请求走实时 HA
   - 控制后触发延迟、节流的局部 refresh
9. 最后给我一份结果汇报，说明：
   - 改了哪些文件
   - 当前服务是否运行
   - 缓存是否生成成功
   - 后续我还需要补哪些配置

要求：
- 优先使用 openclaw-ha 作为 HA 感知层
- 不要把真实 token 提交进 git
- 本地配置、data、logs 保持不入库
- 如果发现现有 skill 已存在，不要重复造第二套，优先在现有 home-assistant skill 上集成
- 如果能自动完成，就直接执行；只有在缺少 HA 地址、token、重点设备列表时再问我
```

### 版本 C：给执行型编码 Agent（Codex / Claude Code）

```text
在当前工作区完成 openclaw-ha 接入，目标是让 OpenClaw Agent 可以通过 Home Assistant 实现“实时控制 + 家庭状态感知”。

请直接执行，不要只给建议。

任务清单：
- clone 或接入 openclaw-ha 到当前工作区
- 运行 bootstrap 初始化配置
- 填写或接入 HA URL / token
- 根据现有设备补 focus_entities / entity_aliases
- 运行 run_once，确认生成 raw_states / summary / answer_brief / answer_card
- 配置并启动 WebSocket listener（优先 systemd user service）
- 运行 healthcheck
- 将现有 home-assistant skill 接到 openclaw-ha：
  - home overview 问题优先读缓存
  - 控制请求走实时 HA
  - 控制后触发 delayed + throttled partial refresh
- 不要提交真实 token、本地日志、本地 data
- 完成后输出：改动文件列表、服务状态、healthcheck 结果、剩余待补配置
```

---

## Agent 接入后的推荐工作流

接入完成后，推荐让 Agent 这样用：

### 1. 家庭状态问答
优先读缓存：
- `data/answer_brief.json`
- `data/summary.json`
- `data/answer_card.md`

适合的问题：
- 家里现在什么情况
- 哪些灯开着
- 空调开没开
- 有没有异常设备
- 扫地机在干嘛

### 2. 实时控制
直接走 Home Assistant：
- 打开/关闭设备
- 调空调温度
- 执行动作类请求
- 高风险确认（门锁、电源、安防）

### 3. 控制后刷新
控制成功后：
- 优先做一次延迟、节流的局部 refresh
- 避免回答还停留在旧状态

---

## 配置原则

### 首次安装唯一必需
- `config/ha.json`
- 或等价的 `HA_URL` / `HA_TOKEN` 环境变量

说明：
- 这通常不是 Agent 默认已知的信息
- 如果当前环境里不存在现成配置，Agent 应先询问用户

### 可以自动生成 / 可后补
- `config/focus_entities.json`
- `config/entity_aliases.json`
- `config/cache_rules.json`
- `config/ws_noise_rules.json`

推荐原则：
- 首次安装只要求用户提供 HA URL / token
- 其他配置优先让 Agent 自动生成初始版本
- 后续在真实使用中逐步补齐与调整

## 当前能力

- Home Assistant 全量状态同步
- WebSocket 事件监听
- 定时刷新兜底
- `summary.json` 结构化摘要
- `answer_brief.json` 简版回答摘要
- `answer_card.md` 文本回答卡
- focus entities 重点设备机制
- entity aliases 别名映射
- 事件降噪规则
- focus-first / per-entity debounce / batching
- 局部刷新（partial refresh）
- healthcheck
- systemd user service 模板

---

## 关键入口

### 同步

```bash
./scripts/run_once.sh
```

### 监听

```bash
./scripts/run_ws_listener.sh
```

### 读缓存

```bash
python3 src/read_cache.py brief
python3 src/read_cache.py summary
python3 src/read_cache.py card
```

### 健康检查

```bash
./scripts/healthcheck.sh
```

---

## systemd user service

参考：
- `docs/systemd.md`
- `systemd/openclaw-ha-ws.service`

---

## Git 策略

推荐：
- 代码入 git
- 文档入 git
- 示例配置入 git
- 本地真实配置 / data / logs 不入 git

默认忽略：
- `data/`
- `logs/`
- `config/*.json`

保留：
- `config/*.example.json`

---

## 与 OpenClaw skill 的关系

推荐结构：

- `openclaw-ha`：独立项目 / 能力层
- `skills/home-assistant`：OpenClaw 工作区内的 skill / 决策层

也就是：
- `openclaw-ha` 负责同步、监听、缓存、摘要
- `home-assistant` skill 负责判断什么时候读缓存、什么时候实时查 HA、什么时候控制后刷新

当前**不建议为了这个目的再拆第二个 skill 仓库**。

---

## 常见排查

### 1. 先看 healthcheck

```bash
./scripts/healthcheck.sh
```

### 2. 看 listener 状态

```bash
systemctl --user status openclaw-ha-ws.service
journalctl --user -u openclaw-ha-ws.service -n 100 --no-pager
```

### 3. 手动重新同步

```bash
./scripts/run_once.sh
```

### 4. 看最近日志

```bash
tail -n 50 logs/ws_listener.log
```

---

## 文档

建议继续看：
- `docs/events.md`
- `docs/systemd.md`
- `docs/skill-integration-design.md`
- `docs/architecture.md`
