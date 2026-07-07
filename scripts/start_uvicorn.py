"""
Sprint 205+ Windows NSSM 启动 wrapper (跟 macOS uvicorn_launchd.py 同位).
读 .env -> os.environ.setdefault() -> uvicorn.run().
NSSM 直接调这个 Python 文件,不走 macOS launchd 模式.
"""
import os
import sys
from pathlib import Path

# Force UTF-8 for stdout/stderr on Windows (fix Chinese garbled output)
os.environ["PYTHONIOENCODING"] = "utf-8"

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"

# 1. 读 .env 注入 os.environ (setdefault 保留系统已有的,不覆盖 Windows 自身环境变量)
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)

# 2. PYTHONPATH
os.environ["PYTHONPATH"] = str(REPO_ROOT)

# 3. 启动 uvicorn
import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("UVICORN_PORT", "8000"))
    workers = int(os.environ.get("UVICORN_WORKERS", "1"))
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        workers=workers,
        log_level="info",
    )
