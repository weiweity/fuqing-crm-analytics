# 芙清CRM - Windows服务器部署SOP

> 本文档供Windows电脑上的AI助手执行，一步步完成部署。
> Windows固定IP: 192.168.100.39 | 同事访问地址: http://192.168.100.39:5173

---

## Phase 1: 安装软件（约30分钟）

### 1.1 安装 Python 3.13

- 下载地址: https://www.python.org/downloads/
- 安装时 **勾选 "Add Python to PATH"**
- 安装完成后打开 CMD 验证:

```cmd
python --version
pip --version
```

### 1.2 安装 Node.js 18+

- 下载地址: https://nodejs.org/ (选LTS版本)
- 安装完成后验证:

```cmd
node --version
npm --version
```

### 1.3 安装 Git

- 下载地址: https://git-scm.com/download/win
- 安装时全部默认选项
- 安装完成后验证:

```cmd
git --version
```

### 1.4 配置 Git SSH Key（连接GitHub）

```cmd
:: 生成SSH密钥
ssh-keygen -t ed25519 -C "你的邮箱"
:: 一路回车（默认路径，不设密码）

:: 查看公钥
type %USERPROFILE%\.ssh\id_ed25519.pub
```

把公钥内容复制到 GitHub → Settings → SSH and GPG keys → New SSH key

验证连接:
```cmd
ssh -T git@github.com
```

看到 "Hi weiweity!" 表示成功。

---

## Phase 2: 克隆代码（约5分钟）

```cmd
:: 切到D盘
D:

:: 克隆仓库
git clone git@github.com:weiweity/fuqing-crm-analytics.git

:: 进入项目
cd fuqing-crm-analytics
```

---

## Phase 3: 安装依赖（约10分钟）

### 3.1 后端Python依赖

```cmd
cd D:\fuqing-crm-analytics
pip install -r requirements.txt
```

### 3.2 前端Node依赖 + 构建

```cmd
cd D:\fuqing-crm-analytics\frontend-vue3
npm install
npm run build
```

构建完成后会生成 `dist/` 目录，这就是前端静态文件。

---

## Phase 4: 拷贝原始数据（首次需要，约3GB）

**只需要拷贝原始Excel数据，不需要拷贝DuckDB**（Windows上跑ETL会自动生成DuckDB）。

### 4.1 Mac开启文件共享

1. Mac上：「系统设置 → 通用 → 共享 → 文件共享」→ 开启
2. 点击「选项」→ 勾选你的用户账号
3. 把 `~/Desktop/fuqin date/芙清CRM数据库/` 加入共享文件夹（点「+」添加）

### 4.2 Windows拉取数据

1. Mac上查IP：打开终端输入 `ifconfig | grep "inet "` 找到内网IP
2. Windows上按 `Win+R` → 输入 `\\Mac的IP地址` → 回车
3. 输入Mac的用户名和密码
4. 把 `芙清CRM数据库` 整个文件夹复制到 `D:\芙清CRM数据库\`

**约3GB，内网传输5-10分钟。**

### 4.3 不需要拷贝的内容

| 文件 | 大小 | 原因 |
|------|------|------|
| `fuqing_crm.duckdb` | 35GB | ❌ Windows跑ETL自动生成 |
| `fuqing_crm.duckdb.backup` | 7GB | ❌ 旧备份 |
| `taoke_file_cache.json` | 60MB | ❌ 缓存，ETL自动生成 |

### 4.4 Windows跑全量ETL生成DuckDB

```cmd
cd D:\fuqing-crm-analytics
set PYTHONPATH=D:\fuqing-crm-analytics
python scripts/run_etl.py
```

**注意**: 首次全量ETL可能需要1-2小时（取决于Windows性能），请耐心等待。
完成后会在 `data/processed/` 下生成 `fuqing_crm.duckdb`。

---

## Phase 5: 配置环境变量（约5分钟）

在 `D:\fuqing-crm-analytics\` 目录下创建 `.env` 文件:

```env
# ─────────────────────────────────────────────────────────────
# 芙清CRM - Windows服务器环境变量
# ─────────────────────────────────────────────────────────────

