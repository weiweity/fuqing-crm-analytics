# 金额单位来源修复

本地代码与回归已完成；运行候选仍为 4325 的 `6202e89` 和原 18083 API。本修复尚未切换运行实例，真实 DeepSeek 复测、浏览器视觉和新一轮五库备份恢复均未执行；完整 T13/T15/T16/T17 与产品仍 PARTIAL。

## 问题与行为

重新读取 A3/B2 各自绑定的原生工具日志后，确认能力目录没有 currency/amount_unit。模型将金额称为 CNY/minor，没有工具依据。此前“措辞不一致”的判断不足，现明确更正；原回答、原报告和原始失败证据均保留。[原生审计](evidence/computed-units-2026-09-10/native-unit-source-audit.json)包含对应日志哈希和实际 source_context。

源现在可显式声明金额单位；当前 demo 没有声明，保持 UNKNOWN，不补成人民币。新计算生成 `competition-gsv-facts/v2`，将 money_unit 纳入原 evidence_digest；篡改单位与金额一样会被拒绝。旧 v1 模型和摘要原样保留。结果信封按事实版本严格核对两个 schema 引用。

HTTP 能力目录和计算结果从同一 source 取得单位。SQLite 保存、认可成板、重开和表格/图形都保留该事实；旧结果显示“未记录”，新未声明结果显示“未知”，显式合成夹具分别显示人民币元或分。金额保留原始数值，只有 raw ratio 转为百分比展示。生成的 OpenAPI/TypeScript 与方法包已同步，冻结 C0 不变。

方法要求模型引用本次事实的单位和合同，准确说明 analysis_persisted=true 的自动保存；这些提示词变更仍需真实模型复测，不能仅凭代码认定输出已修好。

## 验证

| 检查 | 实际结果 |
|---|---|
| 后端完整日常合成 profile | 2339 passed / 77 skipped / 71 deselected，10 组退出码均为 0 |
| 受影响后端 | 47 passed：源、合同、摘要、持久化、新进程、HTTP 成板重开和取消 |
| B0 pipeline | PASS：离线合同、480 Python tests、源测试、host/client 类型检查、编译后 DOM 和干净重建 |
| 新旧单位解码 | 5 passed；非法单位、未提供 money_unit 或版本不匹配的 v2 在 HTTP 边界拒绝 |
| 编译后 DOM | 旧 v1、UNKNOWN、major、minor × TABLE/BAR/LINE/METRIC/EVIDENCE，保存偏好后重开，金额和比例保持 |
| 实际跨版本读者 | 新读者读取旧 v1 和新 v2；旧读者读取 v2 返回 409；原 v1 JSON/摘要及无单位源 data_digest 不变 |
| 静态与提交前审查 | Ruff、diff check 通过；[审查记录](evidence/computed-units-2026-09-10/REVIEW.md) |

[完整证据](evidence/computed-units-2026-09-10/verification.json)及 [源码哈希](evidence/computed-units-2026-09-10/source-manifest.json)绑定基线 `24a3722` 之上的补丁。上一提交 `24a3722` 的 [CI 34439092941](https://github.com/weiweity/fuqing-crm-analytics/actions/runs/34439092941) SUCCESS 不替代本次提交的远端检查。

两次新增测试失败来自测试预期未使用既有 publication-time 精确规范格式；应用时间规则没有改变。修正测试后通过，失败日志保留。Linux spill 配额偶发失败仍未归因，本次通过不代表根因修复。

## 候选切换与回退门槛

旧读者不能读取新 v2，即使 SQLite metadata 仍是 1。切换前更新五库备份，在独立恢复目录核对全部现有板、草稿和 8 条结果；不能把旧历史备份当成本次备份。升级后的状态留存，回退以旧代码读取对应旧快照，禁止用旧程序直接接管含 v2 的目录。

通过上述检查及本次远端 CI 后，再准备环境绑定的插件、切换本轮 4325/18083、验证新旧资产和未知单位展示，并执行有界真实 DeepSeek 复测。用户业务口、归档大库和模型凭据保持原状；本地验收不代表公网发布或本人 T15 签字。
