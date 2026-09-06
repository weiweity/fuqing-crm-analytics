# B0 首个任务内核代码单元：实现与验证

日期：2026-09-06。状态：`KERNEL_UNIT_VERIFIED / DSH_NOT_CONNECTED / B0_PARTIAL`。这是当前本地未提交代码的验证记录，不是整分支、完整 B0 或发布通过报告。

后续执行已进入[DSH 原生接线与固定构建单元](./B0-DSH-KERNEL-INTEGRATION-2026-09-06.md)。本文保留首单元发生时的结果与未运行项；`DSH_NOT_CONNECTED` 不再代表后续代码现状。B0 整体仍为 PARTIAL。

## 1. 这次完成了什么

用户要求在既有方案审核无阻断项后进入下一步实施。本次 `/autoplan` 续接核对了 D1–D4 已确认及四节静态审核记录，没有重开 CEO/Design/Engineering/DX 全流程；随后实现前置到 B0 的第一个代码单元，并按 `/review` 的关键项、一般项两轮清单复核。历史独立模型与视觉降级不变；本次没有独立模型复核、子 agent 审查、PR/Greptile 审查或整分支 clean 认证。

| 本单元 | 实际落点与证据 |
|---|---|
| 版本化 B0 合同 | [analytics.py](../../backend/contracts/analytics.py)；仅 `analytics-run-b0/v1`，CHAT 任务、固定合成事实、错误与事件；通过 [schemas.py](../../backend/contracts/schemas.py) 导出 |
| 受理和恢复 | [jobs.py](../../backend/services/analytics/jobs.py)；具名 SQLite、WAL/FULL、短事务同时记录 run、请求 hash、dispatch intent、原 202 和幂等键；每次操作新连接 |
| 任务与预算账本 | 同一状态仓储执行队列/在途额度、唯一活动名额、截止时间、工具步数、保留与空间准入；UNKNOWN/CANCELLING 不释放名额，重启不生成新 attempt/requestId 或重置预算 |
| 隔离 HTTP app | [analytics_app.py](../../backend/analytics_app.py)；6 个真实路由定义，进程内 HTTP 测试；没有模块级 app、默认状态路径、CRM lifespan 或默认身份，未连接运行时默认拒绝新 run |
| 权限 | [access.py](../../backend/services/analytics/access.py)；显式本地 B0 不透明 token、actor 所有权、操作能力与合成范围；受理/重放/派发/工具/读流/结果提交重新检查当前权限 |
| 生成合同 | [OpenAPI](../../backend/contracts/analytics-run.openapi.json) → [TypeScript](../../dsh-plugins/analytics-workbench/src/run-contract.generated.d.ts)；离线生成、同源 hash、正反类型编译与逐字节漂移校验 |

入口路径细化：没有新建 `backend/routers/analytics.py`，因为导入 `backend.routers` 会运行其初始化并导入旧 CRM 路由。新路由直接放在独立 app factory 中；旧 `backend/main.py`、`backend/routers/__init__.py`、旧 BI 预算与数据库路径本次均未改动。新进程阻断旧配置/路由/数据库模块、SQLite 连接、网络与子进程的导入测试，证明离线生成不打开业务状态或真实库。

## 2. 已实现接口与使用边界

以下是可装配、已用 TestClient 验证的接口，不是当前有在线监听地址；没有运行 `start-stack` 或新 Web 服务。前缀为 `/api/v1/analytics`。

| 方法与路径 | 能力与控制头 |
|---|---|
| `POST /conversations` | 创建合成会话；`Idempotency-Key` |
| `GET /conversations/{id}` | 查看自己的会话及任务 ID |
| `POST /conversations/{id}/runs` | 当前身份/所有权校验后受理；`Idempotency-Key`；新请求还要求服务端显式运行时就绪 |
| `GET /runs/{id}` | 查看自己的权威快照；版本在 `ETag` 返回 |
| `POST /runs/{id}/cancel` | `Idempotency-Key` + `If-Match` 正整数字符串；排队任务直接取消，活动任务只进入取消中 |
| `GET /runs/{id}/events` | 有界 SSE 连接；按 `Last-Event-ID`/`after` 续读；游标冲突 422，过期 410 并返回快照地址 |

所有路由使用显式 `Authorization: Bearer ...` 本地 B0 身份，不能用 actor/role 请求头伪造身份。它不是飞书、SSO 或生产认证；重启后的身份装配由后续可信 adapter 负责。事件每次披露前再次检查权限与同一身份；连接断开不重新提交问题。

