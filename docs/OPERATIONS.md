# 芙清 CRM - 运维手册

> **本文件给 IT / 运维 / AI 远程协助用,不是给运营看。**
> **运营看 `D:\fuqin-date\README-OPERATIONS.md`。**

**最后更新**: 2026-07-11 (Sprint 205+ L4.85.4 登录申请 claim 契约 + 16GB Mac 低内存运行档：create 返回 request_id + claim_token；A approve 不返回 B token；B 带 X-Login-Claim 查询 status 并 POST claim；404/410 为终态)。

## L4.85.4 验证前安全准备

生产口令只从当前终端的 `CRM_PASSWORD` 环境变量读取。不要把实际口令写进命令、文档或 Git；下面函数经 stdin 生成登录 JSON，口令不会出现在 curl 的进程参数中。执行本页登录验证前先运行一次：

```bash
: "${CRM_PASSWORD:?请先在本机安全设置并 export CRM_PASSWORD}"
crm_login_json() {
  CRM_PASSWORD="$CRM_PASSWORD" python3 -c 'import json, os; print(json.dumps({"username": "admin", "password": os.environ["CRM_PASSWORD"]}))'
}
```

## L4.85.3 业务验证 4 件套 (跟 L4.85.3 业务验证 1:1 stable 永久规则化沿用, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 L4.75 v2 lock_timeout_seconds 1:1 stable 永久规则化沿用, 跟之前 L4.85.1 + L4.85.2 业务验证 1:1 stable 永久规则化沿用, 跟 user 7/10 拍板 "都登陆不上去, 写: 账号正在被使用, 请使用申请登录按钮, 我没有任何一个号在线" 1:1 stable 永久规则化沿用)

### 验证 1: uvicorn restart → admin login → 200 (跟 L4.85.3 治本 1:1 stable 永久规则化沿用, 跟 user 7/10 拍板 "没人在线也能登" 1:1 stable 永久规则化沿用)

```bash
ps aux | grep "uvicorn" | grep -v grep | awk '{print $2}' | xargs -I{} kill {} 2>/dev/null
sleep 4
RESP1=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.1" --data-binary @- -w "\nHTTP_CODE:%{http_code}")
echo "Login 1 响应: $RESP1"
```

**预期**: HTTP 200 (ACTIVE_TOKENS 空, 跟 L4.85.3 治本 1:1 stable 永久规则化沿用).

### 验证 2: admin 5 分钟内有 active → login → 409 (跟 L4.85.2 1:1 stable 永久规则化沿用)

```bash
RESP2=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.2" --data-binary @- -w "\nHTTP_CODE:%{http_code}")
echo "Login 2 响应: $RESP2"
```

**预期**: HTTP 409 "账号正在被使用, 请使用申请登录按钮" (跟 L4.85.2 1:1 stable 永久规则化沿用, 跟 L4.85.3 1:1 stable 永久规则化沿用).

### 验证 3: logout → 200 (跟 L4.85.1 logout 1:1 stable 永久规则化沿用)

```bash
TOKEN_A=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" --data-binary @- | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))")
LOGOUT_RESP=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/logout -H "Authorization: Bearer $TOKEN_A" -w "\nHTTP_CODE:%{http_code}")
echo "Logout 响应: $LOGOUT_RESP"
```

**预期**: HTTP 200 (跟 L4.85.1 logout 1:1 stable 永久规则化沿用).

### 验证 4: admin logout 后, login → 200 (跟 L4.85.3 治本核心 1:1 stable 永久规则化沿用, 跟 user 7/10 拍板 "没人在线也能登" 1:1 stable 永久规则化沿用, bug 修复成功)

```bash
RESP3=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.3" --data-binary @- -w "\nHTTP_CODE:%{http_code}")
echo "Login 3 响应: $RESP3"
```

**预期**: HTTP 200 (跟 L4.85.3 治本核心 1:1 stable 永久规则化沿用, bug 修复成功, 跟 user 7/10 拍板 "我没有任何一个号在线" 1:1 stable 永久规则化沿用).

## L4.85.2 业务验证 3 件套 (跟 L4.85.2 业务验证 1:1 stable 永久规则化沿用, 跟 L4.42 立项实证 SOP 1:1 stable 永久规则化沿用, 跟 plan-eng-review 5 维分析 1:1 stable 永久规则化沿用, 跟之前 L4.85.1 业务验证 1:1 stable 永久规则化沿用, 跟 user 7/10 拍板 "我两个设备，同时选择登陆按钮，还是能进入" 1:1 stable 永久规则化沿用)

