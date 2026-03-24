# 发布前检查清单

## 目标

在公开仓库前，确认项目里只保留：
- 通用代码
- 文档
- 示例配置
- 服务模板

不带入任何本地实例数据、日志或敏感信息。

## 必查项

### 1. 配置
- [ ] `config/*.json` 未提交
- [ ] 只保留 `config/*.example.json`
- [ ] `config/ha.json` 未提交
- [ ] 不含真实 HA URL
- [ ] 不含真实 HA token

### 2. 运行数据
- [ ] `data/` 未提交
- [ ] `logs/` 未提交
- [ ] 不含 `recent_events.jsonl`
- [ ] 不含真实 `summary.json` / `raw_states.json`

### 3. 文档
- [ ] README 不包含私有目录路径
- [ ] docs 不包含私有目录路径
- [ ] docs 不包含真实用户名 / 主机路径

### 4. 代码
- [ ] 默认配置来源对外可用
- [ ] 环境变量方式可工作
- [ ] 不依赖私有目录结构才能启动

### 5. Git 检查
- [ ] `git status` 只出现应纳入的源码/文档/模板文件
- [ ] `git add . --dry-run` 未包含 data/logs/真实配置

## 推荐发布顺序

1. 先运行敏感信息扫描
2. 再检查 `.gitignore`
3. 再看 `git status`
4. 最后才正式提交
