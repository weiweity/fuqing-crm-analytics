# 项目整洁度规范（Project Hygiene）

> **最后更新**: 2026-07-19  
> 团队双轨审计（docs + code）后的最小可执行 SSOT。  
> 目标：工作区可读、误提交风险低、新人 5 分钟知道「什么在 git / 什么是本地生产」。

---

## 1. 根目录应有什么

| 保留 | 用途 |
|---|---|
| `README.md` | 人读入口 |
| `CLAUDE.md` | AI 行为规则 SSOT（细则见 `docs/rules/`） |
| `VERSION` | 版本号唯一数字源 |
| `CHANGELOG.md` | 近窗变更 |
| `STATUS.md` | **短状态表**（勿再堆 sprint 编年；长文进 CHANGELOG / history） |
| `HANDOVER.md` | 交接（中期可迁 `docs/maintenance/`） |
| `backend/` `frontend-vue3/` `scripts/` `docs/` `mcp_servers/` | 应用与文档 |

| 不应长期堆在根 | 去向 |
|---|---|
| `HANDOFF-TO-CODEX-*.md` | 已 `.gitignore`；ship 后物理删或 `docs/sprints/archive/` |
| `HANDOFF-TO-CLAUDE-*.md` / `HANDOFF-FINAL-*.md` | 同上 + ignore |
| `outputs/` | 运行时产物，**禁止 commit** |
| 根目录空/占位 `.vue` | 真源在 `frontend-vue3/src/views/` |

---

## 2. 文档职责（消歧）

| 文档 | 只回答 | 禁止 |
|---|---|---|
| `VERSION` | 当前版本号 | 故事 |
| `STATUS.md` | 能不能用 / 测多少 / 债指针 / main 大致 HEAD | 多段「最后更新」编年 |
| `docs/TECH-DEBT.md` | 还欠什么 | 已关闭 sprint 复述 |
| `CHANGELOG.md` | 版本间可见变更 | 未合并 WIP 日记 |
| `docs/sprints/*` | **未 ship** handoff | 已 ship 过程文（进 `archive/`） |
| `docs/rules/L4-permanent-rules.md` | L4 细则全文 | — |
| `CLAUDE.md` | 硬 STOP + 12 步 + 索引 | 无限加长 L4 全文 |

---

## 3. 代码 / 数据边界

| 路径 | git | 说明 |
|---|---|---|
| `data/**`、`*.duckdb` | ❌ | 本地即生产，永不 commit |
| `.env` | ❌ | 密钥 |
| `outputs/` | ❌ | 跑数/导出/二维码 |
| `backend/services` 等 | ✅ | 业务代码 |
| `docs/sprints/archive/` | ✅ | 有意历史归档 |
| `scripts/archive/`、`scripts/_archive/` | ❌ ignore | 死脚本归档 |

**红线**：勿 `git add -f data/`、勿提交 duckdb、勿把 `outputs/` 当交付仓。

---

## 4. 2026-07-19 已做清理（本 hygiene sprint）

1. `.gitignore`：`outputs/`、`logs/`、`scripts/_archive/`、`HANDOFF-TO-CLAUDE-*`、`HANDOFF-FINAL-*`、`analysis/`
2. 删除根孤儿 `SamplingView.vue`（真文件在 frontend）
3. 已跟踪根 HANDOFF → `docs/sprints/archive/`
4. 本文件 + `team-workflow-v1.md` 落地

**未做（下一波）**：STATUS/TECH-DEBT 全文截断、CLAUDE L4 表继续下沉、scripts 根 monitor 归 `ops/`、e2e merge 策略 — 见 `team-workflow-v1.md`。

---

## 5. 检查清单（PR 前 30 秒）

```bash
git status -sb                    # 无 outputs/ data/ .env
git check-ignore -v outputs/      # 应被 ignore
ls SamplingView.vue 2>/dev/null   # 根上不应再有
```