### 验证 1: admin 同时按登录按钮 → 整合 L4.84 path 跟 L4.85 path (跟 L4.85.2 整合 1:1 stable 永久规则化沿用)

```bash
TOKEN_153=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.153" --data-binary @- | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))")
sleep 1
RESP_201=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.201" --data-binary @- -w "\nHTTP_CODE:%{http_code}")
echo "Token .153: ${TOKEN_153:0:20}..."
echo ".201 login 响应: $RESP_201"
curl -s -o /dev/null -w "Token .153 HTTP %{http_code} (应该 200, L4.85.2 整合后不踢)\n" http://127.0.0.1:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN_153"
```

**预期**: Token .153 HTTP 200 (admin 第一次) + .201 login 响应 HTTP 409 (admin 第二次, 跟 L4.85.2 整合 1:1 stable 永久规则化沿用, **不踢 .153 旧 token**). 跟 L4.85.2 整合 L4.84 path 跟 L4.85 path 1:1 stable 永久规则化沿用, 跟 user 7/10 拍板 "admin 账号只允许登陆一个人" 1:1 stable 永久规则化沿用.

## L4.85.4 登录申请业务验证 3 件套

### 验证 1: admin 第二次直接登录被引导到申请流程 (.153 + .201)

```bash
TOKEN_153=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.153" --data-binary @- | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))")
sleep 1
RESP_201=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.201" --data-binary @- -w "\nHTTP_CODE:%{http_code}")
echo "Token .153: ${TOKEN_153:0:20}..."
echo ".201 login 响应: $RESP_201"
curl -s -o /dev/null -w "Token .153 HTTP %{http_code} (应该 200，A 保持在线等待审批)\n" http://127.0.0.1:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN_153"
```

**预期**: `.201` 第二次直接登录 HTTP 409（提示使用申请登录按钮），`.153` 的 A 端 token 仍 HTTP 200，等待 B 创建申请。

### 验证 2: A 端 login-request 弹窗 + 同意 (L4.85.4 claim 契约)

```bash
TOKEN_ADMIN=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.153" --data-binary @- | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))")
sleep 1
REQ_RESP=$(crm_login_json | curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login-request -H "Content-Type: application/json" -H "X-Forwarded-For: 192.168.100.20" --data-binary @-)
echo "B 端申请: $REQ_RESP"
REQUEST_ID=$(echo "$REQ_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('request_id',''))")
CLAIM_TOKEN=$(echo "$REQ_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('claim_token',''))")
PENDING_RESP=$(curl -s -X GET http://127.0.0.1:8000/api/v1/auth/login-requests/pending -H "Authorization: Bearer $TOKEN_ADMIN")
echo "A 端 pending: $PENDING_RESP"
APPROVE_RESP=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/auth/login-request/$REQUEST_ID/approve" -H "Authorization: Bearer $TOKEN_ADMIN")
echo "A 端 approve（响应不应包含 B token）: $APPROVE_RESP"
curl -s -o /dev/null -w "A 端旧 token HTTP %{http_code} (应该 401, 强制退出)\n" http://127.0.0.1:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN_ADMIN"
```

**预期**: create 返回 `request_id + claim_token`；A 端 pending 看到 B 申请；approve 返回 `{"success":true,"username":"admin"}` 且不含 B 的 bearer token；A 旧 token HTTP 401。内部索引使用 `_PENDING_REQUEST_OWNERS`，`request_id` 本身不是领取凭证。

### 验证 3: B 端 polling /status 后 POST /claim 领取 token

```bash
sleep 1
STATUS_RESP=$(curl -s -X GET "http://127.0.0.1:8000/api/v1/auth/login-request/$REQUEST_ID/status" -H "X-Login-Claim: $CLAIM_TOKEN")
echo "B 端 polling status: $STATUS_RESP"
CLAIM_RESP=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/auth/login-request/$REQUEST_ID/claim" -H "X-Login-Claim: $CLAIM_TOKEN")
TOKEN_B=$(echo "$CLAIM_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))")
curl -s -o /dev/null -w "B 端领取 token HTTP %{http_code} (应该 200)\n" http://127.0.0.1:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN_B"
```

**预期**: GET status 返回 `{"request_id":"...","status":"approved","username":"admin"}`，不返回 token；POST claim 返回 `{"token":"...","username":"admin"}`，重复 claim 在授权仍有效时返回同一 token。

