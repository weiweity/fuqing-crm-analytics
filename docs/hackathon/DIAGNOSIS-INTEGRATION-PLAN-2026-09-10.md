# 诊断数值进入认可与看板：工程审查

基线：`8c2e676cf9a9c4baa62aef67aa08f44b12cb0e66`，工作树 `competition-diagnosis-integration`，分支 `codex/competition-diagnosis-integration`。这是[七阶段产品验收](PRODUCT-READINESS-2026-09-10.md)中诊断主线的实施计划，不替代其余六阶段。实施期保留 4325/18083 既有候选；独立检查后已通过原 supervisor 切换新插件，模型配置与状态仍在原位置，切换记录见本轮交付。

## Step 0：范围与复用

目标：由原生 DSH 工具调用得到实际计算的合成 GSV 本期/对比期数值；相同结果进入认可列表，认可后成板，刷新或重开仍读取同一份数值、条件和证据。模型只选择受控能力与条件，不生成可信 facts。

既有 C0 的冻结哈希保持 `97ee36833200b3a1626a4fa88e6b3bc9591bfb5f6bebc5e666aeabdcce13815a`。扩展采用独立版本，不能改掉旧 goldens 来接受新结构。超过 8 个文件的主要原因是合同、生成物和三层调用方必须同步；不增加第二个 Agent Loop、调度器或通用多态框架。

### What already exists

| 子问题 | 已有实现 | 处理 |
|---|---|---|
| 计算与条件 | `metrics/competition_compute.py`、`semantic/time.py`、`competition_diagnosis/condition.py` | 复用真实计算、比较窗口和条件继承，删除运行时读取测试文件的副作用 |
| 模型与权限 | DSH 原生 loop、`competition-agent/tools.mjs`、`DiagnosisAdapter`、身份 registry | 复用单循环、会话绑定和受控工具列表；执行前及持久化前核对当前权限 |
| 保存分析 | `SavedAnalysisRecord`、`first_purchase/asset_state.py` | 复用记录外形、SQLite 短事务与私有目录校验；增加独立诊断快照类型，不伪装为 ChannelFollowup |
| 成板与编辑 | `CompetitionAssetService` | 复用认可、批次、版本、幂等、取消、撤销；增加有明确 family 的受信来源分派 |
| UI | `competition-board/BoardWorkbench.tsx`、decode、transport | 保留现有交互，增加新结果解码和真实数字表格，不重画界面 |
| 生成与验证 | 离线合同生成器、B0 pipeline、bounded pytest | 新合同进入同一构建检查，不启动旧 CRM 生成类型 |

### NOT in scope（本接线增量）

- 真实 DuckDB/业务数据：目标和锁兼容仍待确认，本增量仅使用显式创建的小型 synthetic 快照。
- 改写 C0、ChannelFollowup、FirstPurchase 的既有事实合同：会破坏旧资产来源语义；用新结果版本和受控来源分派。
- 新模型、第二运行时、队列或 RunStore 的模型完成协议：这是现有模型调用的确定性工具计算，不声称整次模型运行或完整诊断链已成功。
- 未核清派样渠道全集、会员历史与默认业务枚举：保留 UNKNOWN 和显式输入要求，不自行补默认值。
- 本计划完成不自动等于 T13/T15/T16、视觉验收或正式发布通过。其余七阶段工作继续按原清单执行。

## 1. Architecture review

1. **[P1，置信度 10/10] 新 GSV 事实不能装进 C0 旧结果引用。** `backend/contracts/competition_c0.py:536` 的 `facts_schema_ref: Literal[...]` 只列出既有 family/空态，未定义实际 GSV 双期事实；`CompetitionResultRef` 同时固定 `competition-result/v1`。建议新增 `competition-computed-result/v1` 及其 facts 合同，由客户端与 HTTP 显式按版本分派。拒绝未知版本和其他 family 冒充，保留 C0 原始验证器。

2. **[P1，置信度 10/10] 当前诊断与保存入口断开。** `competition_diagnosis/orchestrator.py:207` 是 `result = fixture_result(capability_id, parsed, cap.support_status)`；`analytics_competition_app.py:188` 的列表来自 `store.list(actor)`；`cockpit_source.py:103` 又限定 `query.get("query_id") != QUERY_ID`。因此只把 fixture result ID 塞进列表不能完成可信闭环。建议服务器计算后保存不可变诊断快照，列表、认可和看板从同一快照解析，严格核对 owner、版本、run/result ID、条件 hash、事实 digest。

采用项目已存在的独立资产模式：一个诊断结果存储类，复用私有 SQLite 初始化/事务工具；一个明确来源适配层连接诊断与现有 channel 保存分析。来源选择按版本或 query family 显式分派，不能用“先尝试 A，异常就试 B”的方式吞掉权限或损坏错误。原 ChannelFollowup 存储无需迁移。

