# 项目整洁度规范（Project Hygiene）

> **适用性更新**: 2026-09-06。当前行为规则统一见 [AGENTS.md](../../AGENTS.md)，本文件说明文件用途并保留 2026-07-19 清理历史。归档默认冷存，候选清理不等于删除许可。

---

## 1. 根目录应有什么

| 保留 | 用途 |
|---|---|
| `README.md` | 人读入口 |
| `AGENTS.md` | 唯一 AI 行为正文；`CLAUDE.md` 仅一行导入 |
| `VERSION` | 版本号唯一数字源 |
| `CHANGELOG.md` | 近窗变更 |
| `STATUS.md` | **短状态表**（勿再堆 sprint 编年；长文进 CHANGELOG / history） |
| `HANDOVER.md` | 交接（中期可迁 `docs/maintenance/`） |
| `backend/` `frontend-vue3/` `scripts/` `docs/` `mcp_servers/` | 应用与文档 |

| 不应长期堆在根 | 去向 |
|---|---|
| `HANDOFF-TO-CODEX-*.md` | 已 `.gitignore`；先核对是否仍在使用及有无独有证据，再按授权归档或清理 |
| `HANDOFF-TO-CLAUDE-*.md` / `HANDOFF-FINAL-*.md` | 同上；不因 ship 自动删除 |
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
| `docs/rules/L4-permanent-rules.md` | 旧 CRM 技术细则和历史依据 | 覆盖当前行为边界 |
| `AGENTS.md` | 当前行为、授权与必要契约 | 模型专用重复正文、Sprint 编年 |

---

## 3. 代码 / 数据边界

| 路径 | git | 说明 |
|---|---|---|
| `data/**`、`*.duckdb` | ❌ | 真实库/运行数据不入仓；当前默认归档冷存 |
| `.env` | ❌ | 密钥 |
| `outputs/` | ❌ | 跑数/导出/二维码 |
| `backend/services` 等 | ✅ | 业务代码 |
| `docs/sprints/archive/` | ✅ | 有意历史归档 |
| `scripts/archive/`、`scripts/_archive/` | ❌ ignore | 死脚本归档 |

**红线**：勿 `git add -f data/`、勿提交 duckdb、勿把 `outputs/` 当交付仓。

---

## 4. 2026-07-19 已做清理

### 上午 hygiene（#33 一带）

1. `.gitignore`：`outputs/`、`logs/`、`scripts/_archive/`、`HANDOFF-TO-CLAUDE-*`、`HANDOFF-FINAL-*`、`analysis/`
2. 删除根孤儿 `SamplingView.vue`
3. 已跟踪根 HANDOFF → `docs/sprints/archive/`
4. 本文件 + `team-workflow-v1.md` 落地

### 下午 tech-debt + 文档整理（#35 + 本波）

1. **STATUS.md** 截断短表；长编年 → `docs/history/STATUS-HISTORY.md`
2. **TECH-DEBT.md** 短开放表；历史 → `docs/history/TECH-DEBT-HISTORY.md`
3. **e2e** schema-only soft/skip（CI 不挡合）
4. **`docs/sprints/`** 仅 `_sprint-close-index` + `README` + `archive/`
5. 根 **8× `HANDOFF-TO-CODEX-*`** → `docs/sprints/archive/root-handoffs-2026-07-19/`
6. 父工作区 **`fuqin-date/README.md`** 刷新扫描；`archive/README.md` 建入口

### document-release（同日）

1. **#CLAUDE-L4-sink ✅**：L4 全文 → `docs/rules/L4-permanent-rules.md`；CLAUDE 短索引  
2. CHANGELOG 近窗 + HISTORY 滚动  
3. archive 删 Admin Upload / L4.74 中间 stage；保留决策 memo + GO-NO-GO  
4. `docs/history/README.md` + `sprints/archive/INDEX.md`

**未做（真债，见 TECH-DEBT）**：

| ID | 说明 |
|---|---|
| `#scripts-ops` | ✅ monitors → `scripts/ops/`（2026-07-19） |
| `#e2e-data` / `#C7` / `#preflight-env` | 仅触发型延期，见 TECH-DEBT |

---

## 5. 检查清单（PR 前 30 秒）

```bash
git status -sb                    # 无 outputs/ data/ .env
git check-ignore -v outputs/      # 应被 ignore
ls SamplingView.vue 2>/dev/null   # 根上不应再有
```
