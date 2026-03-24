# Repo hardening / 私有耦合清理清单

## 已完成

- 单项目目录策略
- `.gitignore` 忽略本地配置、数据、日志
- 增加 `config/*.example.json`
- 增加开源 README
- 增加 LICENSE
- 增加开源整理文档
- HA 配置支持环境变量优先
- systemd 模板改为可替换示例

## 当前仍存在的私有耦合点

### 1. 仍保留旧路径 fallback
当前脚本仍兼容某些特定工作空间下的旧配置路径，方便本地继续使用。

**建议改造：**
- 长期可考虑把旧路径 fallback 降为可选开关
- 对外 README 只宣传环境变量 / `config/ha.json`

### 2. 脚本仍带有 OpenClaw 兼容语义
虽然项目已可独立运行，但部分设计仍明显面向 Agent / OpenClaw 使用场景。

**建议改造：**
- README 中把 OpenClaw 集成列为“可选集成”
- 保持核心同步层独立表述

### 3. 本地真实文件仍存在于目录中
这些文件虽然已被 `.gitignore` 忽略，但发布前仍需人工确认：
- `config/*.json`
- `data/*`
- `logs/*`

### 4. 依赖说明还可以更完整
当前项目实际依赖：
- Python 3
- Node.js（WebSocket 监听）
- Home Assistant long-lived token

**建议改造：**
- 后续补版本建议
- 说明为什么监听器采用 Node 实现

## 建议下一步优先级

### P0
- 发布前按 `docs/release-checklist.md` 做一次完整检查

### P1
- README 增加更清晰的安装依赖说明
- README 增加 Agent / OpenClaw 只是可选集成的表述

### P2
- 增加初始化脚本或 bootstrap 指引
- 增加 architecture 图或时序图
