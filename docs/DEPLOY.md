# 芙清 CRM — 部署指南

> 最后更新: 2026-05-27

## Mac 开发环境

### 启动后端
```bash
cd "/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics"
export HEALTH_API_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
PYTHONPATH="$(pwd)" nohup ~/.workbuddy/binaries/python/envs/default/bin/python -m uvicorn backend.main:app \
  --host 0.0.0.0 --port 8001 --reload --reload-dir backend >> /tmp/fuqin-crm-backend.log 2>&1 &
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

## Windows 生产服务器

### 架构
- Mac(开发+ETL) → GitHub → Windows(生产服务器)
- Windows固定IP: `192.168.100.39`
- 同事访问: `http://192.168.100.39:5173`

### 部署步骤
1. Windows安装Python 3.13 + Node.js 22
2. `git clone` 项目到 Windows
3. `pip install -r requirements.txt`
4. `cd frontend-vue3 && npm install && npm run build`
5. 前端用 `npx serve dist` 托管静态文件
6. 后端用 `uvicorn backend.main:app --host 0.0.0.0 --port 8001`
7. 防火墙放行 5173 和 8001 端口
8. 开机自启：`start.bat` 放 Windows 启动文件夹

### 代码同步
```bash
# Mac 推送
git push origin main

# Windows 拉取
git pull origin main
```

### ETL 在 Windows 上运行
```bash
PYTHONPATH="%cd%" python scripts/run_etl.py --update
```

详细步骤见 `docs/windows-deploy-sop.md`

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
