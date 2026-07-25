# 供应链与依赖 SSOT（PR5）

## 1. Python 依赖分层

| 文件 | 角色 |
|------|------|
| `requirements.txt` | **声明式 SSOT**：版本下限/上界（开发与 B2 import 对账） |
| `requirements-lock.txt` | **可复现 pin**：CI / Docker / 生产 venv |
| `requirements-e2e.txt` | **e2e 最小集**：无 Torch/OCR/爬虫 |
| `pyproject.toml` + `uv.lock` | 工具配置 + 未来 uv SSOT（当前 uv.lock 仅项目元数据，**未**全量迁移） |

### 更新 lock 流程

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
pip freeze > /tmp/freeze.txt
# 人工剔除非 CRM 路径包后写回 requirements-lock.txt
# 禁止把 Torch / paddle / easyocr / scrapling 等打进 CRM lock
```

### 明确排除（无生产 import，已从 lock 删除）

- Torch / torchvision / sentence-transformers / transformers
- PaddleOCR / EasyOCR / OpenCV / onnxruntime
- Pillow / pypdf（CRM 路径未 import）
- scrapling 及浏览器指纹类爬虫依赖

ML/OCR/爬虫工具在独立 scraper 仓维护，不进入本仓 CI 镜像。

### 安全 pin（2026-07-25）

| 包 | pin / 下限 | 说明 |
|----|------------|------|
| starlette | `>=1.3.1` / lock `1.3.1` | CVE 修复；与 PR1 可重叠 |
| click | `>=8.3.3` | CLI/uvicorn 树 |
| idna | `>=3.15` | HTTP 客户端树 |
| urllib3 | `>=2.7.0` | requests/httpx 树 |
| fastapi | `<0.136.3` | 供应链事件上界 |

**禁止本 PR 升级生产 DuckDB**；见 [duckdb-backup-upgrade-checklist.md](../maintenance/duckdb-backup-upgrade-checklist.md)。

## 2. 前端依赖

| 项 | 策略 |
|----|------|
| registry | `frontend-vue3/.npmrc` → `https://registry.npmjs.org/` |
| 安全 pin | axios `1.18.1`、echarts `6.1.0`、vite `8.1.5`、postcss `8.5.23` |
| Excel | 仅 `xlsx-js-style`（**不**盲换；已删未使用直接依赖 `xlsx`） |
| peer | `overrides` 让 `openapi-typescript` 接受仓库 TypeScript `~6`，减少 `--legacy-peer-deps` |
| 禁止 major | Pinia 4 / Tailwind 4 / TypeScript 7 **不**在本 PR 升级 |

```bash
cd frontend-vue3
npm ci                 # 不再默认 --legacy-peer-deps
npm audit --omit=dev   # CI dependency-audit job
```

## 3. CI 审计 job

- `pip-audit -r requirements-lock.txt`（`continue-on-error: true` 起步）
- `npm audit --omit=dev --audit-level=high`
- 稳定后可将 `dependency-audit.continue-on-error` 改为 `false` 升为硬门禁

## 4. 相关文档

- [docker-ports-and-images.md](./docker-ports-and-images.md)
- [github-governance-checklist.md](./github-governance-checklist.md)
- [duckdb-backup-upgrade-checklist.md](../maintenance/duckdb-backup-upgrade-checklist.md)
