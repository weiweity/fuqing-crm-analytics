# Docker 端口策略与基础镜像（PR5）

## 1. 端口矩阵（SSOT）

| 场景 | 后端 | 前端 | 说明 |
|------|------|------|------|
| **本地 dev（非 Docker）** | `8000` | Vite `5173` | README 默认：`uvicorn --port 8000` |
| **Compose 容器内** | uvicorn **`8001`** | nginx **`8080`** | `scripts/docker-entrypoint.sh` / `nginx.conf` |
| **Compose 宿主映射** | `127.0.0.1:8000:8001` | `127.0.0.1:5173:8080` | 默认仅本机可访问 |
| **健康检查** | `GET /api/v1/health` @ `127.0.0.1:8001` | — | **不是** `/health`，**不是** curl |

历史 bug（已修）：

- compose 曾 `8000:8000` 但 entrypoint 听 `8001` → 映射错位
- healthcheck 曾 `curl .../health`：slim 无 curl + 路径错误
- 数据库路径曾写成 `fuqing.duckdb`，与真实 `fuqing_crm.duckdb` 漂移

容器内数据库路径统一为：

```text
/app/data/processed/fuqing_crm.duckdb
```

## 2. Workers 默认 1

```bash
UVICORN_WORKERS=1   # Dockerfile ENV + compose environment + entrypoint 默认
```

原因：

1. DuckDB 文件锁 / 连接与多 worker 进程模型默认不兼容
2. `FQ_SINGLE_USER_V2=1` 强制单 worker（会话一致性）；若 `UVICORN_WORKERS!=1` 则 entrypoint **FATAL**
3. 需要水平扩展时显式设 `UVICORN_WORKERS=N` 并回归验证写路径

## 3. 健康检查（无 curl）

```yaml
healthcheck:
  test:
    [
      "CMD",
      "python",
      "-c",
      "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/api/v1/health', timeout=5)",
    ]
```

## 4. 基础镜像 pin

| 镜像 | 当前 pin | 说明 |
|------|----------|------|
| 后端 | `python:3.13.5-slim-bookworm` | minor 固定；digest 见下 |
| 前端 builder | `node:22.17.0-alpine` | 构建阶段 |
| 前端 runtime | `nginxinc/nginx-unprivileged:1.27-alpine` | 静态托管，**禁止**生产 `vite preview` |

### 人工锁定 digest（推荐运维执行）

```bash
# 拉取后记录 RepoDigests，写入本文件表格并 PR
docker pull python:3.13.5-slim-bookworm
docker inspect --format='{{index .RepoDigests 0}}' python:3.13.5-slim-bookworm

docker pull node:22.17.0-alpine
docker inspect --format='{{index .RepoDigests 0}}' node:22.17.0-alpine

docker pull nginxinc/nginx-unprivileged:1.27-alpine
docker inspect --format='{{index .RepoDigests 0}}' nginxinc/nginx-unprivileged:1.27-alpine
```

| 镜像 tag | digest（人工填写） | 日期 |
|----------|-------------------|------|
| `python:3.13.5-slim-bookworm` | _待填_ | |
| `node:22.17.0-alpine` | _待填_ | |
| `nginxinc/nginx-unprivileged:1.27-alpine` | _待填_ | |

锁定后 Dockerfile 可改为：

```dockerfile
FROM python:3.13.5-slim-bookworm@sha256:<digest>
```

## 5. .dockerignore

- **根** `.dockerignore`：排除 `.env*`、`data/`、`node_modules`、导出、本地日志、大文档
- **frontend-vue3/.dockerignore**：排除 `node_modules`/`dist`/`e2e`/本地 env

## 6. 前端生产形态

- 多阶段：`npm run build` → 拷贝 `dist` 到 **nginx-unprivileged**
- **禁止**生产入口使用 `vite preview`（仅本地 `npm run preview` 可选）
- API 反代：`nginx.conf` → `http://backend:8001`
- nginx 将 `X-Forwarded-For` **覆盖**为直接客户端地址；backend 只信任 compose 网段/loopback，由 Uvicorn `--forwarded-allow-ips` 解析

## 7. 冒烟

```bash
docker compose build
docker compose up -d
curl -sS http://localhost:8000/api/v1/health
# 前端静态: http://localhost:5173
```

CI `docker-smoke` 必须：

1. 用 `scripts/ci/seed_e2e_duckdb.py` 生成微型 DuckDB；
2. 真正启动 backend/frontend 容器；
3. 检查 backend health、前端 HTTP 与强制 CSP；
4. 结束后清理本次 compose 资源。

**禁止**：为冒烟复制或挂载生产 DuckDB。
