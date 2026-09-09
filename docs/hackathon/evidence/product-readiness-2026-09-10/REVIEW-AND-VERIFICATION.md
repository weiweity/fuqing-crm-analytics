# 本轮审查与验证

基线 main `788b5b108fed22526805248a86f310ef7602cc6e`，候选分支 `codex/competition-product-readiness`。最终源码由本目录 source-manifest.json 绑定。Git 发布及远端 CI 以实际 PR/commit 记录为准。

## 审查

按 gstack review 的 SQL/数据、并发、模型工具信任边界、shell、枚举消费者及完成度清单检查本轮完整差异；没有重新运行已停止的 OCR 或调用额外评审模型。

- 已修复：未保存图表选择被布局快捷键替换；新增红测复现 attempt 被替换，修复后保持当前预览至保存/放弃。
- 已修复：重开后“继续编辑草稿”只恢复 pending 而未加载预览；放弃草稿未释放编辑目标。组件覆盖恢复、放弃、再次编辑。fixture 的 GET 现在读取已保存版本，与真实 HTTP 一致。
- 已修复：手动编辑入口按 `modelAvailable=false` 显示“模型不可用”，与实际原生模型连接状态混淆。现在说明手动编辑和原生聊天的职责。
- 新图表合同沿现有权限/版本/取消/幂等事务，必填精确 block_id；TABLE/BAR/LINE/METRIC/EVIDENCE 的后端、类型、预览、持久化和展示消费者均检查。没有改冻结 C0 或上游源码。
- 真实调用中修复原生条件 schema 缺失及工具未注册；保留宿主会话身份，传递 AbortSignal，并设置 5 秒 HTTP 上限。模型不能提供 HTTP 凭据或替换权限身份。

本轮差异未发现尚待修复的阻断问题。产品仍有后述已确认缺口，不因此标记整产品通过。

## 实际验证

| 层级 | 结果 | 证据 |
|---|---|---|
| 完整日常合成后端 profile | 2282 passed / 77 skipped / 0 failures；239 个目标文件 | 初跑 `.context/checks/20260909T191247809919Z` 的 1–6 组，加修正文档后 `.context/checks/20260909T191912217065Z` 全 4 组 |
| Python 源码一致性 | 两次 source hash 相同：`9c28251a540c45ccf95fd5d7285e16e54a1a0a30dbaf1a2b5c2e6912e8d467a4` | 原始 summary.json 和逐组 JUnit；未把初次失败组重复计数 |
| B0 完整 pipeline | PASS：合同、Python/Node、类型、编译后 DOM、干净重建 | `.context/readiness-b0-final.log`；clean-build-HlNOWb；构建证据摘要见 build-verification.json |
| 图表/草稿定向回归 | 20 passed（含 11 个编译后 DOM） | `.context/chart-dom-fixed.log` |
| 图表 HTTP | 新增 8 passed；相关组合 27 passed | `test_competition_chart_persistence.py`，完整后端亦包含 |
| 真实浏览器 | BAR v2 重开；LINE 草稿刷新后恢复，放弃返回 BAR；草稿 v2 重开；390 无横向溢出；同页 footer 重开 | 截图、HTTP trace 与 UAT 清单 |
| 欢迎页 | 3 个新运行时首点无误报；其中 2 次点击后刷新仍正常 | welcome-reproduction.json；历史错误根因未复现，不声称已修复 |
| 备份与恢复 | 4 个小型 SQLite quick_check=ok；新应用从恢复目录读取同一块 BAR v2 | state-backup-restore.json |

初跑失败均保留：STATUS 超过短状态页行数上限，迁移历史上下文后修正；diagnose 测试默认假定当前无运行实例，改用明确的冷状态 fixture，不停止候选来迁就断言；新增草稿红测及错误工具链路径的失败日志亦保留。B0 最终通过后按 4325/18083 配置重建供浏览器使用，未安装或升级依赖。

## 仍开放

- T13 PARTIAL：真实 DeepSeek 已调用，诊断后端仍包含 OFFLINE_STUB/C0 结果；真实业务数值、完整语料集与实时撤权/故障矩阵未通过。
- T15：工程预演仅局部完成；模型产生的诊断结果不能直接在认可列表成板，且用户本人尚未签字。
- T16：现有 1 板、并发 1 的合成基线通过测量；正式目标数据与阈值尚未确定，不能推广至 131GB 归档库。
- T17：原生工作区/会话/模型/设置与竞争工具已补验；OS 目录选择器、原生工具拒绝/运行中撤权、全矩阵和 DESIGN 主题一致性仍开放。
- 旧 MCP：源码 `server.py` 仍同步串行，stdout/stderr 各截到 4096 个字符（常量名 BYTES 与实现并不相同）；截断响应 `isError=true/completeness=FAILED`。现有 `test_competition_api.py` 覆盖不把截断当完整结果。没有用真实库验证长结果分页或将旧 MCP 改成另一个运行时。
