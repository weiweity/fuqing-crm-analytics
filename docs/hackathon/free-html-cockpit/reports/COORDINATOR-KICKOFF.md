# 主协调启动快照 · 2026-09-18

- 状态：KICKOFF（六路尚未施工；P12/P13 未运行）
- 执行者：主协调 Agent
- 主仓：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics`
- 基线：`main` @ `b45a27bb9022057ce37aa9123927e8b4663a2720`
- approved-plan SHA256：`47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb`（文件字节核验一致）
- 施工包：未跟踪；`implementation_status=NOT_STARTED`；六份 `LANE-*.md` 当时尚未落地
- 现役 6677：`127.0.0.1:6677` PID **8758**，本轮未触碰

本文件是给 Lane A–F 的架构/接口/范围裁定，不是实现通过证据。破坏性差异一律 BLOCKED，交给 P12。

## 核验过的事实

| 项 | 实测 |
|---|---|
| 六 worktree | A–F 均存在，分支 `codex/free-html/lane-{a-f}`，HEAD 同基线，无 upstream |
| dirty | 仅未跟踪 `AI-PROMPT.md`、`MAIN-COORDINATOR.md`、施工包；无业务代码 diff |
| `src/free-page/` | 六个 worktree 当时还没有该目录 |
| 工具链 | Node v24.19.0、Python 3.14.4、DSH `0.1.6-alpha.2` / `ddefc45f`。宿主 pnpm **11.19.0**，toolchain 钉 **11.7.0**：不要为对齐去升级或降级 |
| PACKET-CHECK | 历史交接检查。当前 `README.md` 与 `manifest.json` 哈希已变（并行编排后刷新），不能当实现证据 |
| 主仓 dirty | `STATUS.md` 本地 +8 行；`HANDOVER-CODEX.md` 未跟踪。lane 不得改这两处 |
| 报告 | `reports/` 仅 README；P01–P13、LANE-A–F 均未写 |

## 现在可以做什么

1. **立即开工：Lane A 与 Lane B**（无批次依赖；B 的 P04 DONE 仍要求本 lane 先有 P01 浏览器证据）。
2. **允许并行脚手架：C/D/E/F**，必须消费本目录 `fixtures/` 与 A 落地后的合同；其 DONE 仍受 manifest 依赖约束。
3. **禁止**：push/merge、切 6677、读 131GB DuckDB、改 DSH 上游、写凭据、`pnpm add`、把 BoardSpec 目录当生成白名单、多 lane 同时改 `manifest.json`。
4. **manifest**：只由主协调更新。各 lane 写 `reports/LANE-*.md`，不要写 `P01.md`–`P11.md`，也不要改批次 status。

## 路径裁定（顺序提示词 vs PARALLEL-6）

顺序批次提示词把 `src/free-page/` 写进多个 owner；并行方案禁止跨 lane 改运行时。以下目录是本轮冻结边界。目录均相对 `dsh-plugins/analytics-workbench/`，backend 相对仓库根。

| 路径 | Owner | 允许 | 禁止 |
|---|---|---|---|
| `backend/contracts/page_*.py`、`analytics-page*.openapi.json`、离线合同入口 | A | 独立 HTML 资产/桥/错误 Schema | 把字段塞进 `board_spec.py` |
| `backend/services/analytics/page_documents*.py`、对应 route/test | A | 权限/CAS/幂等/回滚存储 | 改 `board_documents.py` 的 BoardSpec codec |
| `src/free-page/contract/` | A | 类型、fixture、契约单测 | iframe/MessageChannel/缓存实现 |
| `src/free-page/runtime/`、`resource/`、`preview/` | B | 沙箱、资源清单/缓存、预览宿主 | backend 资产表；`src/client/library-*` |
| `backend/services/analytics/page_result_access*.py` | C | 只读授权读取 | 改 A 的 page_documents 存储 |
| `src/free-page/bridge/` | C | 桥实现与负测 | SQL/token/页面保存 API |
| `src/free-page/source-index/`、`patch/`、`edit/` | D | 定位、补丁、D48 守卫 | `library-board-client.mjs`、宿主 UI |
| `src/client/` 资料库/工作区/composition/competition-shell | E | 页面、主题、浏览/编辑可见模式 | `leave/`、`navigation/`、D 的编辑实现 |
| `src/client/leave/`、`navigation/`、host adapter | F | 离开协调、epoch、脏稿谓词 | E 的 UI 组件；DSH 上游 |
| `src/board-spec/html-sandbox.mjs` | 无人改 | 旧静态禁脚本合同保持 | 扩展成自由页运行时（D13） |
| `.context/dsh-b0/upstream/` | 无人改 | — | 改 DSH 源码 |

需要改别人的文件：停笔，写入该 lane 报告的 **integration notes**。

## 不得发明第二套的东西

- Agent / 聊天：只用原生 DSH。N10 接现有 session，不新建 Router 或第二 loop。
- 主题：只映射 `src/client/competition-shell/tokens.ts` + ThemeProvider。D37 默认 Noto Sans SC；PuHuiTi 未完成授权前不是已生效默认。
- 状态机：复用 `board_documents.py` 的 actor/owner、preview/confirm、CAS、幂等、回执不明；HTML 用独立 codec。
- 绑定状态：只有 `UNBOUND_SAMPLE` / `BOUND_VERIFIED` / `BOUND_STALE`。
- 提交路径：D6 = 补丁预览确认；D9 = 本地草稿显式保存。同一次确认不得创建两个版本。退出编辑、关面板、取消选区 ≠ 保存。
- 生成上限：自由 HTML/CSS/JavaScript。DESIGN.md/skill、BoardSpec、组件目录、参考图都不是白名单。

## D6 / D9 最小合同

沿用现有 preview 状态 `PENDING | APPLIED | CANCELLED`，页面操作集：

`GENERATE | PATCH | SAVE | ROLLBACK`

- `GENERATE`：`base_version === 0`；失败保留输入，不制造已保存资产。
- `PATCH`：D6。必须先有有效 preview；确认用原幂等键。
- `SAVE`：D9。宿主内存草稿的显式保存，不经过“把退出编辑当成保存”。
- `ROLLBACK`：目标版本的源码+manifest 原子恢复，然后重查当前授权。

公共字段（与现有看板同语义，新资产新 id）：`page_id`、`session_id`、`version`（int ≥ 1）、`base_version`、`idempotency_key`、`preview_id`、`expires_at_ms`。身份字符集沿用 `boardIdentity`：`^[A-Za-z0-9_.:-]{1,128}$`。

错误码先复用再扩展，不要换一套 HTTP 语义：

| code | HTTP | 何时 |
|---|---|---|
| `VERSION_CONFLICT` | 409 | CAS 失败，旧版本未覆盖 |
| `NOT_FOUND` | 404 | 资产对当前 actor 不可见 |
| `FORBIDDEN` | 403 | 缺 capability / 跨 owner |
| `PREVIEW_EXPIRED` / `PREVIEW_CANCELLED` | 409 | 不能 confirm |
| `IDEMPOTENCY_CONFLICT` | 409 | 同键用于另一草稿 |
| `RECEIPT_UNCERTAIN` | 客户端 | 丢回执；保留草稿，用原键核对 |
| `INVALID_PAGE` | 422 | 包/字段非法；**不要**用 `INVALID_BOARD` |
| `RESULT_UNAVAILABLE` / `RESULT_STALE` / `RESULT_REVOKED` | 409/403 | 数据桥 |
| `MAPPING_STALE` | 409 | D48 定位失效，必须重选 |
| `SCOPE_REQUIRES_CONFIRMATION` | 409 | 共享 CSS/JS 扩大影响，未确认不得提交 |

## D48 不得默许

1. 静态元素 + 有效 `data-shine-node` 映射 → 精确源码范围。
2. 动态图表/Canvas + 可靠所属区域 → 明示区域范围，不是猜 DOM。
3. 映射失效/伪造/过期 → 保留源码和草稿，提示重选；**禁止**静默改成整页。
4. 整页范围只有用户主动切换。
5. 共享 CSS/JS 实际扩大时，补丁预览必须显示扩展范围，等待对应确认。
6. 取消/过期/失败不写有效版本；不能用整页重生成救场。

Lane D DONE 用确定性 fixture 覆盖 1–6。三类真实 AI 样本是 P13，不是 D 的完成条件。

## 各 lane 最小建议

### Lane A · P02/P03 · T1/T2 · N07/N11/N12/N13/N05/N14

先冻结 `free-page/v1` 源码包、binding manifest、桥消息；再抽公共状态做 `page_documents`。复用 `BoardDocumentStore` 的 preview/confirm/CAS，**新 SQLite 文件、新 application_id、独立 codec**。离线生成学 `scripts/dsh-b0/competition-c0-contract.mjs` / `cockpit-contract.mjs`，不启动旧 CRM。测试：`backend/tests/test_page_documents.py` 必须含新连接、进程重开、双击幂等、CAS 冲突、跨 actor、旧 BoardSpec 回归。交付 `src/free-page/contract/` fixture，供 B–F 引用。

### Lane B · P01/P04 · T0/T3/T4 · N07/N09/N15

先做隔离夹具，再用合成失控页证明：宿主可操作、单页可关/重启、已保存版本可恢复。没有这三项浏览器证据，P04 只能 PARTIAL/BLOCKED，不能把 `sandbox` 属性写成 CPU 隔离。不要改 `html-sandbox.mjs` 去 `allow-scripts`。资源必须走显式清单 + hash；外联负测要打真实网络出口，不只 mock `fetch`。预览容器放 `src/free-page/preview/`，E 来挂载。

### Lane C · P05 · T5 · N06/N07/N12

只读 `result_ref` / `data_ref`。新查询仍走原生 Agent。禁止页面 SQL、token、直接保存。每次缓存命中仍核验 actor/单位/时间/版本/撤权。未绑定页必须仍能打开。消费 A 的 bridge contract fixture；A 未落地前用 `fixtures/frozen-contract-v0.json`。

### Lane D · P06/T29 · N08–N11/N13

只在 `source-index` / `patch` / `edit`。宿主 UI 由 E 接 `edit` 公开 adapter。D 的 DONE 不含真实模型。补丁确认走 D6，本地保存走 D9；取消/关面板不保存。fixture：`fixtures/d48-scope.fixture.json`。

### Lane E · P07–P10 · T7/T10–T20 · N01–N11/N16

资料库首页锚点是自然语言输入（D34），不是空卡片墙。必须保留原生聊天入口（N01/N10）。浏览默认把点击交给页面；显式编辑才出选区浮层。状态脊不可隐藏示例/绑定/过期（D32）。主题只做 competition-shell 映射。窄屏与对比度可先用 mock adapter，但 DONE 仍等 C/D 真实 adapter 或 P12 接缝。不要实现离开三选——那是 F。

### Lane F · P11 · T21–T28 · N01/N02/N06/N13/N14/N16

`hasUnsavedChanges` ≠ `hasActiveEditContext`（D42）。现有 `library-workspace.tsx` 把干净 `editContext` 当离开理由，**不要复制这个谓词**。单一 coordinator；保存成功且回执匹配才原导航一次；失败/冲突/未知留页。迟到 get/list/preview 按 epoch 丢弃；保存回执按幂等/CAS 核对，不当普通读取丢弃。真实 DSH 宿主接缝可 PARTIAL，记入 P12。

## 脚手架期允许的 mock

C/D/E/F 可 mock 对方内部实现，但必须声明 mock 清单。禁止复制另一 lane 源码。合同字段以 approved-plan 与 A 冻结合同为准；本目录 `fixtures/frozen-contract-v0.json` 是开工夹具，A 落地后以 A 的生成类型替换。

## P12 集成清单（尚未执行）

等六份 LANE 报告 + 真实 diff 后再做。预列：

1. 越界路径审查（上表）。
2. 按 A→B→C→D→E→F 移植，冲突不让 lane 互相 cherry-pick。
3. 真浏览器：生成 → 未绑定预览 → 绑定 → 选区 → 局部补丁 → D6 确认 / D9 保存 → 重开 / 回滚。
4. iframe + MessageChannel 握手、刷新旧端口、外联负测。
5. 全局离开：干净选区不拦、脏稿三选、epoch、晚到回执。
6. 把 `src/free-page` 测试纳入 `scripts/dsh-b0/pipeline.mjs` 实际扫描。
7. 旧 `html-sandbox` 禁脚本测试仍绿。

P13 仍未授权运行真实模型；三个样本、有无 DESIGN.md、D48 矩阵、375/768/1440、读屏/键盘/200%/reduced-motion 全部 NOT_RUN。

## 剩余风险

- 施工包未进 Git；重建 worktree 必须重新复制本目录。
- B 的 T0 失败则 D20 运行时实现不能冻结。
- 现有 library 离开谓词与 D42 不一致，P12 接 E/F 时必改。
- 6677 现役与本施工隔离；官方 `reload` 会编原仓插件，不要用。
