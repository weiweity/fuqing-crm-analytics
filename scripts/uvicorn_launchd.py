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

from dotenv import load_dotenv

REPO_ROOT = "/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics"

# 切到主仓根 (跟 plist WorkingDirectory 冗余, 防御 launchd 环境变量被 reset)
os.chdir(REPO_ROOT)
sys.path.insert(0, REPO_ROOT)

# launchd 不继承交互 shell 环境；显式读取本地、gitignored 的 .env。
load_dotenv(os.path.join(REPO_ROOT, ".env"), override=False)
missing_secrets = [
    key for key in ("HEALTH_API_KEY", "FQ_CRM_PASSWORDS")
    if not os.environ.get(key)
]
if missing_secrets:
    raise RuntimeError(f"Missing required launch credentials in .env: {', '.join(missing_secrets)}")

os.environ["DUCKDB_MEMORY_LIMIT"] = "8GB"
# 16GB Mac 运行档：限制单查询线程和读并发，避免 20×10 线程超卖拖死整机。
os.environ["DUCKDB_THREADS"] = "4"
os.environ["FQ_READ_POOL_SIZE"] = "2"
os.environ["FQ_READ_CONCURRENCY_LIMIT"] = "2"
# 重查询单独使用更保守的 buffer 档；低内存时允许 DuckDB spill，禁止挤爆系统。
os.environ["FQ_READ_MEMORY_LIMIT"] = "3GB"
os.environ["FQ_RSS_ALERT_GB"] = "6"
os.environ["FQ_RSS_HARD_LIMIT_GB"] = "8"
# 单 worker 生产进程启用同 IP 单 RFM in-flight 护栏。
os.environ["FQ_SINGLE_USER_V2"] = "1"
# 故意 unset DUCKDB_PATH: 让 backend/config.py 走默认 (相对主仓根)
os.environ.pop("DUCKDB_PATH", None)

# PATH 包含 homebrew (跟 plist EnvironmentVariables 冗余)
os.environ["PATH"] = "/Users/hutou/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")

print(f"[{datetime.now().isoformat()}] uvicorn_launchd.py starting (repo={REPO_ROOT})", file=sys.stderr, flush=True)
print(f"[{datetime.now().isoformat()}] credentials loaded from .env", file=sys.stderr, flush=True)

# exec uvicorn (PID 1 of process group, launchd 监控 uvicorn 主进程)
os.execvp(
    sys.executable,
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
)