`run_id` 在新合同中明确标记为 `TOOL_COMPUTATION` 的执行标识，不等同于原生模型会话 SUCCEEDED。不要复制 `jobs.py` 的模型调度状态机。工具数值计算完成与整条诊断链完成分开。

```text
DSH 原生会话
  -> 已注册 step 工具（宿主 session_id，显式/继承 Condition）
  -> FastAPI 当前身份 + 条件解析 + 能力检查
  -> 显式注入的只读 synthetic 快照
  -> A2 本期/对比期计算 -> 新 facts 合同验证
  -> 当前权限复核 -> SQLite 原子保存事实 + 条件 + digest
  -> computed result 引用 + 数值返回模型
                         |
GET /results <----------+ 只列本人可读的持久化结果
  -> 人工认可 -> 原 batch/幂等/版本链
  -> 看板保存引用 -> GET 重开从快照读 facts，不重算
```

失败处理：数据快照不匹配、权限变更、取消、计算错误和存储失败均不能进入 COMPLETE 可认可列表；不可变结果保存成功但响应丢失时，相同执行键重读同一份结果。业务层不接受客户端 facts。

## 2. Code quality review

3. **[P1，置信度 10/10，已修复] 计算模块暗中补入测试数据。** 基线 `competition_compute.py:131` 遍历 `sys.modules.values()`，随后从 `FIXTURES` 找 JSON 并 `CREATE TABLE refunds`。本轮回归实证：同一数据库，仅加载无关夹具模块即从 GSV 100 变成 73；只读连接报错。已移除这条路径；A9 seeder 显式写入 refunds，并保留退款发生前的有效订单状态，原有期末金标准数值不变。

4. **[P2，置信度 10/10] 完成状态和投影必须一起收紧。** `orchestrator.py:324` 将 `item.completeness in {"COMPLETE", "PARTIAL"}` 都视作成功步骤；现阶段被 UNSUPPORTED 阻挡，但新能力接通后不能继续这样计数。`competition_assets/result.py:49` 起固定回显 2026-08 的日期和派样模式，不能用来投影新计算结果。新适配需读取冻结 metadata，且整链仅从满足当前条件的 COMPLETE 步骤计算。尚未执行的能力保持 PARTIAL/UNSUPPORTED。

新事实建议包含：query/version、execution kind、数据快照 ID/digest、实际执行的两期范围和截数、GSV 本期/对比期/差额、同比 raw ratio 或空值原因、当前实际订单数、限制。倍率在格式化边界转换，零分母显式为空值，不能借用旧 `safe_ratio` 的非零除零默认 0。

数据提供者负责创建小型合成快照，计算函数只读取调用方传入的连接。新数据集独立于 A9 验收 JSON；不能把重新命名测试文件当成消除夹具依赖。请求不能指定任意路径、SQL 或 actor；未知快照/as_of/rule_version 返回可解释错误，不静默改写。

## 3. Test review

既有测试框架是 pytest + Node/编译后 DOM；完整检查仍以 `docs/operating/verification.md` 和共享 pipeline 为准。下图保留实施前的 GAP 清单；当前完成层级见 Implementation Tasks 和本轮交付。未执行的原生取消仍为 GAP。

```text
代码分支                                     用户流程
计算只依赖注入数据库
  + [已测] 无退款表、有退款表                  同问题不随测试导入改变数字
  + [已测] 全新子进程、有/无夹具模块            + [已测] 修复前 2 FAIL -> 修复后通过
  + [已测] 只读/读写连接、数据库内容不变
  + [已测] 部分/全额退款前后时间点
新结果合同 [GAP]
  + 两期、三种比较、日期/范围冲突               + [E2E GAP] 原生诊断 -> 认可 -> 成板
  + 零分母、0 金额、空期、UNKNOWN              + [E2E GAP] 刷新/重开仍为同一数值
  + 外族/未知字段/NaN/无 digest 拒绝
保存与来源 [GAP]
  + 当前权限、owner、digest/版本损坏拒绝        + [E2E GAP] 断线重试不重复结果/看板
  + 同键同载荷重读、异载荷冲突                 + [E2E GAP] 撤权后不可读/不可成板
  + 落盘后新进程、SQLite busy、安全错误        + [E2E GAP] 旧板仍可读取/编辑
Adapter/HTTP [GAP]
  + 继承、变更条件后失效、取消/执行失败          + [EVAL GAP] 真模型引用数值与证据一致
  + 未完成步骤不计整链 COMPLETE                + [EVAL GAP] 不从 UNKNOWN 推断业务结论
```

必须增加的测试：

