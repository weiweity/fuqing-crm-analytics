# 六路并行施工方案

这份文件回答“如何让 6 个 AI 同时施工且互不影响”。它是已批准方案的执行编排，不修改 D1–D48，也不把六个 worktree 误当成六个独立产品。

## 先记住三条规则

1. **六个 AI 必须使用六个独立 worktree/分支。** 禁止六个进程同时改同一个工作目录。没有 worktree，就不要并行。
2. **每个 lane 只能修改自己的 owner paths。** 需要改别的 lane 文件时，写 integration note，交给 P12 总协调 AI；不要直接越界编辑。
3. **契约已在 approved-plan.md 中冻结。** Lane A 实现合同与持久化，其他 lane 使用合同 fixture/类型；发现合同需要破坏性变化时停在 BLOCKED，不能各自改一版。

默认不 push、不合并、不切现役服务、不读真实大库、不写凭据、不安装浮动依赖。是否本地 commit 按实际授权；未授权就交付 worktree 状态、补丁和报告，由总协调者统一收口。

## 六个 lane

| Lane | 交给哪个 AI | 负责批次/任务 | 允许主要路径 | 不得触碰 | 开始条件 | 交付 |
|---|---|---|---|---|---|---|
| A 合同与资产 | AI-A | P02/P03 · T1/T2 | `backend/contracts/`；HTML 页面资产专属 service/route/test；离线合同 | `dsh-plugins/analytics-workbench/src/client/`、`src/free-page/` 运行时 | 从同一基线读取 approved-plan | 页面包/manifest/版本/CAS/幂等/回滚合同与测试 |
| B 运行时与资源 | AI-B | P01/P04 · T0/T3/T4 | 隔离夹具；`dsh-plugins/analytics-workbench/src/free-page/runtime/`、`resource/`、预览容器专属文件 | backend 页面资产 service；`src/client/`业务状态 | 先验证自己的隔离夹具；消费合同 fixture | 沙箱、MessageChannel、资源清单/缓存、页面错误恢复 |
| C 授权数据桥 | AI-C | P05 · T5 | `backend/services/analytics/page_result_access*`；`src/free-page/bridge/`；桥测试 | Lane A 的资产存储文件；宿主 UI | 使用 approved-plan 的 bridge contract fixture | result_ref/data_ref 只读、分页、额度、过期/撤权和来源状态 |
| D 源码定位与编辑 | AI-D | P06/T29 · T6/T29 | `src/free-page/source-index/`、`patch/`、`edit/`；独立编辑测试/fixture | 现有 `src/client/library-board-client.mjs`、宿主导航/UI | 使用 A/B 的类型/fixture；不等真实模型 | 元素/动态区域/重选/主动整页、补丁预览与范围守卫 |
| E 资料库与宿主视觉 | AI-E | P07/P08/P09/P10 · T7/T10–T20 | `src/client/`资料库页面、workspace、composition UI、competition-shell 主题映射、UI tests | Lane F 的导航/leave coordinator；Lane D 的 `src/free-page` 编辑实现 | 使用 C/D 的 mock adapter；不得修改上游 DSH | 生成入口、预览工作区、浏览/编辑模式、状态脊、首页、主题、响应式与可访问性 |
| F 离开与导航竞态 | AI-F | P11 · T21–T28 | 新建 `src/client/leave/`、`navigation/`、host adapter、协调器/epoch/helper 测试 | Lane E 的 UI 组件；Lane D 的编辑源码模块；DSH 上游 | 使用稳定的 client/host adapter fixture | 单一离开协调、脏稿谓词、epoch、回执 helper、宿主接缝测试 |

**重要：** E/F 都会接触用户交互，但 E 拥有页面和视觉，F 拥有离开事务和导航状态。F 不直接重写 E 的组件；E 通过 F 公开的 adapter 接入。D 不把 T29 的真实 AI 样本写入自己的完成条件，真实矩阵由最终验收负责。

## 依赖与合并顺序

### 可以并行的阶段

