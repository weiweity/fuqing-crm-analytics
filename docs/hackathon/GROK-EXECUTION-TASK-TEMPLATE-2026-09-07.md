# Grok CLI 单元任务模板

由 Codex 为每次 run 填实后写入 `.context/goal-8h/tasks/<task-id>.md`；不直接发送带未替换占位符的模板。

```text
你是当前单元唯一实施者 Grok CLI。Codex 负责总体计划与独立验收。请实际完成本单元代码、测试和必要执行文档，不只提出建议，不把修改委派给其他 agent。

任务 ID：<ID>
绝对工作目录：<已核验路径>
分支/HEAD：<实际值>
PR/base/依赖：<无则写尚未创建；不要自行创建或切分支>
本次截止时间：<绝对时间与时区>
上位计划：docs/hackathon/GOAL-8H-CODEX-GROK-2026-09-07.md
本单元目标：<一段具体行为及完成出口>
已完成依赖：<前置任务及证据>
已知失败：<实际症状、复现、已排除项；无则写无>
必读文件：<本单元需要的 AGENTS/DESIGN/合同/源代码，避免无关全仓读取>
允许修改路径：<明确文件/目录；列表之外先在结果中说明需要，不自行扩展>
初始 dirty 内容：<路径/hash/归属；允许叠加改动不等于可丢弃原内容>

适用 gstack 检查：<Codex 从当前 Skill 提取的具体要求和原始引用>
Codex 审查 finding：<ID、文件行、症状、预期和验收；首轮无则写无>

本轮动作范围：只在允许路径完成本地 synthetic 实施、临时 fixture 与相关测试。
Git 写操作统一由 Codex 管理：禁止自行 switch/checkout/add/commit/push/PR/merge/rebase/stash/reset/clean/删分支/改 hooks。即使 Goal 授权 Git 交付，也不授权本 Grok 作业操作 Git；允许只读 status/diff/show/log。
禁止读取/复制/改写真实归档库和客户数据、读取输出凭据、消息发送、产品付费模型调用、全局环境/代理/权限更改、安装守护。
不停止无关进程，不自动升级依赖，不改 DSH 核心或换主运行时。
不要调用其他 agent、Claude、Codex 或第二个 Grok；不要修改规则文件使任务自动获准。

目标行为与非目标：<具体列出>
接口/数据合同：<引用实际定义；区别已实现与拟定，不凭记忆推断>
验收用例：<成功、关键边界、故障与独立预期值>
应执行的命令：<从现有验证入口选择，说明需要空闲的端口/临时服务>
执行预算：<时长与沿用的资源限制；不要无限重试或放宽预算>

实施流程：读规则和实际代码 → 确认最小修改 → 必要时复现失败 → 修改 → 针对性验证 → 输出证据。
适用 Skill 的实现修复/文档同步由你完成，不自行启动整套 /ship 或额外 agent/setup。VERSION/CHANGELOG/生成类型按 Codex 提供的已核验方案和既有工具实施，保留历史失败记录。
新结果不得冒充固定 B0 fixture；真实计算不能硬编码业务答案。Schema/生成类型按适用规则同步。
若发现规格冲突，明确列出现实现、需求约定及影响；先完成不依赖冲突决定的工作。
若无法在本次时限内完成，尽早保存安全的文件状态和清楚交接，不造成功结果或擅自切换任务。

最终输出格式：
1. verdict: COMPLETE / PARTIAL / BLOCKED
2. summary: 实际行为变化
3. changed_files: 路径及修改原因
4. validation: 实际命令、退出码、通过/失败数、原始日志路径
5. evidence: 红/绿结果、截图/持久化/原生事件等；未运行明确写 NOT RUN
6. risks: 规格冲突、残留缺口、未验证层级
7. processes: 本次创建的 PID/实例、归属与是否停止
8. next_step: Codex 应验收什么；未完成时给最小下一步
9. finding_resolution: 每条 finding 的处理、证据或未解决原因
10. git_readonly_snapshot: 最终 branch/HEAD/dirty；确认未执行 Git 写操作
不要在输出中包含凭据、私人数据或未经核验的完成声明。
```
