export const meta = {
  name: 'dmp-daily-run',
  description: 'DMP数据采集日常工作流',
  phases: [
    { title: '环境检查', detail: '检查运行环境和登录状态' },
    { title: '数据采集', detail: '运行三个数据采集模块' },
    { title: '数据验证', detail: '验证采集的数据质量' },
    { title: '同步报告', detail: '生成数据同步报告' },
  ],
}

phase('环境检查')

const envCheck = await agent(`
  检查 DMP 数据采集环境：

  1. 检查 chrome_profile/ 目录是否存在
  2. 检查 account.txt 文件是否存在
  3. 检查 Python 依赖是否安装
  4. 检查数据文件状态（data.csv, data2.csv, data3.csv）

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  请提供环境检查报告，包括：
  - 环境状态
  - 是否满足运行条件
  - 需要修复的问题
`, { label: '环境检查', phase: '环境检查' })

phase('数据采集')

const assetsResult = await agent(`
  运行资产诊断数据采集：

  执行命令：python3 dmp_master.py --assets

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  采集要求：
  - 确保登录状态有效
  - 检查数据是否成功写入 data2.csv
  - 记录采集时间和数据量

  请提供采集报告，包括：
  - 采集状态
  - 采集的数据量
  - 是否有错误
`, { label: '资产诊断', phase: '数据采集' })

const flowResult = await agent(`
  运行流转数据采集：

  执行命令：python3 dmp_master.py --flow

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  采集要求：
  - 确保登录状态有效
  - 检查数据是否成功写入 data.csv
  - 记录采集时间和数据量

  请提供采集报告，包括：
  - 采集状态
  - 采集的数据量
  - 是否有错误
`, { label: '流转数据', phase: '数据采集' })

const itemsResult = await agent(`
  运行单品洞察数据采集：

  执行命令：python3 dmp_master.py --items

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  采集要求：
  - 确保登录状态有效
  - 检查数据是否成功写入 data3.csv
  - 记录采集时间和数据量

  请提供采集报告，包括：
  - 采集状态
  - 采集的数据量
  - 是否有错误
`, { label: '单品洞察', phase: '数据采集' })

phase('数据验证')

const dataValidation = await agent(`
  验证采集的数据质量：

  1. 检查 data.csv 的数据完整性
  2. 检查 data2.csv 的数据完整性
  3. 检查 data3.csv 的数据完整性
  4. 检查数据格式是否正确
  5. 检查是否有缺失日期

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  验证要求：
  - 检查最近7天的数据是否完整
  - 检查数据格式是否一致
  - 检查是否有异常值

  请提供验证报告，包括：
  - 数据质量评估
  - 缺失的数据
  - 异常数据
`, { label: '数据验证', phase: '数据验证' })

phase('同步报告')

const syncReport = await agent(`
  生成数据同步报告：

  1. 统计采集的数据量
  2. 检查数据同步状态
  3. 生成数据同步报告

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  报告内容：
  - 采集时间
  - 采集的数据量
  - 数据质量评估
  - 同步状态
  - 建议的后续步骤

  请提供完整的同步报告。
`, { label: '同步报告', phase: '同步报告' })

return {
  envCheck,
  assetsResult,
  flowResult,
  itemsResult,
  dataValidation,
  syncReport,
  summary: 'DMP数据采集完成，数据已同步到CSV文件'
}
