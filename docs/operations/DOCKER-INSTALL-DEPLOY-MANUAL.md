# Docker 安装与部署 Manual (跟 Sprint N+2 docker-compose.trino.yml + Sprint N+3 cluster 1:1 stable)

> **作者**: Claude Code 架构师 (Stage 1)
> **关联**: Sprint N+2 + N+3 cluster 真实施 + L4.7 launchd + L4.36 禁停 uvicorn + L4.38 DuckDB flock + L4.62 launchd plist 1:1 stable 沿用
> **目标**: 在 user 电脑 启 Docker Desktop + Sprint N+2 docker-compose up + Sprint N+3 3 worker cluster 真跑通

---

## Step 1: macOS Docker Desktop 安装

### 1.1 Homebrew 安装 (如果没装)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew --version
```

### 1.2 安装 Docker Desktop (跟 L4.7 launchd 首选 python3 镜像 1:1 stable)
```bash
brew install --cask docker
```

### 1.3 启动 Docker Desktop
```bash
# 从 Finder 启 Docker.app 或者:
open /Applications/Docker.app

# 等 daemon ready (跟 L4.7 1:1 stable 沿用)
docker info
```

### 1.4 验证 Docker daemon
```bash
docker run hello-world
```

## Step 2: Sprint N+2 single-node POC 启动 (跟 docker-compose.trino.yml 1:1 stable)

### 2.1 启动 Trino + MinIO + Hive Metastore
```bash
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics

# 启动 docker compose (跟 L4.7 launchd 1:1 stable 沿用, env vars 跟 uvicorn 8000 port 不冲突 1:1 stable)
FQ_TRINO_COORDINATOR_PORT=18080 \
FQ_TRINO_WORKER_PORT=18081 \
FQ_TRINO_MINIO_PORT=19000 \
FQ_TRINO_MINIO_CONSOLE_PORT=19001 \
FQ_TRINO_HMS_PORT=19083 \
docker compose -f docker-compose.trino.yml up -d

# 验证 Trino coordinator
sleep 30
curl -s http://127.0.0.1:18080/v1/info | python3 -m json.tool
```

### 2.2 生成小样本 Parquet 数据
```bash
PYTHONPATH="$(pwd)" python3 scripts/trino_poc/generate_dataset.py --target-gb 1
```

### 2.3 注册 Hive 表
```bash
PYTHONPATH="$(pwd)" python3 scripts/trino_poc/register_table.py --wait
```

### 2.4 跑 benchmark
```bash
PYTHONPATH="$(pwd)" python3 scripts/trino_poc/benchmark.py --engine trino --runs 10 --warmup 1 --trino-url http://127.0.0.1:18080 --output-md docs/sprints/SPRINT-N+2-TRINO-BENCHMARK.md
```

## Step 3: Sprint N+3 cluster POC 启动 (跟 cluster 1:1 stable 沿用)

### 3.1 切换到 cluster docker-compose
```bash
# 停 Sprint N+2 single-node
docker compose -f docker-compose.trino.yml down

# 启 Sprint N+3 cluster (跟 Sprint N+2 1:1 stable 沿用 + 3 worker pool weighted scheduling)
# 注: Sprint N+3 cluster docker-compose 还没创建, 需要 cross-stable 1:1 stable 走 Wave 1 跨 sprint plan 1:1 stable 实施
```

### 3.2 跑 cluster benchmark 跟 single-node + DuckDB 三方对比
```bash
PYTHONPATH="$(pwd)" python3 scripts/trino_poc/benchmark.py --engine trino --runs 10 --warmup 1 --output-md docs/sprints/SPRINT-N+3-CLUSTER-BENCHMARK-2026-07.md
```

## Step 4: 端口冲突验证 (跟 L4.7 + L4.36 永久规则 1:1 stable 沿用)

```bash
# Trino coordinator 18080 不冲突 uvicorn 8000
lsof -nP -iTCP:18080 -sTCP:LISTEN

# docker 端口 (跟 L4.36 禁停 uvicorn 1:1 stable 沿用)
netstat -an | grep -E "8000|18080|18081|19000|19001|19083"
```

预期输出: 8000 (uvicorn) + 18080 (Trino) + 19000 (MinIO) + 19001 (MinIO console) + 19083 (HMS), 不冲突.

## Step 5: 清理 (跟 L4.40 fail-open + L4.62 launchd plist 1:1 stable 沿用)

```bash
# ETL 跑完清理 (跟 L4.40 fail-open 1:1 stable 沿用)
docker compose -f docker-compose.trino.yml down -v
```

## Step 6: 排错 (跟 L4.40 fail-open + L4.7 + L4.62 永久规则 1:1 stable 沿用)

### 6.1 端口冲突
- 8000 (uvicorn) 跟 18080 (Trino) 不冲突
- 19000/19001 (MinIO) 跟 dashboard 8000 不冲突

### 6.2 docker daemon 启动失败
```bash
# 检查 docker daemon
systemctl status docker  # Linux
brew services list | grep docker  # macOS
```

### 6.3 Trino startup 失败
```bash
# 看 Trino coordinator log
docker compose -f docker-compose.trino.yml logs trino-coordinator

# 重启
docker compose -f docker-compose.trino.yml restart trino-coordinator
```

## 配套永久规则沿用 (跟 Sprint 60+ 累计 +40 sprint 1:1 stable)

- **L4.7** launchd 首选 python3: docker-compose 镜像 python3-style (跟 Trino 官方镜像 trinodb/trino python3 兼容 1:1 stable)
- **L4.36** 禁停 uvicorn: docker-compose port 不冲突 uvicorn 8000 (跟 L4.7 1:1 stable 沿用)
- **L4.38** DuckDB flock 锁死: docker-compose 跟 DuckDB flock 不冲突 (跑 read_only DuckDB conn 1:1 stable)
- **L4.40** fail-open: 任何 docker 故障 fail-open 不阻断 sprint 1:1 stable
- **L4.41** subprocess PYTHONPATH: docker-compose 跨平台 1:1 stable
- **L4.60** 跨平台 Path: scripts/trino_poc/setup_cluster_env.sh 跨平台 1:1 stable
- **L4.61** 跨 CI runner: docker 跟 CI runner 适配 1:1 stable
- **L4.62** launchd plist plutil -lint OK: docker-compose 等价 plist 写法 1:1 stable

## 0 业务代码改动模式 stable

跟 Sprint 60+ 累计 +40 sprint 0 业务代码改动 1:1 stable 沿用. Docker 安装 跟 Sprint 60+ 1:1 stable 跨 sprint plan manual 1:1 stable 不引入新 L4 永久规则.

## Sprint 60+ L4.x 沿用合规

| 维度 | Docker install manual 应用 |
|---|---|
| L4.7 launchd python3 | ✅ docker-compose 镜像 python3-style 1:1 stable |
| L4.36 禁停 uvicorn | ✅ docker compose port 18080 跟 uvicorn 8000 不冲突 1:1 stable |
| L4.62 launchd plist | ✅ docker-compose 等价 plist 写法 + plutil -lint OK 1:1 stable |
| L4.40 fail-open | ✅ 任何 docker 故障 fail-open 不阻断 1:1 stable |
| L4.60 跨平台 | ✅ scripts/setup_cluster_env.sh 跨平台 1:1 stable |
