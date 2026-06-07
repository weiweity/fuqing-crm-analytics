# DMP 项目 Workflows

> 最后更新：2026-06-07
> 项目目标：保留核心 DMP 抓数功能和前端需要的 date, date2, date3 文件

---

## 概述

本目录包含 DMP 数据采集项目的自动化工作流脚本。这些工作流用于：

1. **数据采集**：每日数据采集、数据同步
2. **数据修复**：数据质量修复、数据验证
3. **监控告警**：运行状态监控、异常告警

---

## 工作流列表

### 1. 每日数据采集工作流

**文件**：`dmp-daily-run.js`
**用途**：每日数据采集
**阶段**：
- 环境检查：检查运行环境和登录状态
- 数据采集：运行三个数据采集模块
- 数据验证：验证采集的数据质量
- 同步报告：生成数据同步报告

**运行方式**：
```bash
# 在 Claude Code 中运行
Workflow({scriptPath: "dmp-daily-run.js"})
```

### 2. 数据同步工作流

**文件**：`dmp-data-sync.js`
**用途**：同步数据到前端
**阶段**：
- 数据检查：检查数据文件状态
- 数据同步：同步数据到指定位置
- 同步验证：验证数据同步结果

**运行方式**：
```bash
# 在 Claude Code 中运行
Workflow({scriptPath: "dmp-data-sync.js"})
```

### 3. 数据修复工作流

**文件**：`dmp-data-fix.js`
**用途**：修复数据质量问题
**阶段**：
- 问题诊断：识别数据质量问题
- 数据修复：执行修复操作
- 修复验证：验证修复结果

**运行方式**：
```bash
# 在 Claude Code 中运行
Workflow({scriptPath: "dmp-data-fix.js"})
```

### 4. 数据验证工作流

**文件**：`dmp-data-verify.js`
**用途**：验证数据完整性
**阶段**：
- 数据检查：检查数据文件完整性
- 质量验证：验证数据质量
- 报告生成：生成验证报告

**运行方式**：
```bash
# 在 Claude Code 中运行
Workflow({scriptPath: "dmp-data-verify.js"})
```

### 5. 监控告警工作流

**文件**：`dmp-monitor.js`
**用途**：监控运行状态和异常
**阶段**：
- 状态检查：检查运行状态和日志
- 数据质量：检查数据质量
- 告警生成：生成告警报告

**运行方式**：
```bash
# 在 Claude Code 中运行
Workflow({scriptPath: "dmp-monitor.js"})
```

---

## 工作流使用指南

### 运行工作流

在 Claude Code 中，使用 `Workflow` 工具运行工作流：

```javascript
// 运行每日数据采集工作流
Workflow({
  scriptPath: "scraper/workflows/dmp-daily-run.js",
  name: "dmp-daily-run"
})

// 运行数据修复工作流
Workflow({
  scriptPath: "scraper/workflows/dmp-data-fix.js",
  name: "dmp-data-fix"
})
```

### 查看工作流状态

使用 `/workflows` 命令查看工作流状态：

```
/workflows
```

### 恢复工作流

如果工作流中断，可以使用 `resumeFromRunId` 恢复：

```javascript
Workflow({
  scriptPath: "scraper/workflows/dmp-daily-run.js",
  resumeFromRunId: "wf_xxxxxxxx"
})
```

---

## 工作流脚本结构

每个工作流脚本都遵循以下结构：

```javascript
export const meta = {
  name: 'workflow-name',
  description: '工作流描述',
  phases: [
    { title: '阶段1', detail: '阶段1详情' },
    { title: '阶段2', detail: '阶段2详情' },
  ],
}

phase('阶段1')

const result1 = await agent(`
  任务描述
`, { label: '任务标签', phase: '阶段1' })

phase('阶段2')

const result2 = await agent(`
  任务描述
`, { label: '任务标签', phase: '阶段2' })

return { result1, result2 }
```

---

## 最佳实践

1. **工作流命名**：使用小写字母和连字符，例如 `dmp-daily-run`
2. **阶段命名**：使用中文，清晰描述阶段内容
3. **任务标签**：使用简洁的中文标签，便于识别
4. **错误处理**：在工作流中添加错误处理逻辑
5. **日志记录**：使用 `log()` 记录关键步骤
6. **返回值**：返回结构化数据，便于后续处理

---

## 常见问题

### 工作流运行失败怎么办？

1. 检查工作流脚本是否有语法错误
2. 检查 agent 任务描述是否清晰
3. 检查文件路径是否正确
4. 使用 `resumeFromRunId` 恢复中断的工作流

### 如何调试工作流？

1. 使用 `log()` 记录关键步骤
2. 检查工作流日志文件
3. 逐步运行工作流，检查每个阶段的结果

### 如何创建新的工作流？

1. 在 `workflows/` 目录创建新的 `.js` 文件
2. 遵循工作流脚本结构
3. 在本 README.md 中添加工作流说明
4. 测试工作流是否正常运行

---

*此文件由 AI 维护，最后更新：2026-06-07*
