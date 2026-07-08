# Windows 11 部署 - 已知问题与解决方案 (Sprint 205+ Windows deploy 实战沉淀)

> **本文件记录 Sprint 205+ Windows 11 部署完整过程中踩过的 6 个坑 + 解决方案。**
> **下次 mac → Windows 部署时,直接按这个清单走,避免重复踩坑。**
> **配套:`D:\fuqin-date\setup.bat` 已经集成所有 fix(纯 ASCII v2)。**

---

## 部署终态(Sprint 205+ 验证通过)

| 项 | 值 |
|---|---|
| 部署时间 | 2026-07-07 |
| 工具链 | Python 3.14.4 + Node 20.18.1 + Git 2.55.0 + VSCode 1.127.0 + DuckDB v1.5.4 |
| 数据大小 | 137.25 GB(124GB mac + 13GB Windows 上生成) |
| 部署根 | `D:\fuqin-date\` |
| 项目根 | `D:\fuqin-date\fuqing-crm-analytics\` |
| 验证状态 | backend :8000 ✅ / frontend :5173 ✅ / DuckDB db_size ✅ |

---

## 6 个 fix(实战沉淀,必须应用)

### Fix 1:Python 升到 3.14.4(不是 3.11)

**踩坑**:`setup.bat` v1 要求 Python 3.11+,用户装了 3.11.9,**语法错误**:
- `f-string` 内反斜杠(f"\n{var}\n")
- `threading.RLock | None` 运行时类型注解(Python 3.12+ 支持,3.11 不支持)

**解决方案**:
- Windows 必须装 **Python 3.14.4**(跟 mac 一致)
- 下载:`https://www.python.org/downloads/windows/` 选 3.14.4
- ⚠️ 安装时必勾 "Add Python.exe to PATH"

**永久规则**:**Sprint 205+ 后续,Windows 部署要求 Python 3.14.4,不再用 3.11/3.12**。

---

### Fix 2:npm install 加 `--legacy-peer-deps`

**踩坑**:`npm install` 默认严格模式,前端依赖存在 peer dependency 冲突,直接 fail。

**解决方案**:
```bash
npm install --legacy-peer-deps
npm run build
```

**永久规则**:**Sprint 205+ 后续,所有 Windows 部署 npm install 必须加 --legacy-peer-deps**。

---

### Fix 3:.env 用 Python UTF-8 替换,不用 PowerShell

**踩坑**:`setup.bat` v1 用 PowerShell `Get-Content` + 字符串替换,默认 GBK 编码,**破坏 .env 里的 UTF-8 中文注释**,后端 Python 读 .env 解码失败。

**解决方案**:
```python
# 用 Python 以 UTF-8 读取 + 替换
python -c "
import re
content = open('.env', 'r', encoding='utf-8').read()
content = content.replace('/Users/hutou/Desktop/fuqin-date/', 'D:/fuqin-date/')
open('.env', 'w', encoding='utf-8').write(content)
"
```

**永久规则**:**Sprint 205+ 后续,任何 .env patch 必须用 Python UTF-8 读写,禁用 PowerShell 字符串替换**。

---

### Fix 4:Windows 缺 Unix `resource` 模块 → 补 stub

**踩坑**:pytest 运行时调用 `import resource`(Unix-only 模块),Windows 没装,导致 pytest baseline 失败。

**解决方案**:
```python
# 在 .venv\Lib\site-packages\resource.py 创建空 stub
# 文件内容:
"""Windows stub for Unix resource module."""
class error(Exception): pass
def getrlimit(x): return (0, 0)
def setrlimit(x, y): pass
def getrusage(x): return type('usage', (), {'ru_maxrss': 0, 'ru_utime': 0, 'ru_stime': 0, 'ru_ixrss': 0, 'ru_idrss': 0, 'ru_isrss': 0, 'ru_minflt': 0, 'ru_majflt': 0, 'ru_nswap': 0, 'ru_inblock': 0, 'ru_oublock': 0, 'ru_msgsnd': 0, 'ru_msgrcv': 0, 'ru_nsignals': 0, 'ru_nvcsw': 0, 'ru_nivcsw': 0})()
def getpagesize(): return 4096
```

