# 开源整理说明

## 项目定位

该项目建议以 **`openclaw-ha`** 的定位对外发布。

它的核心不是“同步”或“缓存”本身，而是：
- 把 Home Assistant 能力接入 OpenClaw Agent
- 让智能助手具备家庭状态感知与低延迟回答能力

## 推荐策略

保持 **一个项目目录**，不要长期维护私有版 / 公有版两个目录。

推荐做法：
- 代码、文档、模板配置进入 git
- 本地实例配置、数据、日志不进入 git

## 哪些文件应该进入 git

- `src/`
- `scripts/`
- `docs/`
- `systemd/`
- `README.md`
- `.gitignore`
- `LICENSE`
- `config/*.example.json`

## 哪些文件不应该进入 git

- `data/*`
- `logs/*`
- `config/*.json`（真实配置）
- 任何包含 HA URL / token / 私有实体名 / 私有日志的文件

## 发布前检查清单

### P0
- [ ] 确认没有 HA token
- [ ] 确认没有 HA 内网地址
- [ ] 确认没有真实日志提交
- [ ] 确认没有真实状态快照提交
- [ ] 确认 `.gitignore` 生效
- [ ] 确认只保留 `*.example.json`

### P1
- [ ] README 改成通用说明
- [ ] 文档去掉私有路径和用户信息
- [ ] 加 LICENSE
- [ ] 补英文说明（如有需要）

### P2
- [ ] 做环境变量配置方式
- [ ] 做更通用的安装流程
- [ ] 准备 demo / screenshot / architecture 图

## 为什么不建议双目录长期同步

因为会带来：
- 重复维护
- 容易分叉
- 容易漏同步
- 修 bug 成本更高

双目录更适合作为“发布前导出流程”，不适合作为日常开发方式。
