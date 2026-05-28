# 芙清 CRM — 部署指南

> 最后更新: 2026-05-28

## Mac 开发环境

### 启动后端
```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
# FQ_CRM_PASSWORDS 已在 .env 中配置，无需额外导出；未配置时启动自动生成随机密码
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

## Docker（已就绪）

前端使用非特权 nginx 镜像（nginxinc/nginx-unprivileged:alpine），后端以非 root 用户运行。

```yaml
# docker-compose.yml
services:
  backend:
    build: .
    ports: ["8000:8000"]
    volumes:
      - ./data:/app/data
      - ${SHOP_DATA_SOURCE:-./data/sources/shop}:/data/sources/shop:ro
    env_file: .env
    restart: unless-stopped

  frontend:
    build: ./frontend-vue3
    ports: ["5173:8080"]
    depends_on: [backend]
    restart: unless-stopped
```

### 安全说明

- API 响应包含安全头：X-Frame-Options / X-Content-Type-Options / X-XSS-Protection
- 审计日志自动 HMAC 签名（AUDIT_LOG_SECRET 未配置时自动生成密钥）
- 登录密码通过 `.env` 的 `FQ_CRM_PASSWORDS` 配置；bcrypt 哈希 + 8h TTL + 5 次限速锁
