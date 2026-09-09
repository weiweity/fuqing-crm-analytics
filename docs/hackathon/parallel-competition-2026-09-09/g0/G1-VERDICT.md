# G1 合同验收（总控）

状态：`C0_FROZEN / ACCEPTED_WITH_GAPS`。
contract_hash：`97ee36833200b3a1626a4fa88e6b3bc9591bfb5f6bebc5e666aeabdcce13815a`
base_sha：`71a65f06f87cb3a5cbd888372487b6b36faaf2a6`
plan_snapshot_hash：`53f472f11c0ddfdf2106dd71fabe3c22c475a639a93962e95795931be8fb2937`

## 核验

| 项 | 结果 |
|---|---|
| 独立复算 `stable_contract_hash` | 与 manifest 一致 |
| pytest `test_competition_c0.py` + `test_lint.py` | 30 passed（A1 日志） |
| 离线生成器 `--check` | A1 记录 exit 0 |
| 另造平行 analytics 模型 | 否；映射到现有 audience/cockpit/query 类型 |
| 成功/空/参数错/权限失败 fixture | 有；编辑另有 409/部分成功 |
| 待确认默认 | `sample_mode_when_excluding`、`board_layout_mode` 显式枚举 + pending |
| UNKNOWN 未伪装 | 派样全集、会员历史、旧 CRM F 粒度、自定义月初 cutoff |
| 未改 main.py / index.tsx / 锁 | 是；`schemas.py` 仅 re-export C0 类型 |

## 与 A2 CR 对齐

已覆盖：GSV 必填、timezone=Asia/Shanghai、sample_mode 三值、sales_scope/history_scope 分离、comparison_mode、as_of、闰日 clamp、metrics_contract_id。
嵌套：cutoff 在 ResolvedCondition 实际执行条件中回显，不在 InclusiveDateRange 顶栏。
会员：`MemberMark.UNKNOWN` / `member_history_status=UNKNOWN`，不是 Condition 顶层筛选字段——可接受，A2/A8 按交叉维实现。

## 仍开放（不阻断第二批编码）

- 能力 HTTP 目录 NOT_CONNECTED；FILTER_CHANGE NOT_CONNECTED
- 旧 audience_summary 自定义 cutoff=月初-1 与 C0 start-1 不兼容，A2 必须改计算/绑定，不得静默调用旧分支
- pipeline.mjs / pre_push_path_class.py 接线归总控，第二批不要改

第二批必须使用此 hash。禁止再发明字段；缺口走 CR → A1。