**永久规则**:**Sprint 205+ 后续,任何 Windows 部署必须先在 .venv\Lib\site-packages\resource.py 补 stub**。

---

### Fix 5:NSSM AppEnvironmentExtra 每个变量独立参数

**踩坑 1**:`nssm set fuqing-uvicorn AppEnvironmentExtra "PYTHONIOENCODING=utf-8 PYTHONPATH=D:/..."` 整段字符串 → NSSM 解析错误,环境变量没设上。

**解决方案**:
```bat
REM 错误写法 ❌
%NSSM% set fuqing-uvicorn AppEnvironmentExtra "PYTHONIOENCODING=utf-8 PYTHONPATH=D:/..."

REM 正确写法 ✅
%NSSM% set fuqing-uvicorn AppEnvironmentExtra PYTHONIOENCODING=utf-8 PYTHONPATH=D:/...
```
**关键**:每个 env var 是独立参数,不用引号包整段。

**踩坑 2**:前端服务用 `npm.cmd` 跑 `vite preview` → Windows 上 npm.cmd 退出后 vite 子进程被 kill,服务挂了。

**解决方案**:
```bat
REM 错误写法 ❌
%NSSM% install fuqing-frontend "C:\Program Files\nodejs\npm.cmd" "run preview -- ..."

REM 正确写法 ✅
%NSSM% install fuqing-frontend "C:\Program Files\nodejs\node.exe" "D:\fuqin-date\fuqing-crm-analytics\frontend-vue3\node_modules\vite\bin\vite.js" "preview" "--port" "5173" "--host" "0.0.0.0" "--strictPort"
%NSSM% set fuqing-frontend AppDirectory "D:\fuqin-date\fuqing-crm-analytics\frontend-vue3"
```
**关键**:`node.exe` 直接跑 `vite.js`,不经过 `npm.cmd`。

**永久规则**:**Sprint 205+ 后续,Windows NSSM 服务 env vars 必须独立参数,前端服务用 node.exe + vite.js,不通过 npm.cmd**。

---

### Fix 6:setup.bat 改为离线 + 简化版

**踩坑 1**:`setup.bat` 在 PowerShell 无 TTY 环境(如 Python subprocess 调用)卡死 → 必须用户**双击运行**。

**解决方案**:`setup.bat` 改写时不依赖 TTY,用 `pause` 替代,允许后台跑。

**踩坑 2**:原脚本有 `pip install --upgrade pip` + 在线下载 NSSM,容易在企业网络失败。

**解决方案**:
- 跳过 `pip install --upgrade pip`(用 .venv 自带 pip 即可)
- NSSM zip 提前下载好放在 `D:\fuqin-date\tools\nssm.zip`,setup.bat 不再下载

**永久规则**:**Sprint 205+ 后续,setup.bat 必须是离线版本,不下载任何东西**。

---

## 部署命令速查(下次部署直接复制)

### mac 端(打包)
```bash
# 1. 验证 pytest baseline
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics
PYTHONPATH=$(pwd) pytest backend/tests/ -q --tb=line 2>&1 | tail -5

# 2. mac 端开 SSH
sudo systemsetup -setremotelogin on
ifconfig en0 | grep "inet " | awk '{print $2}'  # 记 IP
```

### Windows 端(部署)
```powershell
# 1. 装 5 工具(Python 3.14.4 / Node 20 / Git / VSCode / DuckDB)
winget install DuckDB.cli  # 单独跑这 1 个,其他手动装

# 2. 测连接 + 建目录
Test-NetConnection -ComputerName <MAC_IP> -Port 22
mkdir D:\fuqin-date

# 3. Git Bash 跑 rsync 同步
cd /d/fuqin-date
rsync -avhP --progress --exclude='.venv' --exclude='node_modules' --exclude='.pytest_cache' --exclude='.ruff_cache' --exclude='__pycache__' --exclude='.DS_Store' --exclude='.gstack' --exclude='.codegraph' --exclude='*.pyc' --exclude='frontend-vue3/dist' --exclude='.githooks/__pycache__' hutou@<MAC_IP>:/Users/hutou/Desktop/fuqin-date/ /d/fuqin-date/

# 4. 跑 setup.bat
D:\fuqin-date\setup.bat

# 5. 验证
curl http://localhost:8000/api/v1/health
curl http://localhost:5173/
```

