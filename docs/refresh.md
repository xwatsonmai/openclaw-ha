# 定时刷新方案

## 目标

让 `openclaw-ha` 自动周期刷新本地状态缓存，而不是每次手动执行。

## 当前实现

项目内提供：

- `scripts/run_once.sh`：执行一次同步
- `scripts/run_loop.sh`：按固定间隔循环执行同步

默认刷新间隔：60 秒。

## 推荐使用顺序

### 1. 先手动验证

```bash
cd openclaw-ha
./scripts/run_once.sh
```

### 2. 再启动循环刷新

```bash
cd openclaw-ha
REFRESH_INTERVAL=60 ./scripts/run_loop.sh
```

## 输出文件

每次刷新会更新：

- `data/raw_states.json`
- `data/summary.json`
- `data/answer_brief.json`
- `data/answer_card.md`

并写日志到：

- `logs/refresh.log`

## 后续可演进方向

1. 接入 systemd user service
2. 接入 cron / pm2 / 守护方式
3. 支持失败重试
4. 支持信号触发立即刷新
5. 接入 HA 事件驱动，轮询作为兜底
