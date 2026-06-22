# launchd uvicorn 守护（Sprint 62 P3）

> 防止 uvicorn 进程异常退出（前端触发、sleep/wake crash）后无守护。launchd `KeepAlive=true` 失败自动重启。

## 安装

```bash
# 一次性安装（load + KeepAlive 自动接管）
bash scripts/launchd/install_uvicorn_launchd.sh

# 验证
launchctl list | grep com.fuqing.uvicorn
# 期望: PID  PPID  STATUS  LABEL
#        12345  1     running com.fuqing.uvicorn
```

plist 路径：`~/Library/LaunchAgents/com.fuqing.uvicorn.plist`（用户级 launchd，root 不需要）。

## 卸载

```bash
bash scripts/launchd/uninstall_uvicorn_launchd.sh
```

## 手动控制

```bash
# 查看日志
tail -f /tmp/fuqing-uvicorn-launchd.log

# 手动停止（launchd 会自动重启）
launchctl unload ~/Library/LaunchAgents/com.fuqing.uvicorn.plist

# 手动启动
launchctl load ~/Library/LaunchAgents/com.fuqing.uvicorn.plist
```

## kill test（验证 KeepAlive 真生效）

```bash
# 找到 PID
PID=$(lsof -ti :8000 | head -1)
echo "killing PID=$PID"
kill -9 $PID

# 等 10s, 验证新 PID 自动接管
sleep 10
lsof -i :8000
# 期望: 新 PID LISTEN 8000
```

实测: kill -9 → 8s 自动 restart (`ThrottleInterval:5s` + uvicorn startup ~3s)。

## 设计要点

### 为什么启动器用 `python3` 不用 `bash`（Sprint 62 实战 fix）

macOS 14+ 的 launchd sandbox 会 deny bash 读取 Desktop 目录下任何路径（`file-read-data` TCC 硬限制）。如果 plist 启动器是 `/bin/bash scripts/uvicorn_launchd.sh`，会触发：

```
sandbox-exec: sandbox_apply: Operation not permitted
```

绕过方案：用 `python3` 直接 exec uvicorn，Python 进程不会被 sandbox 拦。其他 4 个 fuqing launchd plist（Sprint 4 P0-2 backup、Sprint 6 P0-3 cleanup 等）已经用 python3，**新加 launchd 启动器首选 python3**。

### plist 关键字段

```xml
<key>KeepAlive</key>
<dict>
  <key>SuccessfulExit</key>
  <false/>          <!-- exit 0 (clean shutdown) 不重启 -->
  <key>Crashed</key>
  <true/>           <!-- crash / signal 终止自动重启 -->
</dict>
<key>ThrottleInterval</key>
<integer>5</integer>  <!-- 防 restart loop, 5s 至少 -->
<key>RunAtLoad</key>
<true/>              <!-- launchctl load 立即启动 -->
<key>WorkingDirectory</key>
<string>/Users/hutou/Desktop/fuqin date/fuqing-crm-analytics</string>
```

### 启动器 (`scripts/uvicorn_launchd.py`) 职责

1. `unset DUCKDB_PATH`（避免继承 e2e_schema 这种空库 env，强制走 `backend/config.py` 默认绝对路径）
2. 设 `HEALTH_API_KEY`（Sprint 53.5 修复 uvicorn 启动 RuntimeError）
3. 设 `FQ_CRM_PASSWORDS=admin:123456`（默认 admin 密码）
4. 设 `ETL_MIN_DISK_GB=0`（关闭 ETL 磁盘门槛，CI runner 也能跑）
5. exec `python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`

`exec` 替换当前进程，让 launchd 监控的 PID 就是 uvicorn 进程本身（不是 wrapper）。

## 与 P2 fail-fast 协同

P2 治本（`backend/main.py:validate_startup_db`）做 fail-fast：如果 `DUCKDB_PATH` 接错空 schema DB，uvicorn 启动时直接 raise → launchd 看到 crash → 8s 自动重启。但因为新启动也会 fail-fast，会进入 restart loop（`ThrottleInterval:5s` 限制频率）。

**正确做法**：`scripts/uvicorn_launchd.py` 必须 `unset DUCKDB_PATH` 让 uvicorn 走 `backend/config.py` 默认 `data/processed/fuqing_crm.duckdb`（107GB 生产库），就不会触发 fail-fast。如果手动 `DUCKDB_PATH=/tmp/e2e_schema.duckdb uvicorn ...` 启动，会触发 fail-fast（生产模式）拒绝启动。

## 故障排查

| 症状 | 排查 |
|------|------|
| launchctl list 没 com.fuqing.uvicorn | 没 install，跑 `install_uvicorn_launchd.sh` |
| status = error / exit code 非 0 | 看 `/tmp/fuqing-uvicorn-launchd.log` 启动错误 |
| 端口 8000 没监听 | `lsof -i :8000` 确认进程；`curl /api/v1/health` 验 200 |
| 频繁 restart loop (5s 一次) | fail-fast 触发，看 `data/processed/etl_perf/` 有没有 lock，或 `DUCKDB_PATH` env 错 |
| launchd sandbox 拒绝 | plist 启动器必须用 python3 不用 bash（见设计要点） |

## 跨 sprint 沉淀

`CLAUDE.md` L4 永久规则建议加：**launchd 启动器首选 python3 不用 bash**（macOS 14+ sandbox deny bash read Desktop 路径）。

## 实施文件清单（Sprint 62）

- `scripts/uvicorn_launchd.py` (43 行, Python 启动器)
- `scripts/launchd/com.fuqing.uvicorn.plist` (70 行, launchd 配置)
- `scripts/launchd/install_uvicorn_launchd.sh` (84 行, load + 状态检测)
- `scripts/launchd/uninstall_uvicorn_launchd.sh` (45 行, unload)
- `docs/operating/launchd-uvicorn.md` (本文档)

## 跟其他文件关系

- `docs/operating/ship.md` — 12 步流程，本守护是其中第 4 步 (启动服务) 的 P3 升级
- `docs/operating/pre-commit.md` — pre-commit 钩子，跟 launchd 同属 launchd 范式
- `docs/operating/ci-e2e-history.md` — CI e2e 实战 fix，跟本守护都是防止 sleep/wake 异常
- `backend/main.py:validate_startup_db` — P2 fail-fast，跟 launchd 协同（启动期数据校验）
- `~/.claude/CLAUDE.md` L4 永久规则 — 跨 sprint 沉淀候选