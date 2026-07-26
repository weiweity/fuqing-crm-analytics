# GitHub 仓库治理人工清单（PR5）

> **本文件是人工操作 checklist。**  
> 代码侧无法可靠用 API 断言「已启用 branch protection / secret scanning」等组织级设置。  
> **不要**在文档或 CI 中假装这些开关已经打开；合并本 PR 后由仓库管理员按下列项逐项在 GitHub UI 确认。

仓库：`weiweity/fuqing-crm-analytics`（以实际 remote 为准）

## 1. 分支保护（`main`）

在 **Settings → Branches → Branch protection rules → `main`**：

- [x] **Require a pull request before merging**（禁止直推 main）
- [x] **Require status checks to pass**  
  - required：`lint`、`test`、`ground-truth-lint`、`contract-filterbuilder-lint`
  - required：`frontend`、`dependency-audit`、`docker-smoke`
  - **不要**把 optional e2e-smoke 设为 required（门禁分层：不挡 PR merge）
- [ ] **Require branches to be up to date before merging**（按团队节奏）
- [ ] **Do not allow bypassing the above settings**（管理员也尽量不绕过）
- [ ] **Restrict who can push**（仅维护者 / 空名单 + 只走 PR）
- [x] **Block force pushes**（Prohibit force pushes）
- [x] **Do not allow deletions**

## 2. 规则集（Rulesets，若组织已迁移）

- [ ] `main` ruleset 覆盖 force push / deletion / required checks
- [ ] 与旧 Branch protection 不冲突（以 Rulesets 为准时关闭重复规则）

## 3. Actions 权限

- [x] **Settings → Actions → General → Workflow permissions** = **Read repository contents and packages permissions**
- [x] 取消 **Allow GitHub Actions to create and approve pull requests**（除非 Dependabot 明确需要）
- [x] 仅允许 GitHub-owned Actions
- [x] 强制所有 Action 使用 40 位 commit SHA
- [ ] Fork PR 的 secrets 策略：保持默认不向 fork 暴露 secrets

代码侧已设：

```yaml
permissions:
  contents: read
# checkout:
persist-credentials: false
```

## 4. Dependabot

- [x] **Settings → Code security → Dependabot alerts** 开启
- [x] **Dependabot security updates** 开启
- [x] 已提交 `.github/dependabot.yml`：`pip` + `npm` + `github-actions` 周更
  - 注意：DuckDB / 大 major 需人工 review，勿全自动 merge

## 5. Secret scanning & push protection

- [x] **Secret scanning** 开启
- [x] **Push protection** 开启（推送含密钥时拦截）
- [ ] **Validity checks**（若 plan 支持）按需开启
- [ ] 私有依赖/镜像 token 仅用 Actions secrets / org secrets，不进仓库

## 6. Code scanning（可选）

- [ ] CodeQL 或等价 SAST（私仓 plan 允许时）
- [ ] 与 `pip-audit` / `npm audit` 互补，不替代依赖审计

## 7. 合并策略

- [ ] 默认 **Squash merge** 或 **Merge commit**（团队统一一种）
- [ ] 关闭 **auto-delete head branches** 与否按偏好
- [ ] PR template 仍要求：测试证据 / 风险 / 不碰生产 DuckDB 大库

## 8. 环境与 Secrets（运维）

- [ ] 生产 `HEALTH_API_KEY` / `FQ_CRM_PASSWORDS` 等仅在部署主机或 secret store
- [ ] GitHub Actions **不**存放生产 DuckDB 路径或 131GB 库凭据
- [ ] 轮换清单：密码、API key、registry token（周期 + 离职触发）

## 9. 验收命令（管理员本地）

```bash
# 查看 branch protection（需 admin + gh auth）
gh api repos/weiweity/fuqing-crm-analytics/branches/main/protection || echo "未启用或无权限"

# 查看 vulnerability alerts（需权限）
gh api repos/weiweity/fuqing-crm-analytics/vulnerability-alerts -i || true
```

若 API 返回 404/403：**记录为「未确认」**，不要在文档写「已启用」。

## 10. 与本仓 CI 的关系

| 门禁 | 触发 | 挡 merge？ |
|------|------|------------|
| `lint` / `test` / `ground-truth-lint` / `contract-filterbuilder-lint` | PR + main | required |
| `frontend` / `dependency-audit` / `docker-smoke` | 同上 | required |
| `e2e-smoke` | schedule / dispatch | **不**挡 PR |
| Nightly / Weekly | schedule | 不挡 PR |

详见 [supply-chain.md](./supply-chain.md)、[team-workflow-v1.md](./team-workflow-v1.md)。

## 状态更新 (2026-07-26)

已通过 API 启用：main branch protection（PR + 7 个 required checks、禁止强推/删除、enforce_admins）、secret scanning + push protection、Dependabot alerts/security updates、delete_branch_on_merge、Actions workflow permissions=read。

代码侧：`.github/dependabot.yml` 周更（pip/npm/github-actions）；Actions 仅 GitHub-owned 且强制完整 SHA。
