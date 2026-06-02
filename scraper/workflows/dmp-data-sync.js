export const meta = {
  name: 'dmp-data-sync',
  description: 'DMP数据同步工作流',
  phases: [
    { title: '数据检查', detail: '检查数据文件状态' },
    { title: '数据同步', detail: '同步数据到指定位置' },
    { title: '同步验证', detail: '验证数据同步结果' },
  ],
}

phase('数据检查')

const dataCheck = await agent(`
  检查数据文件状态：

  1. 检查 data.csv 的最后更新时间和数据量
  2. 检查 data2.csv 的最后更新时间和数据量
  3. 检查 data3.csv 的最后更新时间和数据量
  4. 检查数据格式是否正确

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  请提供数据检查报告，包括：
  - 各数据文件的最后更新时间
  - 各数据文件的数据量
  - 数据格式是否正确
  - 是否需要同步
`, { label: '数据检查', phase: '数据检查' })

phase('数据同步')

const dataSync = await agent(`
  同步数据到指定位置：

  1. 复制 data.csv 到指定目录
  2. 复制 data2.csv 到指定目录
  3. 复制 data3.csv 到指定目录
  4. 生成同步日志

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  同步要求：
  - 保留历史数据
  - 生成同步日志
  - 记录同步时间和数据量

  请提供同步报告，包括：
  - 同步状态
  - 同步的数据量
  - 同步日志位置
`, { label: '数据同步', phase: '数据同步' })

phase('同步验证')

const syncValidation = await agent(`
  验证数据同步结果：

  1. 检查目标目录的数据文件是否存在
  2. 检查数据文件的内容是否正确
  3. 检查数据格式是否一致
  4. 生成验证报告

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  验证要求：
  - 检查数据完整性
  - 检查数据格式
  - 检查数据一致性

  请提供验证报告，包括：
  - 验证结果
  - 数据质量评估
  - 建议的后续步骤
`, { label: '同步验证', phase: '同步验证' })

return {
  dataCheck,
  dataSync,
  syncValidation,
  summary: 'DMP数据同步完成'
}
