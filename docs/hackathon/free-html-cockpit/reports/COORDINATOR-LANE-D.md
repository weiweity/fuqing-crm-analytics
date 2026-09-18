# 主协调审查 · Lane D

- 状态：Lane D **owner-scope DONE**（确定性 fixture）。P06 批次 **PARTIAL**（依赖 P03/P04 未在本树接上；真浏览器 / 真实 AI / A 持久化 / 完整 pipeline **NOT_RUN**）
- 审查日期：2026-09-18
- 工作树：`/Users/hutou/Desktop/ai-engineering/历史项目/fuqin-date/fuqing-crm-analytics-free-html-D`
- 分支 / HEAD：`codex/free-html/lane-d` @ `b45a27bb9022057ce37aa9123927e8b4663a2720`（未 commit / 未 push）
- 报告：`reports/LANE-D.md`
- approved-plan SHA256：`47fa5bfe482cb9bd93f4f02a7c62c6933d0242b5204ea95f2b912edc603a6ffb`
- 本轮未 commit、未 push、未切 6677（PID 8758 仍在听）、未改 DSH 上游、未改 D 的 owner 业务文件

## 越界核对（通过）

| 路径 | 结果 |
|---|---|
| `library-board-client.mjs` | 与主仓字节相同 |
| `html-sandbox.mjs` | 与主仓字节相同 |
| `scripts/dsh-b0/pipeline.mjs` | 与主仓字节相同（D 未改扫描，只用 `tests/` 再导出） |
| `manifest.json` | 与主协调副本相同；D 未改批次 status |
| DSH upstream | 无 dirty |
| `src/free-page/` 子目录 | 仅 `source-index/`、`patch/`、`edit/` |
| 冻结合同 fixture | `frozen-contract-v0.json` / `d48-scope.fixture.json` 语义未改 |

额外路径 `tests/free-page-edit.test.mjs` 只再导出 34 项，记入 P12：纳入 `src/free-page` 扫描后删掉再导出，避免双跑。

## 复跑证据（本轮主协调执行，不是报告摘抄）

命令（cwd = Lane D worktree，解释器 `/Users/hutou/homebrew/opt/node@24/bin/node` **v24.19.0**）：

```text
node --test \
  dsh-plugins/analytics-workbench/src/free-page/source-index/source-index.test.mjs \
  dsh-plugins/analytics-workbench/src/free-page/patch/patch.test.mjs \
  dsh-plugins/analytics-workbench/src/free-page/edit/edit.test.mjs \
  dsh-plugins/analytics-workbench/src/free-page/edit/d48-scope.test.mjs
```

结果：34 pass / 0 fail，exit **0**，duration_ms ≈ 50。

再导出入口同样 34 pass / exit 0。全部本 lane `.mjs` `node --check` exit 0。

OCR 返修在代码里对得上，且有对应测试名：

| 声称 | 代码 | 测试 |
|---|---|---|
| 选区外无标记 HTML | `htmlOutsideSelectionUnchanged` 要求中间段 = 重索引 outer | `untagged HTML inserted outside the selection cannot be submitted` |
| `document.body.replaceChildren()` | `PAGE_WIDE_JS` → `shared_js` | `region JS rewritten to document-wide APIs requires scope confirmation` |
| 连续 mutate 重绑 | `applyLocalDraft` → `rebindContext` | `consecutive local text edits rebind source ranges after each draft` |
| D9 丢回执复用 `save_*` | `saveDraft` 在 `confirmation_uncertain` 时复用 `last_idempotency_key` | `D9 lost receipt retries the original save idempotency key` |
| kind 必须一致 | `selection.kind !== node.kind` → `MAPPING_STALE` | `static_element cannot silently locate a dynamic region` |
| canvas 不写死 `r_chart` | `tag === 'canvas'` 的 dynamic_region | `canvas_html_unchanged` 字段 |
| `@media` 共享 | `partitionCss` 的 atBlocks 变化一律 shared | `shared at-rule CSS change requires confirmation...` |

合同：`INVALID_PAGE` 不是 `INVALID_BOARD`（后者只出现在注释里）。操作集 `GENERATE\|PATCH\|SAVE\|ROLLBACK`，预览 `PENDING\|APPLIED\|CANCELLED`。`agentContext().runtime === 'native-dsh'`。adapter 分开 `isDirty` / `hasActiveEditContext`。

## 未运行（不得记通过）

- 完整 `scripts/dsh-b0/pipeline.mjs --check`
- 真浏览器 iframe / 选区点击
- 三类真实 AI（P13）
- Lane A `page_documents` 新连接 / CAS（本树是 `createMemoryPageStore`）
- N08 可见浏览/编辑 UI（E）、N10 工具注册、离开协调（F）

## P12 清单（尚未执行移植）

按 A→B→C→D→E→F，不要现在把 D 拷进主仓或其它 lane。

1. 用 A 的 `page_documents` 替换 `createMemoryPageStore`；保持原幂等键、CAS、`INVALID_PAGE`。
2. `pipeline.mjs` 扫描加入 `src/free-page`，然后去掉 `tests/free-page-edit.test.mjs` 再导出。
3. E 只 `import` `src/free-page/edit/adapter.mjs`；脏稿谓词用 `isDirty`，不要把干净选区当离开。
4. D48：`MAPPING_STALE` 且 `widen_to_whole_page: false`；整页仅 `switchWholePage()` / `user_switched`；共享 CSS/JS 用 `SCOPE_REQUIRES_CONFIRMATION` + 匹配 `impact_hash`。
5. 目录无冲突：A=`contract/`，B=`runtime|resource|preview/`，C=`bridge/`，D=`source-index|patch|edit/`。

残余风险：`PAGE_WIDE_JS` 是正则启发式，不是 JS 解析器；P12 接真实页面时仍要看非 `document.body.*` 的整页脚本。ROLLBACK 在 codes 里有，edit controller 未实现回滚（属 A/P03 + P12）。

## 其它 lane（本轮未复验）

A/B/C/E 工作树已有未跟踪实现和 `LANE-*.md`；F 有 `leave/`、`navigation/` 但尚无 `LANE-F.md`。本文件只给 D 结论，不把它们标通过。
