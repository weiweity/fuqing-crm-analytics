# 芙清 CRM — 部署指南

> 最后更新: 2026-05-27

## Mac 开发环境

### 启动后端
```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
PYTHONPATH="$(pwd)" nohup ~/.workbuddy/binaries/python/envs/default/bin/python -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8000 --reload --reload-dir backend >> /tmp/fuqin-crm-backend.log 2>&1 &
```

### 启动前端
```bash
cd frontend-vue3 && npm run dev
```

### 运行ETL
```bash
PYTHONPATH="$(pwd)" ~/.workbuddy/binaries/python/envs/default/bin/python scripts/run_etl.py --update
```

### 跑测试
```bash
PYTHONPATH="$(pwd)" ~/.workbuddy/binaries/python/envs/default/bin/python -m pytest backend/tests/ -v
```

## Docker（Phase 7，待实现）

```yaml
# docker-compose.yml（规划中）
services:
  backend:
    build: .
    ports: ["8001:8001"]
    volumes:
      - ./data:/app/data
      - ${SHOP_DATA_SOURCE}:/data/sources/shop:ro
    env_file: .env

  frontend:
    build: ./frontend-vue3
    ports: ["5173:80"]
    depends_on: [backend]
```
