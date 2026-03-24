# 下一阶段建议

## 当前阶段已完成

- 独立项目目录
- 状态同步脚本
- 缓存过滤与清洗
- 主设备清单
- 别名映射
- 定时刷新脚本
- 结构化摘要 + 文本回答卡
- WebSocket 事件监听
- systemd user service
- 开源结构整理
- OpenClaw skill 集成设计
- bootstrap / healthcheck 脚本

## 下一阶段优先级

### P1. 局部缓存更新
- 从“全量重建”演进到“局部更新 + 摘要重算”

### P2. 事件降噪继续细化
- 更细的 focus 分组策略
- 按 domain / room 做差异化触发
- 更长窗口的事件聚合策略

### P3. 更稳的健康检查与运维说明
- 增加 stale 判定阈值
- 记录 listener / sync 状态指标
- 增加诊断示例输出

### P4. OpenClaw skill 适配落地
- 将设计稿正式合并到 skill 工作流中
