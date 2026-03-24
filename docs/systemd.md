# systemd user service

## 服务文件

项目内服务模板：
- `systemd/openclaw-ha-ws.service`

兼容旧文件名：
- `systemd/ha-state-sync-ws.service`（已弃用，不建议继续使用）

这是一个**示例模板**，其中路径需要按你的实际目录替换。

安装位置：
- `~/.config/systemd/user/openclaw-ha-ws.service`

## 安装步骤

### 1. 复制模板并修改路径

把下面两个值替换成你的实际目录：
- `WorkingDirectory=%h/path/to/openclaw-ha`
- `ExecStart=/usr/bin/env node %h/path/to/openclaw-ha/src/ha_ws_listener.js`

### 2. 安装并启动

```bash
mkdir -p ~/.config/systemd/user
cp ./systemd/openclaw-ha-ws.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now openclaw-ha-ws.service
systemctl --user status openclaw-ha-ws.service
```

## 常用命令

```bash
systemctl --user restart openclaw-ha-ws.service
systemctl --user stop openclaw-ha-ws.service
systemctl --user start openclaw-ha-ws.service
systemctl --user status openclaw-ha-ws.service
journalctl --user -u openclaw-ha-ws.service -n 100 --no-pager
```

## 说明

启用后，监听器由 systemd user 接管：
- 自动启动
- 异常自动重启
- 可通过 journalctl 查看日志

## 配置来源

监听器支持以下优先级：
1. 环境变量：`HA_URL` + `HA_TOKEN`
2. 项目内：`config/ha.json`
3. 兼容旧路径（供特定工作空间使用）
