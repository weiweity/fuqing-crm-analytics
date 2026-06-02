export const meta = {
  name: 'dmp-optimization',
  description: 'DMP项目优化计划执行工作流',
  phases: [
    { title: '代码审核', detail: '检查代码中的优化点' },
    { title: '立即修复', detail: '执行第一阶段优化任务' },
    { title: '验证测试', detail: '验证优化效果' },
  ],
}

phase('代码审核')

const codeReview = await agent(`
  审核 DMP 项目代码，检查以下优化点：
  1. import 拼写错误是否已修复
  2. 重复日志输出问题
  3. 日志初始化性能问题
  4. CSV 写入接口统一性
  5. 其他代码质量问题

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  请提供详细的审核报告，包括：
  - 问题描述
  - 问题位置（文件名和行号）
  - 严重程度
  - 修复建议
`, { label: '代码审核', phase: '代码审核' })

phase('立即修复')

const fixResult = await agent(`
  根据代码审核结果，执行第一阶段优化任务：

  1. 修复 import 拼写错误（如果存在）
  2. 消除重复日志输出
  3. 日志初始化优化

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  修复要求：
  - 只修改必要的代码
  - 保持现有功能不变
  - 添加注释说明修改原因
  - 确保所有模块都能正常运行

  请提供修复报告，包括：
  - 修改的文件和行号
  - 修改前后的代码对比
  - 修改原因
`, { label: '立即修复', phase: '立即修复' })

phase('验证测试')

const testResult = await agent(`
  验证优化效果：

  1. 检查代码语法是否正确
  2. 运行简单的导入测试
  3. 验证日志功能是否正常
  4. 验证 CSV 读写功能是否正常

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/

  验证步骤：
  - 使用 python3 -m py_compile 检查语法
  - 测试 import 是否正常
  - 测试日志函数是否正常工作
  - 测试 CSV 读写函数是否正常工作

  请提供验证报告，包括：
  - 测试结果
  - 是否存在问题
  - 建议的后续步骤
`, { label: '验证测试', phase: '验证测试' })

return {
  codeReview,
  fixResult,
  testResult,
  summary: 'DMP项目优化计划第一阶段执行完成'
}
