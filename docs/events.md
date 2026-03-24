# HA 事件订阅方案

## 目标

让 `openclaw-ha` 不只依赖轮询，而是直接订阅 Home Assistant 事件流，在状态变化时尽快触发缓存更新。

## 当前方案

优先采用 **Home Assistant WebSocket API**：

1. 连接 `ws://<ha>/api/websocket`（或 `wss://`）
2. 使用长期 token 鉴权
3. 订阅 `state_changed` 事件
4. 收到事件后：
   - 记录事件日志
   - 判断是否涉及关注实体/相关实体
   - 触发一次缓存重建

## 为什么先选 WebSocket

- 比 webhook 更贴近 HA 原生能力
- 不需要额外在 HA 里写很多自动化
- 事件粒度完整，后续扩展更容易

## 与轮询的关系

采用：

- WebSocket 事件驱动为主
- `run_loop.sh` 定时刷新为兜底

这样即使：
- WebSocket 断线
- 事件漏掉
- 本地进程重启

也还能靠轮询补齐状态。

## 当前项目内相关脚本

- `src/sync_snapshot.py`：全量重建缓存
- `src/ha_ws_listener.js`：监听 HA WebSocket 事件
- `scripts/run_loop.sh`：轮询兜底
- `scripts/run_ws_listener.sh`：启动事件监听
- `config/ws_noise_rules.json`：事件降噪规则

## 事件处理策略（当前版）

当前版做了两层收敛：

1. **事件过滤降噪**
   - 忽略 `sun.sun` 等无关实体
   - 忽略大量非家居状态问答无关 domain
   - 忽略指示灯 / 提示音 / 备用开关等噪音实体
   - 仅允许核心 domain 触发同步

2. **debounce**
   - 默认 2 秒内合并重复触发

第一版仍然保持：
- 一旦判定事件有价值
- 就调用一次 `sync_snapshot.py` 做全量重建

## 第二版可优化方向

1. 只对重点实体变化触发重建
2. 更细的 debounce / batching
3. 局部更新缓存而不是每次全量重建
4. 断线自动重连 + 状态监控
