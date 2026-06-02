export const meta = {
  name: 'dmp-data-fix',
  description: 'DMP data3 异常数据修复工作流',
  phases: [
    { title: '数据备份', detail: '备份 data3.csv 到带时间戳的备份文件' },
    { title: '数据快照', detail: '记录所有异常数据的精确位置' },
    { title: '执行删除', detail: '删除 5/27~5/31 全部新数据 + 5/24~5/26 异常虚高数据' },
    { title: '缓存清理', detail: '清理 completed_items.json 中 5/24 之后的虚假完成标记' },
    { title: '验证修复', detail: '验证 data3.csv 修复后的状态' },
  ],
}

phase('数据备份')

const backup = await agent(`
  备份 data3.csv：

  1. 复制 /Users/hutou/Desktop/work plat/DMP_test_package/core/data3.csv
  2. 备份到 /Users/hutou/Desktop/work plat/DMP_test_package/core/data3_pre_fix_backup_20260601.csv
  3. 验证备份文件存在且行数与原文件一致
  4. 输出备份文件的 MD5 校验和

  使用 Python 执行（不依赖 shell 通配符）：
  - 读取原文件统计行数
  - shutil.copy2 复制
  - 再次统计备份文件行数
  - 计算 MD5
`, { label: '备份 data3.csv', phase: '数据备份' })

phase('数据快照')

const snapshot = await agent(`
  扫描 data3.csv，识别所有需要删除的异常数据行：

  **删除规则 A**：删除 5/27~5/31（2026/05/27 到 2026/05/31，含 2026/5/27 到 2026/5/31）的所有数据
  **删除规则 B**：删除 5/24~5/26 中"资产总量"超过历史均值 50% 的异常行

  异常判定（基于以下商品的异常幅度）：
  - 803474428381: 5/24~5/27 虚高（5/28 跌回 1.09M）
  - 1010458880710: 5/24~5/26 突然出现（历史均值 253K，实际 768K）
  - 587051744204: 5/26 1.84M（5/24 1.74M，5/28 1.08M）→ 5/26 异常
  - 597655781410: 5/26 249K（5/25 224K，5/28 198K）→ 5/26 略异常
  - 801760206476: 5/26 855K（5/25 748K，5/28 702K）→ 5/26 略异常
  - 803417397714: 5/26 571K（5/25 435K，5/28 187K）→ 5/26 异常
  - 870597889980: 5/26 1.2M（5/25 1.18M，5/28 673K）→ 5/26 略异常
  - 994162104051: 5/26 405K（5/25 469K，5/28 173K）→ 5/26 略异常
  - 683395365107: 5/26 799K（5/25 646K，5/28 521K）→ 5/26 异常
  - 933524395698: 5/26 452K（5/25 348K，5/28 174K）→ 5/26 异常
  - 587053192746: 5/26 257K（5/25 261K，5/28 216K）→ 略异常
  - 612503357090: 5/26 236K（5/25 235K，5/28 155K）→ 略异常

  简化规则：
  - 规则 A：直接删除 5/27~5/31（任何日期格式）
  - 规则 B：删除 5/24~5/26 中"资产总量 > 1.5x 该商品 5/1~5/20 历史均值"的所有行

  输出：
  1. 将要删除的总行数
  2. 按商品+日期列出要删除的行
  3. 保留 5/1~5/20 的所有数据不动
  4. 保留 5/24~5/26 中正常的行（如 621639424901、621639424901）

  项目路径：/Users/hutou/Desktop/work plat/DMP_test_package/core/
`, { label: '识别要删除的行', phase: '数据快照' })

phase('执行删除')

const execute = await agent(`
  执行删除操作，生成修复后的 data3.csv：

  1. 读取 data3.csv 所有行
  2. 过滤掉要删除的行
  3. 写回 data3.csv
  4. 报告删除的行数

  关键要求：
  - **不要修改任何其他文件**
  - **保留表头行**
  - **保留所有 5/1~5/20 的数据**
  - **保留所有 5/21 之前的数据**
  - **删除 5/27~5/31 全部行**
  - **删除 5/24~5/26 异常行**（按 snapshot 阶段识别出的清单）

  实施步骤：
  - 用 Python pandas 或 csv 标准库
  - 写入前先写入临时文件 data3.csv.tmp，再 atomic rename
  - 验证最终行数 = 原行数 - 删除行数
  - 计算新文件的 MD5 校验和

  输出：
  - 删除前总行数
  - 删除行数
  - 删除后总行数
  - 删除的具体行数（按规则 A 和规则 B 分别统计）
`, { label: '执行删除', phase: '执行删除' })

phase('缓存清理')

const cleanup = await agent(`
  清理 completed_items.json：

  1. 读取 /Users/hutou/Desktop/work plat/DMP_test_package/core/completed_items.json
  2. 找出所有日期 >= 2026-05-24 的条目
  3. 删除这些条目
  4. 写回文件

  同时清理 5/24 之前的 1010458880710 条目（该商品在 5/24 首次出现，5/1~5/23 没有数据）

  实施：
  - 用 json 标准库
  - 写入前先备份到 completed_items_post_fix_backup_20260601.json
  - 输出清理前后的条目数
`, { label: '清理 completed_items.json', phase: '缓存清理' })

phase('验证修复')

const verify = await agent(`
  验证修复后的 data3.csv 状态：

  1. 检查文件存在且可读
  2. 统计总行数（应比原来少 69~100 条）
  3. 列出最近 10 个日期的每个商品数据
  4. 确认 5/27~5/31 已无数据
  5. 确认 5/24~5/26 异常行已删除
  6. 计算并输出 MD5 校验和

  输出：
  - 修复前/后行数对比
  - 最近 10 天数据（按商品）
  - 5/27~5/31 是否完全为空
  - 5/24~5/26 异常行是否清理
`, { label: '验证修复', phase: '验证修复' })

return {
  backup,
  snapshot,
  execute,
  cleanup,
  verify,
  summary: 'DMP data3 异常数据修复完成'
}