- A、B 可以同时开始；B 的 T0 可行性证据必须先于它声明 P04 完成。
- A/B 的合同和 fixture 稳定后，C、D、E、F 可以在各自 owner paths 上并行开发；它们遇到未完成实现时用确定性 mock，不复制另一 lane 的内部代码。
- 实际风险最低的并行组合是 **A+B**，以及随后 **C+D+E+F** 的隔离 worktree 开发；每个 lane 都必须声明使用了哪些 mock/fixture。

### 必须由总协调 AI 顺序完成

1. 检查六个 lane 的报告、diff、测试和越界文件。
2. 按 A → B → C → D → E → F 的接口顺序合并或移植改动，解决冲突；不要让 lane 自己互相 cherry-pick。
3. 执行 P12/T8 集成验收：真实 iframe/MessageChannel、生成→预览→绑定→局部修改→保存→重开/回滚，以及全局离开接缝。
4. 执行 P13/T9 真实 AI 验收：三个样本、有无 DESIGN.md/skill 对照、D48 局部编辑矩阵和性能/视觉证据。

并行不等于省略依赖；它把“各自模块施工”并行化，把“合同接缝和真实用户旅程”集中到 P12/P13。

## 六个 AI 的共同启动语句

把下面文字和对应 lane 提示词一起交给 AI：

```text
你是自由 HTML 驾驶舱施工 lane 的独立执行者。你必须在自己的 git worktree 中工作，不读取或修改其他 lane 的工作树。

先读取 AGENTS.md、STATUS.md、docs/operating/verification.md、docs/hackathon/free-html-cockpit/README.md、approved-plan.md、DIAGRAMS.md，以及本 lane 的提示词。核对真实 branch/HEAD/dirty、工具链和依赖报告。需要理解代码且仓库有 .codegraph/ 时，先使用 CodeGraph。

只修改本 lane 的 owner paths；其他路径需要改动时写入报告的 integration notes，并停止越界编辑。不得改 DSH 上游源码。自由 HTML/CSS/JavaScript 是页面资产，不得把生成器限制成 BoardSpec/固定组件目录；DESIGN.md/skill 是可选指导。数据桥只读授权结果，页面不能拿凭据/SQL；源码包与 binding manifest 遵守原子版本、base_version、幂等、CAS。

完成本 lane 的实现、单元/契约验证和失败路径；不要只写方案。失败后调查并修复，仍不能通过就写 BLOCKED，不能用 mock/截图把未运行写成通过。写 docs/hackathon/free-html-cockpit/reports/LANE-*.md，记录准确命令、退出码、浏览器/fixture、改动文件、未完成项、越界请求和交给 P12 的 integration notes。不要自动 push、merge、启动现役服务、访问真实大库、安装浮动依赖或发布公网。
```

## 可直接粘贴的六条启动命令/提示词

每个 AI 都要在独立 worktree 中收到一条：

### AI-A

```text
使用共同启动语句。你是 Lane A 合同与资产负责人。读取 prompts/P02-contracts.md、prompts/P03-asset-state.md；实现 T1/T2。你拥有 backend/contracts、页面资产专属 service/route/test 和离线合同入口。冻结页面包、binding manifest、桥消息、源码/manifest 原子版本、CAS、幂等、回滚、权限与错误语义。不要修改 free-page 运行时或宿主 client。使用合成小库和新连接/进程重开测试。完成后写 reports/LANE-A.md；没有本地提交授权就不要 commit。
```

### AI-B

```text
使用共同启动语句。你是 Lane B 运行时与资源负责人。读取 prompts/P01-runtime-feasibility.md、prompts/P04-source-runtime.md；实现 T0/T3/T4。先用目标浏览器和合成失控页面验证宿主可操作、页面可关闭/重启、保存版本可恢复，再实现隔离运行时、MessageChannel、资源清单/hash/权限/外联负测和错误边界。你只拥有 runtime/resource/预览容器专属路径；不要修改 backend 页面资产或宿主业务状态。完成后写 reports/LANE-B.md；没有本地提交授权就不要 commit。
```

