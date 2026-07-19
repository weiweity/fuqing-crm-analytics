#!/usr/bin/env python3
"""Sprint 201 R2 L2.6: DB size 告警 + 兜底清理.

L4.53 永久规则: 项目目录 > 200GB 触发 osascript 弹窗告警.
跟 L4.31 branch cleanup + L4.50 pytest session cleanup + L4.51 snapshot retention 配套.
跨 sprint stable 1:1 模式.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DB_PATH = PROCESSED_DIR / "fuqing_crm.duckdb"
SNAPSHOT_DIR = PROCESSED_DIR / "snapshots"
BACKUP_DIR = PROCESSED_DIR / "backups"
TMP_SIZE_LIMIT_GB = 1.0
PROJECT_SIZE_LIMIT_GB = 200.0


def project_size_gb() -> float:
    """整个项目目录大小 (GB)."""
    total = 0
    for path in PROJECT_ROOT.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total / 1024**3


def snapshot_size_gb() -> float:
    """snapshots/ 目录大小 (GB)."""
    if not SNAPSHOT_DIR.exists():
        return 0.0
    return sum(p.stat().st_size for p in SNAPSHOT_DIR.rglob("*") if p.is_file()) / 1024**3


def backup_size_gb() -> float:
    """backups/ 目录大小 (GB)."""
    if not BACKUP_DIR.exists():
        return 0.0
    return sum(p.stat().st_size for p in BACKUP_DIR.rglob("*") if p.is_file()) / 1024**3


def find_oversized_duckdb(min_size_gb: float = 1.0) -> list[Path]:
    """找 > min_size_gb 的 .duckdb 文件."""
    found = []
    for path in PROJECT_ROOT.rglob("*.duckdb"):
        if path.is_file() and path.stat().st_size / 1024**3 >= min_size_gb:
            found.append(path)
    return found


def main() -> int:
    """主入口: 检测 + 告警 + 兜底清理."""
    issues = []

    # 1. 整个项目目录大小
    proj_gb = project_size_gb()
    if proj_gb > PROJECT_SIZE_LIMIT_GB:
        issues.append(
            f"⚠️  项目目录 {proj_gb:.1f} GB 超过限制 {PROJECT_SIZE_LIMIT_GB} GB"
        )

    # 2. snapshot 目录 (治根: 删空, L4.53 永久规则)
    snap_gb = snapshot_size_gb()
    if snap_gb > 0.5:
        issues.append(f"⚠️  snapshots/ 累积 {snap_gb:.1f} GB (L4.53 应 0 GB)")

    # 3. 找 > 1GB 的孤 DuckDB 文件
    oversize = find_oversized_duckdb(min_size_gb=TMP_SIZE_LIMIT_GB)
    for p in oversize:
        if p != DB_PATH and p.parent != SNAPSHOT_DIR:
            issues.append(
                f"⚠️  孤儿 DuckDB: {p} ({p.stat().st_size / 1024**3:.1f} GB)"
            )

    if issues:
        msg = "[Sprint 201 R2] 存储告警:\n" + "\n".join(issues)
        print(msg, file=sys.stderr)
        # macOS 弹窗
        try:
            import subprocess
            subprocess.run(
                [
                    "osascript", "-e",
                    f'display notification "{msg}" with title "⚠️ 磁盘告警" subtitle "Sprint 201 R2" sound name "Basso"'
                ],
                check=False,
            )
        except Exception:
            pass
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