**终态处理**: status 返回 `rejected` / `expired`，或 status / claim 返回 HTTP 404（申请不存在/claim 不匹配/终态记录已清理）/ HTTP 410（申请或授权已失效）时，B 端必须停止 polling、清理本地 `request_id + claim_token` 并重新申请；禁止无限重试。只有 `pending` 才继续 polling。

## L4.85.4 登录链路 focused regression

```bash
cd /Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics
/Users/hutou/homebrew/bin/python3.14 -m pytest backend/tests/test_l4_84_login_evict_previous.py backend/tests/test_l4_85_login_request.py backend/tests/test_l4_85_1_login_request_status.py backend/tests/test_l4_85_2_login_both_paths.py backend/tests/test_l4_85_3_account_active_timeout.py backend/tests/test_l4_85_4_account_handoff.py -v --tb=short
```

**预期**: 全部通过，0 fail；不要依赖固定 case 数量。

---

**业务验证清单（L4.85.4 上线后需按新契约复跑）**:
1. **L4.85.2 admin .153 + .201 同时按登录按钮** → .153 HTTP 200 (admin 第一次) + .201 HTTP 409 (admin 第二次, 跟 L4.85.2 整合 1:1 stable 永久规则化沿用, **不踢 .153 旧 token**) + .153 旧 token HTTP 200 ✅
2. **L4.85.4 admin .153 + .201 直接登录** → .153 HTTP 200（A 保持在线）+ .201 HTTP 409（进入申请流程）
3. **L4.85.4 A 端 login-request 弹窗 + 同意** → create 返回 `request_id + claim_token`；A approve 不含 B token；A 旧 token HTTP 401
4. **L4.85.4 B 端 status + claim** → GET status 带 `X-Login-Claim` 且只返回状态；approved 后 POST claim 领取 token；404/410 终止 polling
5. **L4.85.1 fqsw 账号不冲突** (跟 L4.84 + L4.85 + L4.85.1 1:1 stable 永久规则化沿用) ✅
6. **L4.85.1 polling 自适应** (有 pending → 5s, 无 pending → 30s, 跟 L4.72 dual_conn 1:1 stable 永久规则链配套, 减少 conn 占用 6x) ✅

---

## 一、系统概览

| 项 | 值 |
|---|---|
| OS | Windows 11 |
| Python | 3.11+ |
| Node | 20 LTS |
| 数据库 | DuckDB 0.10+ 单文件 122GB |
| 后端 | FastAPI + Uvicorn (8000 端口) |
| 前端 | Vue3 + Vite (5173 端口) |
| ETL | Python scripts/run_etl.py |
| 进程守护 | NSSM (LocalSystem) |

### 当前 Mac 低内存运行档（16GB 机器）

`scripts/uvicorn_launchd.py` 与本机 `.env` 应保持以下值，避免查询并发与 DuckDB buffer 超卖：

```dotenv
DUCKDB_MEMORY_LIMIT=8GB
DUCKDB_THREADS=4
FQ_READ_POOL_SIZE=2
FQ_READ_CONCURRENCY_LIMIT=2
FQ_READ_MEMORY_LIMIT=3GB
FQ_SINGLE_USER_V2=1
```

口令和 API key 仅存本机 gitignored `.env`；不要在本文档、启动脚本或日志中写明文值。

---

## 二、目录结构

```
D:\fuqin-date\                                    <- 部署根
├── README-OPERATIONS.md                          <- 运营操作手册
├── HANDOVER.md                                   <- 离职交接(密钥)
├── setup.bat                                     <- 一键部署(出大问题重装)
├── run-etl.bat                                   <- 手动 ETL
├── ai-help.bat                                   <- AI 诊断信息收集
├── sync-from-mac.bat                             <- 偶尔从 mac 同步代码
├── 原始数据\                                     <- 运营上传的源数据
│   ├── 店铺数据库\
│   ├── 会员数据库\
│   └── ...
└── fuqing-crm-analytics\                         <- 项目代码
    ├── .env                                      <- 路径配置(自动被 setup.bat 改)
    ├── .venv\                                    <- Python 虚拟环境
    ├── backend\                                  <- FastAPI 业务
    ├── frontend-vue3\                             <- Vue3 前端
    │   ├── node_modules\                        <- npm install 装
    │   └── dist\                                 <- npm run build 产出
    ├── scripts\                                  <- ETL + 工具脚本
    │   ├── start_uvicorn.py                     <- NSSM 启动 wrapper
    │   ├── run_etl.py                           <- ETL 入口
    │   ├── etl\                                 <- ETL pipeline
    │   ├── launchd\                              <- macOS 启动器(Windows 不跑)
    │   └── ...
    ├── data\                                     <- DuckDB + 缓存
    │   ├── processed\fuqing_crm.duckdb          <- 主库 122GB
    │   ├── parquet\                              <- 缓存 1.1GB
    │   ├── raw\                                  <- 原始数据镜像
    │   └── exports\                              <- 导出文件
    ├── logs\                                     <- 日志
    ├── tests\                                    <- pytest
    ├── docs\                                     <- 文档
    │   ├── OPERATIONS.md                        <- 本文件
    │   └── DISASTER-RECOVERY.md                 <- 灾难恢复
    ├── CLAUDE.md                                 <- AI 上下文
    └── requirements.txt / package.json
```