- `test_competition_computed_results.py`：独立手算小库，两期和全部范围/派样组合，结果 hash 随输入改变，零分母为空值；伪造时间/快照拒绝。
- `test_competition_diagnosis_store.py`：子进程退出后新连接重读；同键重试、异载荷冲突；其他 actor 隐藏；读/保存撤权；文件或 payload 损坏、SQLite 写锁均不假成功。
- `test_competition_http_wiring.py`：真实计算 -> results -> endorse/batch -> 重建 app -> GET board，比较 facts/条件/digest；失败注入和旧 channel 资产兼容。
- Node 解码与编译后 DOM：版本分派、坏数值拒绝、结果真实数值展示、成板后重开、重试不重复和弹层保持。
- 新增有界真实 DeepSeek T13：相同金标准问题与一个改写/条件变更问题，核对实际工具输出和最终回答的数值引用。既有已花费调用不重复当作新路径证据。

## 4. Performance review

5. **[P2，置信度 9/10] 新接线只适用于受界定的小型合成源。** `refunds_as_of()` 用 `fetchall()` 汇总退款，`iter_effective_orders()` 物化订单；`GET /results` 为每条保存记录再调用一次 get。当前单用户小库可以建立实测基线，但不能外推 131 GB 归档库。新提供者显式限制数据规模；新结果列表分页/有界读取、批量读取 metadata，避免新增逐条连接。SQL 计算完成后才进入 SQLite 短写事务，不在事务里调用模型或扫描 DuckDB。

短事务仍须覆盖写竞争：`BEGIN IMMEDIATE` 可能返回 SQLITE_BUSY，不能把事务开始当作保证成功；沿现有错误转换与原幂等键重试。[SQLite 官方事务说明](https://www.sqlite.org/lang_transaction.html)。类型分派沿 Pydantic 的 discriminator/明确版本选择，避免宽松 Union 错配 family；具体以仓库锁定版本回归为准。[Pydantic 联合类型说明](https://pydantic.dev/docs/validation/latest/concepts/unions/)。

## Implementation Tasks

- [x] **D1 / P1：计算隔离修复**。删除运行时测试发现；显式 seed refunds；添加全新子进程和只读连接负测。完整日常合成后端 2287 passed / 77 skipped，Ruff PASS，见[绑定源文件的验证记录](evidence/diagnosis-integration-2026-09-10/computation-isolation-verification.json)。
- [x] **D2 / P1：独立计算合同与显式数据提供者**。复用 A2 计算，增加新 facts/result 版本、受控时间/范围校验和离线生成物。验证独立手算、合同拒绝和 C0 hash 不变。
- [x] **D3 / P1：快照保存与来源适配**。复用 SQLite helper/记录协议；只从服务器计算结果保存，接入 results/认可/成板/重开。验证 owner、幂等、撤权、错误和新进程落盘。
- [x] **D4 / P1：诊断和 UI 接线**。显式注入执行器；整链状态按实际完成条件计算；新旧结果分派；展示真实数值和限制。验证既有窗口继承和编译后 DOM。
- [ ] **D5 / P1：独立复现和运行时切换准备**。完整 backend/B0 检查、浏览器闭环、有界真模型 eval；新状态备份/恢复；通过后再将候选交给用户验收并更新七阶段证据。

顺序实施，无独立并行 Agent 工作流：D1 -> D2 -> D3 -> D4 -> D5。每一步依赖前一步合同或来源完整性；共享 analytics 和插件模块，不为并行而重复修改。预计实现会触及超过 8 个文件，采用按增量评审，避免一次重写既有保存分析与 RunStore。

## 审查结果与开放条件

Step 0 范围沿既有目标；架构 2 项、代码质量 2 项（其中 1 项已修复）、性能 1 项；测试图已列出新路径缺口。外部模型/独立代理审查未运行，不将本次单 Agent 工程审查写成多模型通过。D2–D4 的实现与验证见[本轮交付](DIAGNOSIS-INTEGRATION-DELIVERY-2026-09-10.md)；D5 仍属于当前诊断闭环。

业务默认值、T16 数据目标/阈值和用户本人 T15 结论沿原问题等待答复，不重新提问；它们不阻止上述显式条件、小型合成源的实现。总体七阶段仍进行中。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---|---|---|
| Eng Review | `/plan-eng-review` | GSV 诊断进入保存与成板 | 1 | D1–D4 IMPLEMENTED | 五项已落实为代码及受限合成验证；原生取消与正式发布条件仍开放 |
| Outside voice | 未运行 | 本次未采用独立代理工作流 | 0 | NOT_RUN | 无跨模型结论 |

**VERDICT:** 数值合同、保存、HTTP 与 UI 已实现；完整后端/B0、两个有界真实模型问题及结果成板重开通过。D5 仍保留原生取消不发布的验收缺口，不能据此宣称正式发布或整产品完成。

**UNRESOLVED DECISIONS:**
- 业务默认值与 T16 数据目标/阈值沿既有异步问题待答复；用户本人 T15 仍待验收。均不影响显式条件、小型合成源的 D2–D5 实施。
