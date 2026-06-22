#!/usr/bin/env python3
# Sprint 60.2 P3 uvicorn 守护 (2026-06-22): launchd keepalive Python 启动脚本
#
# 复用 com.fuqing.duckdb-backup.daily.plist 模式 (Sprint 4 P0-2), 但本脚本
# 是常驻 keepalive (RunAtLoad + KeepAlive), 不是定时任务.
#
# 设计:
# - 用 Python 而不是 bash (避免 macOS launchd sandbox deny bash 读 Desktop 下文件)
# - 直接 exec python -m uvicorn backend.main:app (PID 1 of process group)
# - 注入环境变量 HEALTH_API_KEY + FQ_CRM_PASSWORDS (跟 .env 一致)
# - 故意 unset DUCKDB_PATH: 让 backend/config.py 走默认 (相对主仓根)
# - launchd 自己就是守护进程, 不需要 daemonize
#
# plist 必须 ProgramArguments: [/Users/hutou/homebrew/bin/python3, <this_path>]
# 不能用 /bin/bash 调, 会触发 macOS launchd sandbox deny

import os
import sys
from datetime import datetime

REPO_ROOT = "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics"

# 切到主仓根 (跟 plist WorkingDirectory 冗余, 防御 launchd 环境变量被 reset)
os.chdir(REPO_ROOT)
sys.path.insert(0, REPO_ROOT)

# 环境变量 (跟 .env 同步, 2026-06-22 当前值)
os.environ["HEALTH_API_KEY"] = "nqOgt6K35MVGM3LSP0TNe8cM1glwDKLYjEa7RkL7k8k"
os.environ["FQ_CRM_PASSWORDS"] = "admin:123456,fqsw:fqsw888"
os.environ["DUCKDB_MEMORY_LIMIT"] = "8GB"
# 故意 unset DUCKDB_PATH: 让 backend/config.py 走默认 (相对主仓根)
os.environ.pop("DUCKDB_PATH", None)

# PATH 包含 homebrew (跟 plist EnvironmentVariables 冗余)
os.environ["PATH"] = "/Users/hutou/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")

print(f"[{datetime.now().isoformat()}] uvicorn_launchd.py starting (repo={REPO_ROOT})", file=sys.stderr, flush=True)
print(f"[{datetime.now().isoformat()}] env: HEALTH_API_KEY={os.environ['HEALTH_API_KEY'][:8]}... FQ_CRM_PASSWORDS={os.environ['FQ_CRM_PASSWORDS'][:10]}...", file=sys.stderr, flush=True)

# exec uvicorn (PID 1 of process group, launchd 监控 uvicorn 主进程)
os.execvp(
    sys.executable,
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
)