### AI-C

```text
使用共同启动语句。你是 Lane C 授权数据桥负责人。读取 prompts/P05-data-bridge.md；实现 T5。消费 approved-plan 的 bridge contract fixture，不重写 Lane A 的资产存储。实现 result_ref/data_ref 只读读取、摘要/分页/范围、取消/过期/额度、actor/单位/时间/版本/撤权校验和宿主来源状态；禁止 SQL、token、任意外联和页面直接保存。使用合成结果夹具。完成后写 reports/LANE-C.md；没有本地提交授权就不要 commit。
```

### AI-D

```text
使用共同启动语句。你是 Lane D 源码定位与编辑负责人。读取 prompts/P06-source-editing.md；实现 T6/T29。只在 source-index/patch/edit 专属路径工作，使用确定性页面 fixture。实现静态元素精确映射、动态图表/Canvas 所属区域、映射失效重选、用户主动整页范围、共享 CSS/JS 影响预览和取消/过期/失败不提交。不要要求真实 AI 样本作为本 lane DONE；P13 会做真实矩阵。不要修改 library-board-client 或宿主 UI。完成后写 reports/LANE-D.md；没有本地提交授权就不要 commit。
```

### AI-E

```text
使用共同启动语句。你是 Lane E 资料库与宿主视觉负责人。读取 prompts/P07-library-core.md、P08-browse-edit-access.md、P09-host-experience.md、P10-visual-width-acceptance.md；实现 T7/T10–T20。使用 C/D 的 mock adapter，不复制其内部实现。拥有资料库首页、工作区、composition UI、SHINE/Ant Design 集中主题映射、浏览/编辑可见模式、状态脊、可信状态、响应式、焦点和页面检查器。必须保留原生聊天入口；页面预览保持自由 HTML；提供可见的元素/动态区域/主动整页范围入口。不要修改 Lane F leave coordinator/navigation 文件。完成后写 reports/LANE-E.md；没有本地提交授权就不要 commit。
```

### AI-F

```text
使用共同启动语句。你是 Lane F 离开与导航竞态负责人。读取 prompts/P11-leave-coordinator.md；实现 T21–T28。只拥有新建 leave/、navigation/、host adapter、协调器/epoch/helper 测试路径；使用稳定的 library/host adapter fixture，不重写 Lane E UI。实现干净选区不拦截、真实脏稿才三选、保存成功原导航一次、失败/冲突/未知留页、迟到 list/get/preview 按 epoch 丢弃、保存回执按幂等/CAS 核对。真实 DSH 宿主接缝可在 P12 集成。完成后写 reports/LANE-F.md；没有本地提交授权就不要 commit。
```

## 总协调 AI 的收口语句

```text
六个 lane 已交付。你是总协调 AI，不重新设计产品。读取六份 lane 报告和各自 worktree diff，逐项核对 owner paths、approved-plan SHA、合同一致性和测试证据。先解决合同/类型/fixture 接缝，再按 P12 执行完整集成验收；失败就定位并修复，不能跳过。然后按 P13 执行三个真实 AI 样本、有无 DESIGN.md/skill 对照、D48 范围矩阵、保存重开/回滚、响应式/可访问性/导航恢复和性能证据。更新 reports/P12.md、reports/P13.md 与 manifest；未运行或只用 mock 的项目明确标记。不要自动 push、merge、发布公网、切换现役服务或访问真实大库。最终给出通过项、阻塞项、实际命令、浏览器环境和下一步。
```

## 什么时候可以认为“六路并行成功”

- 六个 worktree 没有越界改动；所有 lane 报告存在并能复现。
- P02 合同一致，C/D/E/F 没有各自发明不同字段或状态机。
- P12 的真实浏览器集成通过；P13 的真实 AI 证据存在。
- 页面仍能自由生成 HTML/CSS/JavaScript，宿主权限、可信状态和版本恢复有效。
- 仍未授权的 commit/push/merge、部署或公网发布不被 AI 擅自执行。
