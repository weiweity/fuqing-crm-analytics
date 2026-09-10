# 计算结果的单位与来源边界

## 问题与工程范围

基线 `24a3722`。A3/B2 真实回答声称能力目录提供 CNY/minor，但本轮重新读取各自原生 `competition_growth_capabilities` 返回，目录的 `source_context` 没有 currency/amount_unit。此前将它归为措辞不一致不够准确：这是未经工具支持的金额单位推断。旧原始回答保留，当前结论在此纠正。

`CompetitionGsvFacts` 只有 metric/current/comparison/difference/change_ratio；`SyntheticDiagnosisSource` 同样没有币种单位字段。现有摘要已经包含 facts，适合绑定单位，不需要另造证据服务。直接改变 v1 的默认序列化会使旧摘要失配，所以保留 v1 原模型，增加明确的 v2 分派。

本修正覆盖源声明→计算事实→摘要校验→SQLite/HTTP→看板和模型；沿用现有入口、解析器、生成器、预算和权限。跨越八个以上文件是合同与调用方同步的必要范围；只增加单位模型和 v2 事实模型，不增加运行时、状态表或依赖。仅改模型提示词无法让图表/HTTP同时获得可核验单位。

## 架构与兼容性

```text
显式 synthetic payload（可缺单位）
  → 校验单位声明：KNOWN + CNY + major/minor，或 UNKNOWN + null/null
  → facts/v2.money_unit → evidence_digest（单位在摘要内）
  → 原 SQLite result_json → 原 HTTP/工具 → v1/v2 分派 → 同一表格/图形
旧 facts/v1 → 原摘要原样校验 → 单位未记录，不补造历史声明
```

当前 demo 没有定义币种单位，保持 UNKNOWN；不以新字段把历史数值重解释成人民币。独立合成金标准会显式声明 CNY major/minor，验证已知路径。单位或币种只有一半、非法枚举、UNKNOWN 携带币种均拒绝。金额不做隐式倍率转换，图表/表格注明对应原始单位，比例始终是计算合同的 raw ratio。

新增 v2 事实携带单位对象；结果信封继续按事实版本严格匹配 facts_schema_ref/existing_result_schema。老 v1 的 JSON 与 evidence_digest 不变，新读者能读取旧行。旧 `6202e89` 读者不能识别 v2，必须实测为明确不兼容，不假称可直接降级。切换用户候选前需通过 SQLite backup 留存旧状态并验证恢复，保留当前新状态；回退使用隔离旧快照和旧插件，不能覆盖写有新结果的目录。未完成该检查前不切换 4325/18083。

## 代码质量与故障路径

- 单位状态在合同中定义，由 source 直接传递；不在模型/React分别设默认币种。未声明是 UNKNOWN，不是错误或人民币默认值。
- 复用 evidence_payload 和原存储鉴权/幂等路径。篡改单位须和篡改金额一样拒绝；旧证据不能因新增默认字段而失效。
- React 复用一个金额单位标签函数；选择结果、表格、BAR/LINE/METRIC 都使用相同事实。旧结果继续读，单位显示“未记录”。
- 模型只引用本次工具明确给出的单位/合同名；analysis_persisted=true 与未成板/未发送分开说明，不能声称没有发生任何持久化。

## 测试图

```text
source声明
 ├─ KNOWN major/minor → 计算原值/单位/比例不变
 ├─ 源未声明 → UNKNOWN；不从环境或其他目录取值
 └─ 半声明/非法币种/UNKNOWN带值 → 拒绝
facts/v1和v2
 ├─ 原v1字节与digest → 新解析器接受，旧记录不被改写
 ├─ v2单位变更/版本不匹配 → 拒绝
 └─ SQLite新连接/进程退出 → 单位与digest保持，HTTP认可成板仍引用同一结果
React
 ├─ v1/v2解码、非法v2拒绝
 └─ KNOWN/UNKNOWN/旧未记录 → 表格+三种图形可读；raw金额不乘除100
发布
 └─ 旧读者读v2拒绝 → 隔离备份恢复旧资产 → 才能切候选
真实模型
 └─ 新方法包和实际单位字段被读取 → 不编造currency/minor，准确说明自动持久化
```

既有 pytest、Node 编译后 DOM、完整 B0 与共享后端矩阵执行，不引入新测试框架。新生成合同使用 competition-computed-contract.mjs，冻结 C0 不变。旧读者测试运行固定旧合同源码，使用隔离小结果而非真实库。

## 性能与验收

单位为每结果一个有界对象，不增加查询次数、网络轮次、行数或数据库复制。只增加原有规范化 JSON 的几个字段；仍按原 bounded worker/HTTP 预算。性能数据不代替正式 T16。首次先完成本地合同/存储/渲染回归与旧读者兼容性证明，再准备候选备份、切换及真实复测；不把源代码修改等同于 T13/T17 通过。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---|---|---|
| Eng Review | plan-eng-review | 单位证据和兼容性 | 1 | 实施计划就绪 | 源无单位、摘要回归与旧读者拒绝均已纳入验证；不增加服务/状态表 |
| Design Review | DESIGN + 现有视图检查 | 图表与表格同源单位 | 1 | 实施前范围检查 | 沿用既有组件与品牌；实际视觉验收仍待执行 |

**VERDICT:** 实施计划覆盖架构、代码质量、测试与性能；本地修正可继续。完整业务默认值与 T15/T16 的既有待确认项不由本计划决定。跨模型评审未执行，不冒充独立意见。

NO UNRESOLVED DECISIONS
