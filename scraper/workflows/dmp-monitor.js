export const meta = {
  name: 'dmp-monitor',
  description: 'DMP监控告警工作流',
  phases: [
    { title: '状态检查', detail: '检查运行状态和日志' },
    { title: '数据质量', detail: '检查数据质量' },
    { title: '告警生成', detail: '生成告警报告' },
  ],
}

phase('状态检查')

const statusCheck = await agent(`
  检查 DMP 运行状态：

  1. 检查最近的运行日志
  2. 检查数据采集状态
  3. 检查错误日志
  4. 检查系统资源使用情况

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  检查内容：
  - 最近24小时的运行日志
  - 数据采集成功率
  - 错误和警告信息
  - 系统资源使用情况

  请提供状态检查报告，包括：
  - 运行状态
  - 成功率
  - 错误信息
  - 建议的后续步骤
`, { label: '状态检查', phase: '状态检查' })

phase('数据质量')

const dataQuality = await agent(`
  检查数据质量：

  1. 检查数据完整性
  2. 检查数据格式
  3. 检查数据一致性
  4. 检查异常数据

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  检查内容：
  - 最近7天的数据完整性
  - 数据格式是否正确
  - 数据是否一致
  - 是否有异常值

  请提供数据质量报告，包括：
  - 数据质量评估
  - 缺失的数据
  - 异常数据
  - 建议的后续步骤
`, { label: '数据质量', phase: '数据质量' })

phase('告警生成')

const alertGeneration = await agent(`
  生成告警报告：

  1. 分析状态检查结果
  2. 分析数据质量结果
  3. 生成告警报告
  4. 提供建议的后续步骤

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  告警内容：
  - 运行状态异常
  - 数据质量问题
  - 系统资源问题
  - 建议的后续步骤

  请提供告警报告，包括：
  - 告警级别
  - 告警内容
  - 建议的后续步骤
`, { label: '告警生成', phase: '告警生成' })

return {
  statusCheck,
  dataQuality,
  alertGeneration,
  summary: 'DMP监控告警检查完成'
}
