# Competition 审查修复交付（2026-09-10）

本轮修复此前独立复现的 7 项问题，代码位于 `competition-closeout` 工作树、`codex/competition-closeout` 分支。基线为 `0d13886c8c339a93ff6df12a07047526528bca29`；修复尚未提交，当前成果以工作区文件及 `.context/competition-repair/repair-manifest.json` 的 SHA-256 为准。

## 修复结果

| 原问题 | 修复与验证 |
|---|---|
| P1 候选 ID 跨权限域覆盖 | 写事务内验证 ID 与权限域、cohort、快照；拒绝跨域和同 ID 改内容；重读核验授权列与 JSON 一致。覆盖原请求重放、冲突和旧损坏状态。 |
| P1 诊断缓存旧权限 | 每次 HTTP 取当前身份；权限变化丢弃旧条件、证据与目标，保留已用预算。降权后的已有会话返回 403。 |
| P1 看板重开显示别的结果 | 保留服务端 blocks，按冻结绑定恢复结果、布局和标题；不可用来源不替换成列表首项。覆盖实际 HTTP 保存布局、新应用重读及编译组件显示。 |
| P1 第二次成板固定 ID 冲突 | 按成板意图生成新 ID；失败和重挂载重试沿用原载荷，成功后清理；HTTP 预览不再写库。覆盖首次响应丢失、同请求重试与第二组结果创建。 |
| P1 取消成功后仍发布 | 取消持久化到同一 SQLite，发布事务内检查；取消先到时阻止晚到请求，发布持锁时取消不假报成功。覆盖 batch/attempt 并发与独立进程退出重读。 |
| P2 行动草稿无法新建、重开 | 按当前 actor/权限域查询草稿和候选；补首次创建入口，恢复版本并更新同一草稿。覆盖保存、换应用/组件实例重开及隐私隔离。 |
| P2 新诊断会话永久 429 | 状态按 actor + session 隔离，定义空闲回收和容量边界；原生工具从执行上下文传 session。覆盖每会话预算、条件隔离和编译工具覆盖模型伪造 session 值。 |

运行时包络和兼容规则见 [Competition HTTP 约定](../operating/competition-http.md)。冻结 C0 合同 hash 仍为 `97ee36833200b3a1626a4fa88e6b3bc9591bfb5f6bebc5e666aeabdcce13815a`。

## 本轮验证

| 检查 | 结果 | 本地日志 |
|---|---|---|
| 全部 `test_competition_*.py` 与诊断模块测试 | 153 passed；含新增 9 项后端回归和 A9 有限验收 | `.context/competition-repair/backend-all-competition.log` |
| 定向编译组件与成板意图测试 | 24 passed | `.context/competition-repair/frontend-final.log` |
| 共享 B0 pipeline | PASS：460 项 Python、合同与 Ruff；Node 分组 20/225/53/56/53 全通过；host/client 类型检查、真实 Cordis loader、干净重建字节比对通过 | `.context/competition-repair/b0-pipeline.log` |
| 最后补充的原生会话传递回归 | competition-agent 文件 11 passed，使用实际编译工具注册/执行与拦截的 HTTP | `.context/competition-repair/native-session.log` |
| 修改范围的 Ruff、`git diff --check` | PASS | 本轮命令输出 |

各分组存在重叠，未相加作为独立测试总数。B0 检查后只增加会话传递测试和文档，生产代码没有继续变化。原生会话测试另行运行通过，无须重复整套 B0。

复现命令（在成果工作树执行）：

```sh
PYTHONPATH="$PWD" PYTHON_DOTENV_DISABLED=1 \
  .context/reproduce-backend/bin/python -m pytest \
  backend/tests/test_competition_*.py \
  backend/services/analytics/competition_diagnosis/tests -q

B0_BUILD_UPSTREAM="$PWD/.context/dsh-b0/upstream" \
  /Users/hutou/homebrew/opt/node@24/bin/node scripts/dsh-b0/pipeline.mjs \
  --check --python "$PWD/.context/reproduce-python/bin/python"

PATH="$PWD/.context/reproduce-python/bin:/Users/hutou/homebrew/opt/node@24/bin:/usr/bin:/bin" \
  /Users/hutou/homebrew/opt/node@24/bin/node --test \
  dsh-plugins/analytics-workbench/src/competition-agent/competition-agent.test.mjs
```

依赖沿用已准备的锁定 Python/Node 和 DSH `d347e703908d0406b7a7ef80e3a0e594d86b2215`。取消持久性测试使用两次独立子进程和本次私有临时小库；其他 HTTP 验证使用 TestClient，组件验证使用编译 React 与 jsdom/受控 HTTP 响应。B0 pipeline 的临时端口按既有隔离入口使用并回收，没有切换用户演示实例。

## 交付边界

这是 7 项已知问题的本地修复及回归结果，不代表 OCR 175 文件全量审核完成，也不代表整产品已通过。OCR 保持停止；本轮没有 commit、push、PR、merge 或部署。

没有运行付费业务模型、真实业务数据、浏览器三角色 UAT 或容量测试；T13/T15/T16 和原有 T17 PARTIAL 状态没有借本轮回归改为通过。预先运行的 4327、8000、5173、14327 实例未重启或终止。

持久化表结构未迁移；取消新增于已有 metadata 命名空间。取消前已提交的批次操作仍保留。旧程序会忽略取消记录，降级需保留取消检查，不能仅凭数据库版本相同宣称行为可回退。