---

## 相关文件

| 文件 | 作用 |
|---|---|
| `D:\fuqin-date\setup.bat` | v2 完整版(集成 6 个 fix) |
| `D:\fuqin-date\run-etl.bat` | ETL 跑批(纯 ASCII) |
| `D:\fuqin-date\ai-help.bat` | AI 诊断(结构化输出) |
| `D:\fuqin-date\sync-from-mac.bat` | 偶尔从 mac 同步代码 |
| `D:\fuqin-date\fuqing-crm-analytics\scripts\start_uvicorn.py` | NSSM 启动 wrapper |
| `D:\fuqin-date\fuqing-crm-analytics\docs\OPERATIONS.md` | 运维手册 |
| `D:\fuqin-date\fuqing-crm-analytics\docs\DISASTER-RECOVERY.md` | 灾难恢复 |
| `D:\fuqin-date\fuqing-crm-analytics\docs\WINDOWS-DEPLOY-KNOWN-ISSUES.md` | **本文件** |

---

## L4.70 PC2 端 .env 1 行 fix (Sprint 205+ 真业务触发)

### 问题
- L4.69 (commit f8fc8bc) 治本 RFM 雪崩时, `dual_conn.py READ_POOL_SIZE` 从默认 5 hardcoded 改 2
- 副作用: dashboard 页面 (人群看板 / 指标看板 YoY) 5 个并行接口被池化阻塞, 总时长 30s+ (前端 axios timeout 30s)
- 7/8 用户报"全部 30s timeout"

### 治本 (PC2 端 1 行 .env 修复, 0 业务代码改动)

```ini
# C:\fuqin-date\fuqing-crm-analytics\.env 加:
FQ_READ_POOL_SIZE=5
```

恢复 7/7 默认值。**RFM 路径走 `_run_rfm_period_serial` 自己 new conn, 不通过此 pool, L4.69 治本完好**。

### PC2 端 9 接口验证 (跟 L4.69 验证同模式)

- 5 个简单接口 (visitor/summary / metrics/overview / audience/summary / customer-health/config / rfm/r-flow) 全 < 1.1s
- 5 个 YoY 接口 (人群看板场景, 5 并行) 全 < 1.1s
- 后端启动 147MB (L4.65.1 治本), ANALYZE 后稳态 1612MB, watchdog v2 1.8GB 兜底

### Mac 端 .env 配套 (本机)

- Mac 端不显式设 `FQ_READ_POOL_SIZE`, 默认 5 (跟 PC2 端 .env 显式 5 配套)
- 配套永久规则: 见 L4.69 永久规则化 (CLAUDE.md line "L4.69 (架构)") + Sprint 205+ L4.69 close memory
- 7/17 运营接管后: 跨 sprint 留尾 (跟 L4.57 + L4.58 + L4.59 1:1 stable), 7/16 离职前必把 .env 文档化

### L4.71 RFM 业务治本 (7/16 后接手立项, 跟 L4.56 POC 留尾 1:1 stable)

- 列存覆盖索引 (L4.70 D 方案 PC2 验证失败已回退)
- ETL 预计算物化视图
- 改用 `user_rfm` 1.5GB 预计算表
- ClickHouse POC (L4.56 启动条件: DuckDB > 200GB / P95 > 30s 持续 1 周 / 5+ 业务分析师并发取数)

---

**最后更新:2026-07-08  |  Sprint 205+ Windows deploy + L4.70 PC2 .env 实战沉淀**