同一 actor/操作/目标/key 的相同规范化请求返回原响应；即使 run 已终态或运行时暂时离线，也能取回原 202；当前权限仍须有效。改 payload、父任务越域或旧版本取消分别拒绝。请求体上限 64 KiB，`question` 1–8000 字符；`condition_patch` 只允许缺省或 null，不会把未实现的业务筛选静默丢弃。版本化完整产品合同仍以[草案](./ANALYTICS-CONTRACTS-DRAFT.md)为待实现目标。

`claim_next()` 只在提交后交出派发意图，**不调用 DSH**。`observe()` 只接受可信适配器的四项关联标识与退出证据；不是公开 HTTP 接口，也不能反序列化模型声称“已退出”后直接调用。原生取消命令、进程/运行时退出确认和清理责任仍须由下一单元接好。测试中的受控子进程退出只是账本接缝证据，不是完整 DSH 停止链。

## 3. 本次冻结的本地小样资源输入

[B0ResourceProfile](../../backend/services/analytics/resource_profile.py) 是显式、严格校验、独立于旧 BI 环境变量的配置；状态中冻结完整配置/hash，打开已有状态时 profile 不匹配则拒绝，不隐式迁移。保留额度没有默认回退，下面小样值由调用者显式选择，不是生产容量承诺或删除策略。

| 参数 | 当前值与执行层 |
|---|---|
| 活动执行 / 排队 / 单 actor 在途 | 1 / 8 / 3；SQLite 事务及唯一活动名额约束执行；活动数包含 UNKNOWN/CANCELLING |
| 总任务 / 单查询 / 工具步骤 | 120 秒 / 30 秒 / 最多 8 步；持久化绝对截止/计数，迟到结果拒绝；实际中断仍待运行时 adapter |
| 派发尝试 | 配置上限 3；当前只实现首次 claim，次数持久化；没有自动重试循环，不据此声称重试策略已交付 |
| 结果 / 单事件 / 单 run 事件 | 1 MiB / 64 KiB / 4 MiB；写入前校验，事件留出终态空间；没有 token 流压缩/合并实现 |
| 状态准入高水位 | 256 MiB；统计 SQLite/WAL/SHM，计入每个非终态 run 的逻辑预留；这是准入保护，不是文件系统硬配额或真实磁盘耗尽验收 |
| 小样记录保留上限 | run 总数 40、每 actor 20；会话总数 20、每 actor 10；取消 key 每 run 16；超过则拒绝新记录，不删除证据或重放键 |
| DuckDB / temp / RSS | 512 MiB、2 线程 / 512 MiB / 1024 MiB 观测阈值；本单元只冻结输入，没有创建分析 worker、RSS/spill 强制执行或容量验收 |

状态目录必须显式存在、当前用户所有且权限 0700；拒绝目录/数据库/初始化锁的符号链接、数据库/锁硬链接和无关 SQLite。没有默认真实库路径、自动 pruning、ETL、SQL 查询工具或原数据迁移。合成结果仅为登记 fixture 的 100 名客户、25 名复购客户、`repeat_ratio=0.25`；不能当作完整指标金标准或模型答复能力。

## 4. 实际验证

环境：macOS，本仓现有 Homebrew Python 3.14.4 / pytest 9.0.3，Node 24.19.0，已安装 openapi-typescript 7.13.0 / TypeScript 6.0.3。未安装或升级依赖。测试明确跳过旧 CRM conftest，仅使用本单元自包含夹具，避免旧启动配置与数据库副作用；不是跳过新权限或持久化逻辑。

| 验证 | 本次结果 |
|---|---|
| Python 合同、HTTP/访问、落盘/进程故障、资源准入 | **100 passed**；4 个测试文件，单次约 2.9 秒；启用 ResourceWarning 失败检查后无连接泄漏警告 |
| Python scoped Ruff | **PASS**；仅本次新内核和测试，不对旧脏改动做全库 lint 承诺 |
| 现有 ground-truth-lint | **PASS**；比率另有固定值、数值类型和范围负向测试，不只依赖静态命名检查 |
| 离线 OpenAPI/TS 生成及 `--check` | **PASS**；正向接口类型及四个 `@ts-expect-error` 负例通过，固定比率常量同时进入 OpenAPI/TS；没有拉取远端 schema |
| DSH 原生 / 模型 / 新 UI / 全产品测试 / CI | **NOT RUN**；本次没有启动这些服务或执行这些验收 |

仍有 1 条现有依赖弃用警告：Starlette TestClient 提示将 httpx 迁往 httpx2；不影响本次断言，未为消除警告擅自变更依赖。测试夹具初次遗漏关闭 SQLite 连接的问题已修复并重跑。

代表证据：