# 原始数据路径（改成Windows实际路径）
SHOP_DATA_SOURCE=D:\芙清CRM数据库\店铺数据库
MEMBER_DATA_SOURCE=D:\芙清CRM数据库\会员数据库
SPU_MAPPING_SOURCE=D:\芙清CRM数据库\天猫_spu单品匹配表_数据表.csv
SHOP_STATUS_SOURCE=D:\芙清CRM数据库\订单状态刷新
VISITOR_DATA_SOURCE=D:\芙清CRM数据库\店铺流量数据库
CAMPAIGN_SCHEDULE_SOURCE=D:\芙清CRM数据库\芙清全年平台活动节奏 - Sheet2.csv

# DMP数据（如果没有可以不填）
DMP_DATA_DIR=D:\work plat\DMP_test_package\core

# DuckDB数据库路径
DUCKDB_PATH=D:\fuqing-crm-analytics\data\processed\fuqing_crm.duckdb

# API安全密钥（随便生成一个长字符串）
HEALTH_API_KEY=替换为一个随机长字符串
```

**验证**: 确认上面每个路径对应的文件夹/文件都存在。

---

## Phase 6: 创建启动脚本

在 `D:\fuqing-crm-analytics\` 目录下创建 `start.bat`:

```bat
@echo off
chcp 65001 >nul
title 芙清CRM服务

cd /d D:\fuqing-crm-analytics

:: 拉取最新代码（静默，不阻塞）
git pull origin main

:: 启动后端API（端口8001）
start "芙清CRM-后端" /min cmd /c "cd /d D:\fuqing-crm-analytics && set PYTHONPATH=D:\fuqing-crm-analytics && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001"

:: 等后端启动
timeout /t 3 /nobreak >nul

:: 启动前端服务（端口5173，serve静态文件）
start "芙清CRM-前端" /min cmd /c "cd /d D:\fuqing-crm-analytics\frontend-vue3 && npx serve dist -l 5173 -s"

echo.
echo ========================================
echo   芙清CRM服务已启动
echo   前端: http://localhost:5173
echo   后端: http://localhost:8001
echo   同事访问: http://192.168.100.39:5173
echo ========================================
echo.
echo 关闭此窗口不会停止服务
echo 要停止服务请关闭后端和前端的命令行窗口
echo.
pause
```

---

## Phase 7: 设置开机自启

1. 按 `Win+R`，输入 `shell:startup`，回车
2. 右键 → 新建 → 快捷方式
3. 位置填: `D:\fuqing-crm-analytics\start.bat`
4. 名称: `芙清CRM服务`
5. 完成

以后Windows开机就会自动启动服务。

---

## Phase 8: 验证（约5分钟）

### 8.1 本机验证

- 浏览器打开 http://localhost:5173 → 应该看到芙清CRM界面
- 浏览器打开 http://localhost:8001/docs → 应该看到FastAPI文档

### 8.2 同事电脑验证

- 同事浏览器打开 http://192.168.100.39:5173 → 应该看到芙清CRM界面
- 如果打不开，检查Windows防火墙是否放行了5173和8001端口

### 8.3 防火墙放行（如果同事访问不了）

```cmd
:: 放行5173端口
netsh advfirewall firewall add rule name="芙清CRM前端" dir=in action=allow protocol=TCP localport=5173

:: 放行8001端口
netsh advfirewall firewall add rule name="芙清CRM后端" dir=in action=allow protocol=TCP localport=8001
```

---

## 日常运维SOP

### Mac改代码后

```
Mac:  git add . && git commit -m "改了什么" && git push
Windows: 重启 start.bat（会自动 git pull）
```

### 新的Excel数据

```
1. Mac上拿到新Excel文件
2. 拷贝到Windows D:\芙清CRM数据库\ 对应目录
3. Windows上跑ETL增量:
   cd D:\fuqing-crm-analytics
   set PYTHONPATH=D:\fuqing-crm-analytics
   python scripts/run_etl.py --update
```

### 如果Windows增量ETL跑不动

```
1. Mac上跑ETL增量
2. 把更新后的DuckDB文件拷贝到Windows对应位置
3. 重启Windows后端服务
```

---

## 注意事项

1. **DuckDB版本一致性**: Windows上 `pip install duckdb` 的版本必须和Mac一致，否则数据库文件格式不兼容
2. **端口冲突**: 确保8001和5173端口没被其他程序占用
3. **Windows更新重启**: 设置Windows更新不在工作时段自动重启
4. **数据安全**: .env文件不要提交到Git（已在.gitignore中排除）
5. **SSH Key安全**: Windows上的SSH Key不要泄露给他人
