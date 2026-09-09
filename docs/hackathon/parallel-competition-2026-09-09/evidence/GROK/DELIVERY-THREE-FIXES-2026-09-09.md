# 成板 dialog / footer 重开 / 行数 undefined

日期：2026-09-09。候选 `competition-integration`。**未 commit / 未 push。**<br>
基础 HEAD `71a65f06f87cb3a5cbd888372487b6b36faaf2a6` 不能单独绑定本轮；以下为脏工作区 SHA-256。

未停、未占用 `4327`（PID 81058）、`8000`（36717）、`5173`（36727）。未付费模型、未容量、未真实业务数据、未 Git 发布。

## 根因（事件与生命周期，不是“重新进页”）

1. **成板关掉 dialog**：`按认可结果成板` 先 `setPanel('confirm')` 再 `void confirmBoards()`。确认面板读 `resolved_condition.history_scope.kind` / `sales_scope.kind`；合成 HTTP `_competition_result_item` 当时没有这些字段 → **render throw**。React 卸掉 overlay 树，原生 `<dialog>` 随节点删除而关闭。`POST /batches` 仍可能 200（fetch 已发出）。不是 form submit（按钮已是 `type="button"`）。
2. **footer 无法重开**：throw 后 DSH `shell.overlay` 槽进入 error；`store.open` 可能仍为 true。footer `open()` 只把 `open=true` 再写一遍，**不重挂**出错的树。用户看起来像“点了没反应”，只能重新进页才恢复。
3. **行数 undefined**：UI 曾 `String(result.row_count)`；HTTP 结果只有 `page.total`、没有 `row_count`。

## 修复

- 后端结果补 `row_count`、`history_scope`、`sales_scope`、`cutoff`、`sample_mode`。
- `formatResultRowCount`：`row_count ?? page.total`，缺省 `—`，永不输出 `undefined`。
- 确认/看板渲染全部 optional-chain；`conditionChips` 缺字段显示 `—`。
- `OverlayErrorBoundary` 包住看板子树；footer `openTick++`；`RoutedOverlay` / `BoardWorkbench` `key={openTick}`，同页重开即重挂。
- 成板失败留在 overlay 内可重试；相同 `Idempotency-Key` 不新建板。成功后清掉错误横幅。

## 补丁标识

```
7d6cbef99e01ac05ce781b706a0d79db31c0fd19b9c741221bb87446ce0b1a9a  asset-overlay.tsx
2bc7438d43b679a180f8580ee483ffdf5cc2cf4780f51e0910945a9fd6c81f83  index.tsx
cca85b97759804005c96c782bac976df94de989c625e899854cd2799e6ad5b58  overlay-error-boundary.mjs
20cea1b05be9432ab047db5ddfd59cc5f7f72371d5c984fd60eed682b3f707a4  BoardWorkbench.tsx
9ece7872e5a478fa45d7cd1e19e43fd80f4981c5d19911768c6bbfc199e0c5ee  decode.mjs
2694accf4744a332e432db9c106f25321401166f9d11c1965167d3391a7156b8  transport.mjs
93dc87b08725b2728dc810b52704249732d6ef7d0c7cbb97312b9e2880dc3a27  analytics_competition_app.py
b18fa678e8e3e6d4b94dc3f4ea80c759d7f36229546e3e9abe92476a1cecfef8  lib/client.js
```

C0 `contract_hash` 仍为 `97ee36833200b3a1626a4fa88e6b3bc9591bfb5f6bebc5e666aeabdcce13815a`。<br>
上游 DSH `d347e703908d0406b7a7ef80e3a0e594d86b2215`。

## 组件回归

| 测试 | 结果 |
|---|---|
| `competition-board.test.mjs`（含 `formatResultRowCount` / sparse chips） | PASS |
| `overlay-error-boundary.test.mjs` | PASS |
| `competition-board-dom.test.mjs`（sparse 确认不抛；fail_once 重试不重复板） | PASS 7 |
| `test/asset-overlay.test.mjs`（footer 同页重开、409 文案、Tab trap） | PASS 15 |
| `scripts/dsh-dev/brand.test.mjs`（sibling digest fallback） | PASS |
| `backend/tests/test_competition_http_wiring.py`（row_count + 同 key 不重复） | PASS 8 |

## 同一页面浏览器验收（14327 + 18082，未刷新）

顺序：打开 → 选择 COMPLETE → 成板（先注入一次 apply 500）→ 重试成板 → 查看新板 → 关闭 → footer 再开 → 再成板。

| 步骤 | 结果 | 截图 |
|---|---|---|
| 打开 overlay | dialog `open=true`，标题「伸美 AI 增长董事会」，SHINE MAGE 可读 | `samepage-01-open.png` |
| 认可成板列出 COMPLETE | dialog 仍开 | `samepage-02-results.png` |
| 第一次 apply 失败 | dialog **仍开**；文案「可重试；相同幂等键不会重复建板」 | `samepage-03-fail-retry.png` |
| 重试成板 | 「已按认可结果成板」；**行数 1**（不是 undefined）；标题「8月GSV诊断板」 | `samepage-04-new-board.png`（含失败横幅残留，随后已清） |
| 关闭后 footer 再开 | 同页 `dialogOpen=true`，板仍在，行数 1 | `samepage-05-reopen.png` |
| 清错误后的成功态 | 无 INTERNAL 横幅；行数 1 可读 | `samepage-06-success-clean.png` |
| 再点成板 | `GET /boards` **n=1** `board_3214bbbd13f32407b2644cf427242b5d` | HTTP 列表 |

`GET /b0/brand/logo.png` 200（3662 bytes）；`mark.svg` 200。未认证 DSH `/` 401。boundPorts 仅 `[14327]`。

**不以单次 HTTP 200 代替闭环。** 判定依据是同页 dialog 未关、footer 能再开、行数单元格为 `1`、板列表不增加。

## Logo

见 `LOGO-CROSS-WORKTREE.md`：工作树 PNG 是 LFS pointer；`brand.mjs` 按 digest 回退兄弟主工作副本；独立构建不 smudge、不把 Logo 打进 plugin。

## 停本轨

```bash
node scripts/dsh-dev/cli.mjs stop   # 只停 14327
# 只结束监听 18082 的本轨 Python；禁止动 4327/8000/5173
```

T13/T15/T16、Git 发布：仍 NOT_RUN。