- [test_analytics_jobs.py](../../backend/tests/test_analytics_jobs.py)：跨连接同 key 竞争；受理事务前/后真实 SIGKILL 与新连接恢复；独立协议接收方正/负对照及丢失回执；两种终态先后顺序和真实并发竞争；缺主结果不能成功；状态提交失败没有假终态。
- [test_analytics_access.py](../../backend/tests/test_analytics_access.py)：跨 actor/父任务隔离；受理、重放、派发、流式披露和最终提交的当前权限；撤权后继续占额，确认退出后失败且无成功结果。
- [test_analytics_run_contracts.py](../../backend/tests/test_analytics_run_contracts.py)：6 路由、原 202 离线重放、取消版本、429、SSE 顺序/重连/410、错误不回显输入、禁止身份/SQL/未来版本字段及独立进程离线导入。
- [test_analytics_run_resources.py](../../backend/tests/test_analytics_run_resources.py)：严格配置、私有状态路径、全局/个人/保留/空间额度、8 步上限、真实进程退出后原预算/截止/关联 ID 保持不变、超时持额与事件空间回滚。

复现（本工作树根目录；没有应用启动）：

```bash
PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 /Users/hutou/homebrew/bin/python3.14 -m pytest --noconftest backend/tests/test_analytics_jobs.py backend/tests/test_analytics_access.py backend/tests/test_analytics_run_contracts.py backend/tests/test_analytics_run_resources.py -q -o addopts='' -W error::ResourceWarning
/Users/hutou/homebrew/opt/node@24/bin/node scripts/dsh-b0/run-kernel-contract.mjs --check --python /Users/hutou/homebrew/bin/python3.14
```

生成脚本用显式 Python 路径；`--write` 只重建两份生成合同，`--check` 只比较与编译。当前 OpenAPI SHA-256（不含其自描述 hash 字段）为 `5d93c3aabf362865e8f24e28c96a8d1f75717c80370f31734407d85b128b9679`。不要运行旧 `gen:types` 去连接完整 CRM 服务以生成本单元类型。

## 5. 局部复核结论与下一单元

本单元两轮复核完成，未发现剩余阻断本地单元交付的问题；SQL 参数、事务/CAS、四项运行关联、结果类型、状态枚举消费、异步 SSE/同步状态隔离与源合同生成均检查。过程中修正了离线时原 202 被挡、流式读后撤权仍可能披露、撤权诊断丢失及测试连接泄漏等边界，并加入回归。不是整个已有脏分支的 Pre-Landing clean，不写 `/ship` 就绪认证；没有持久化全局学习/遥测或做 Git 提交。

文档同步检查：9 份本次新增/更新文档的 170 个本地文件链接均存在，空白检查通过；历史审核降级、原未运行项目与 11 包未完成勾选保持，不修改旧审核报告的证据 hash。测试创建的故障子进程已退出，没有遗留本次启动的服务。

| 原计划检查点 | 本次完成度 / 剩余门 |
|---|---|
| D1 / A2 / E-T1,E-T2,X-T1 最小内核 | **PARTIAL**：合同、持久状态和 HTTP 已实现；运行时管理器/DSH adapter 未接；Node 旧实验账本尚未替换 |
| D2 / A4 插件交付 | **NOT DONE**：仅提供可复用的离线生成类型；固定上游、统一 build/profile/CI 与干净环境验证仍未实现 |
| D3 故障测试 | **PARTIAL**：落盘与受控进程接缝已有本次证据；D3 全地图/固定 DSH 原生取消/恢复不因此全通过 |
| D4 / A3 资源执行 | **PARTIAL**：独立配置、任务账本预算已实现；真实 worker 退出绑定、DSH 重试/预算对齐、DuckDB/RSS/temp/spill 与磁盘压力仍未验收 |

下一单元按既定 D1–D4 接通同一 FastAPI 内核与 DSH 原生发送/停止/重连，并将旧 Node `b0-dispatch.sqlite` 实验权威状态替换为协议转发；不能将两个账本同时当权威。旧 Node/插件小样本次没有改线、启动或标记为新合同消费者。之后完成固定构建/CI 和原生故障门，再判断 B0 是否能退出 PARTIAL。完整三类查询、共享数仓/ETL、分析资产、驾驶舱、人群与七项业务验收不在本单元完成声明内。

Git 核验：工作树 `.worktrees/hackathon-mission-mvp` 上的本地分支仍是 `codex/architecture-warehouse-plan-closeout`，HEAD `de2d785f4e0c7abe7fcd8fbb39be7d8c5a0c9642`。远端 `main` 与本地 `origin/main` 均为 `89d342355b65e79418964780ec4e1b2f80b7ca02`，当前提交历史领先 13 / 落后 0；本分支无远端同名分支、upstream 或 PR。分支存在不等于未提交文件已有远端备份；本次没有 commit/push/PR/merge、fetch/重置、真实库操作或公网发布。