---

## 三、NSSM 服务管理

### 3.1 服务列表

| 服务名 | 用途 | 启动命令 | 日志位置 |
|---|---|---|---|
| `fuqing-uvicorn` | 后端 API (8000) | `net start fuqing-uvicorn` | `%TEMP%\fuqing-uvicorn.log` |
| `fuqing-frontend` | 前端 preview (5173) | `net start fuqing-frontend` | `%TEMP%\fuqing-frontend.log` |

### 3.2 常用命令

```powershell
# 查看服务状态
sc query fuqing-uvicorn
sc query fuqing-frontend

# 启动
net start fuqing-uvicorn
net start fuqing-frontend

# 停止
net stop fuqing-uvicorn
net stop fuqing-frontend

# 重启
net stop fuqing-uvicorn && net start fuqing-uvicorn

# 修改配置(用 NSSM)
nssm edit fuqing-uvicorn    # 弹 GUI
nssm get fuqing-uvicorn AppDirectory
nssm set fuqing-uvicorn AppDirectory "D:\fuqin-date\fuqing-crm-analytics"

# 卸载
nssm remove fuqing-uvicorn confirm
```

### 3.3 进程守护策略

NSSM 配置:
- `Start = SERVICE_AUTO_START`(开机自启)
- `AppExit Default Restart`(进程死了自动重启)
- `AppRestartDelay = 5000`(5 秒后重启,防 restart loop)
- ThrottleInterval 默认 5 秒(同 macOS launchd)

---

## 四、ETL 跑批

### 4.1 触发方式

| 方式 | 触发命令 | 适用场景 |
|---|---|---|
| **手动** | 双击 `D:\fuqin-date\run-etl.bat` | 运营临时跑 |
| **API**(7/10+ 上线后) | `POST /api/v1/etl/run` | 前端按钮触发 |
| **自动**(未来) | Windows Task Scheduler | 不推荐(用 API 更稳) |

### 4.2 ETL 跑批流程(跟 run-etl.bat 一致)

```
1. 停 fuqing-uvicorn(释放 DuckDB 锁)
2. 激活 .venv
3. python scripts/run_etl.py [--update|--inc|--full]
4. 跑完重启 fuqing-uvicorn
```

### 4.3 ETL 模式

| 模式 | 命令 | 耗时 | 适用 |
|---|---|---|---|
| 增量更新 | `--update` | 10-18 min | 默认,推荐 |
| 强制增量 | `--inc` | 8-12 min | 数据库已有数据,只跑增量 |
| 全量重建 | `--full` | 5-10 min | DROP+CREATE,慎用 |

### 4.4 ETL 期间注意事项

- DuckDB 锁:ETL 期间 uvicorn 必须停(L4.38 + L4.51)
- 前端 vite preview 不停,仍可访问静态页(只是 API 502)
- 跑批期间不要中断(10-18 min)

---

## 五、健康检查

### 5.1 必跑检查项

```powershell
# 后端
curl http://localhost:8000/api/v1/health
# 期望: {"status":"ok",...}

# 前端
curl -I http://localhost:5173/
# 期望: HTTP 200

# DuckDB 大小
curl http://localhost:8000/api/v1/health/db_size
# 期望: {"size_gb":120.0 左右}

# pytest baseline
cd D:\fuqin-date\fuqing-crm-analytics
$env:PYTHONPATH = (Get-Location).Path
pytest backend/tests/ -q
# 期望: 跟 mac 一致,可能少 2-3 个 test
```

### 5.2 完整 AI 诊断

跑 `D:\fuqin-date\ai-help.bat`,输出 11 段诊断信息,截图发给 AI。

---

## 六、数据备份

### 6.1 备份策略(当前阶段)

- **不备份**(用户决定,7/17 前不接 NAS)
- DuckDB 122GB 在 Windows 硬盘上,单点风险
- 未来如果需要,加 Windows Task Scheduler + 群晖 NAS 备份

