> 历史方案：Git 收口候选已改为本 checkout Git LFS 字节，见 ../CODEX/GIT-CLOSEOUT.md。下文保留原轮证据。

# Logo 跨工作树依赖与独立构建

日期：2026-09-09。候选 `competition-integration`。**未 commit。**

## 事实

- 产品 Logo 源文件：`frontend-vue3/src/assets/brand/shine-mage.png`
- 冻结 digest：`21b8273703b9015027b572cb830b8bb01e9fc406c39b14ec7c228fbcdcaf4000`
- 比赛工作树里该 PNG 是 **Git LFS pointer**（`version https://git-lfs.github.com/spec/v1`）。本轨禁止 smudge、禁止把真实 DuckDB/LFS 大文件拷进工作树。
- 独立 DSH（`--web-port 14327`）不把 Logo 打进 plugin bundle。运行时由 `scripts/dsh-dev/brand.mjs` 挂到 `/b0/brand/logo.png` 与 `/b0/brand/mark.svg`。
- `overlay.mjs` 在 `--plugin on` 时把 `analytics-dev-brand-assets` 与 workbench UI 一起插入 patch。独立构建只要走 `scripts/dsh-dev/cli.mjs start`，不必另接 `--extra-patch`。

## 运行时回退（已实现）

`brand.mjs` 的 `readLogo()`：

1. 先读本工作树 `frontend-vue3/src/assets/brand/shine-mage.png`，校验 SHA-256。
2. 若是 LFS pointer 或校验失败，再读**兄弟主工作副本**<br>
   `../../fuqing-crm-analytics/frontend-vue3/src/assets/brand/shine-mage.png`<br>
   （相对 `competition-integration` 工作树根）。
3. 仅当字节通过 digest 才 `registerAsset`。pointer 不会当 PNG 发出。
4. 不执行 `git lfs pull`，不改 `GIT_LFS_SKIP_SMUDGE`。

`scripts/dsh-dev/brand.test.mjs` 覆盖：路由注册成功；源码含 sibling fallback、不含 LFS pull。

## 独立构建（无兄弟 checkout）时

按优先级：

1. **推荐**：旁边保留主工作副本 `fuqing-crm-analytics`，让 runtime fallback 生效。独立 DSH 不复制 PNG。
2. **无兄弟树**：把已校验 PNG 放到本树同一相对路径，**不要 git add、不要 smudge**。`GIT_LFS_SKIP_SMUDGE=1` 克隆后用 `cp` 覆盖 pointer 即可。
3. 若 `dsh-b0/brand-assets.mjs` 能提供 `/b0/brand/logo.png`，`apply()` 优先走那条；失败才回退到上述文件读取。
4. 构建 plugin 时 **不要** 把 Logo 打进 `lib/client.js`。品牌只由 `dsh-dev` webServer 提供。

## 不要做

- 不要对本工作树跑 `git lfs pull` / 关闭 skip-smudge。
- 不要把真实业务数据、付费模型、容量测试或 Git 发布绑到 Logo 恢复。
- 不要改用户占用的 `4327/8000/5173`。
