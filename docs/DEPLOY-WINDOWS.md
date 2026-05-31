# Windows 服务器部署指南

## 环境准备

### 1. 安装 Python 3.14

```powershell
# 从 python.org 下载 Windows installer
# 安装时勾选 "Add Python to PATH"

# 验证安装
python --version  # 应显示 3.14.x
```

### 2. 安装依赖

```powershell
cd fuqing-crm-analytics

# 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 安装 DuckDB（Windows 版本）
pip install duckdb
```

### 3. 配置环境变量

```powershell
# 创建 .env 文件
Set-Content .env @"
HEALTH_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
DUCKDB_PASSWORD=your_password_here
CORS_ORIGINS=http://localhost:80,http://your-domain.com
"@
```

## 部署后端

### 方式一：直接运行（简单）

```powershell
$env:PYTHONPATH = Get-Location
$env:HEALTH_API_KEY = Get-Content .env | Select-String "HEALTH_API_KEY" | ForEach-Object { $_.Line.Split("=")[1] }

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 方式二：Windows Service（推荐）

使用 NSSM (Non-Sucking Service Manager) 将后端注册为 Windows 服务：

```powershell
# 1. 下载 NSSM
# https://nssm.cc/download

# 2. 注册服务
nssm install fuqing-crm-backend

# 3. 配置参数
Path: C:\Python314\python.exe
Startup directory: C:\fuqing-crm-analytics
Arguments: -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4

# 4. 设置环境变量
nssm set fuqing-crm-backend AppEnvironmentExtra PYTHONPATH=C:\fuqing-crm-analytics;HEALTH_API_KEY=your_key_here

# 5. 启动服务
nssm start fuqing-crm-backend
```

### 方式三：Docker（最干净）

```powershell
# 1. 构建镜像
docker build -t fuqing-crm .

# 2. 运行容器
docker run -d -p 8000:8000 --env-file .env fuqing-crm
```

## 部署前端

### 1. 构建静态文件

```powershell
cd frontend-vue3
npm install
npm run build

# 产物在 dist/ 目录
```

### 2. Nginx 配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root C:/fuqing-crm-analytics/frontend-vue3/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

## 数据迁移

### 1. 导出数据

```bash
# 在 Mac 上执行
cp data/fuqing_crm.duckdb /Volumes/USB/backup/
```

### 2. 导入数据

```powershell
# 在 Windows 上执行
copy C:\backup\fuqing_crm.duckdb C:\fuqing-crm-analytics\data\
```

## 生产环境检查清单

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 关闭 --reload | ☐ | 生产环境不要用 reload |
| 设置 workers | ☐ | 根据 CPU 核心数设置 |
| HTTPS | ☐ | 使用 Nginx SSL 或 Cloudflare |
| 日志轮转 | ☐ | 防止日志文件无限增长 |
| 备份策略 | ☐ | 定期备份 DuckDB 文件 |
| 防火墙 | ☐ | 只开放 80/443/8000 |
| 监控 | ☐ | 推荐 UptimeRobot 或自建 |

## 常见问题

### 1. DuckDB 文件锁

Windows 下 DuckDB 文件锁更严格，确保只有一个进程访问数据库。

### 2. 路径问题

Windows 路径使用反斜杠，Python 代码中应使用 `pathlib.Path`：

```python
from pathlib import Path
DUCKDB_PATH = Path("data/fuqing_crm.duckdb")
```

### 3. 编码问题

Windows 默认编码可能是 GBK，确保所有文件使用 UTF-8：

```powershell
# PowerShell 设置 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```