### 6.2 备份到 NAS(预留,7/17 后再加)

```powershell
# 一次性配置 Task Scheduler
$action = New-ScheduledTaskAction -Execute "D:\fuqin-date\backup-to-nas.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At "03:00"
Register-ScheduledTask -TaskName "fuqing-backup-to-nas" -Action $action -Trigger $trigger

# 验证
Get-ScheduledTask -TaskName "fuqing-backup-to-nas"
```

详见 `DISASTER-RECOVERY.md`。

---

## 七、常见问题排查

### 7.1 服务起不来

```powershell
# 看 NSSM 服务状态
sc query fuqing-uvicorn
# 看 STATE 是 STOPPED / START_PENDING / RUNNING

# 看最近日志
powershell -Command "Get-Content $env:TEMP\fuqing-uvicorn.log -Tail 50"
```

**常见原因**:
- 端口被占: `netstat -ano | findstr :8000` 找占用进程
- Python 路径错: `nssm get fuqing-uvicorn AppPath` 看路径
- 依赖没装: 跑 `setup.bat` 重装

### 7.2 ETL 跑批卡住 / 失败

```powershell
# 1. 手动 Ctrl+C 终止 run-etl.bat
# 2. 看错误
# 3. 跑 ai-help.bat + 截图发 AI
```

**常见原因**:
- DuckDB 锁冲突(uvicorn 没停)
- 原始数据文件格式错
- 磁盘满(看 D 盘)

### 7.3 页面打不开

```powershell
# 1. 看服务
sc query fuqing-uvicorn
sc query fuqing-frontend
# 2. 重启
net stop fuqing-uvicorn && net start fuqing-uvicorn
net stop fuqing-frontend && net start fuqing-frontend
# 3. 还不行,看防火墙
netsh advfirewall firewall show rule name="fuqing-crm" 2>nul
# 如果没规则,加:
netsh advfirewall firewall add rule name="fuqing-crm" dir=in action=allow protocol=TCP localport=8000,5173
```

### 7.4 pytest 失败

```powershell
cd D:\fuqin-date\fuqing-crm-analytics
$env:PYTHONPATH = (Get-Location).Path
pytest backend/tests/ -q --tb=short
# 看具体哪个 case fail,截图发 AI
```

**Windows 特有 fail 模式**(Sprint 202+ 已治本大部分):
- 路径分隔符(`\` vs `/`)→ Python pathlib 应已处理
- subprocess env 没传 PATH → 检查 NSSM env
- LockFileEx 锁冲突 → 重启 uvicorn 后再试

---

## 八、版本升级 / 代码同步

### 8.1 从 mac 同步代码(偶尔)

如果 mac 上 AI 写完新功能 push 到 GitHub,Windows 上跑:

```powershell
D:\fuqin-date\sync-from-mac.bat
# 等价于:
# cd D:\fuqin-date\fuqing-crm-analytics
# git pull origin main
# net stop fuqing-uvicorn && net start fuqing-uvicorn
```

**注意**:
- 只同步代码,不动 DuckDB 122GB
- 如果改了 .env 模板,需要手动 merge
- 如果改了 requirements.txt,需要重跑 `pip install`

### 8.2 大版本升级(谨慎)

1. 在 mac 上 commit + push + merge 到 main
2. 验证 mac 上跑通
3. Windows 上 `git pull`
4. 跑 `pytest backend/tests/ -q`(确认 0 回归)
5. 重启服务
6. 浏览器硬刷新测试

---

## 九、附录

### 9.1 关键文件

| 文件 | 作用 |
|---|---|
| `scripts/start_uvicorn.py` | NSSM 启动 wrapper,读 .env |
| `setup.bat` | 一键部署 + 跨 OS 验证 |
| `run-etl.bat` | 手动 ETL |
| `ai-help.bat` | AI 诊断信息收集 |
| `.env` | 路径 + 密钥配置 |
| `requirements.txt` | Python 依赖 |
| `package.json` | Node 依赖 |

### 9.2 关键命令速查

```powershell
# 服务
sc query fuqing-uvicorn
net start fuqing-uvicorn
net stop fuqing-uvicorn

# 健康
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health/db_size

# 测试
pytest backend/tests/ -q

# ETL
D:\fuqin-date\run-etl.bat

# 诊断
D:\fuqin-date\ai-help.bat

# 重装
D:\fuqin-date\setup.bat
```

---

**最后更新:2026-07-06  |  版本:v0.4.14.43 解耦后**
