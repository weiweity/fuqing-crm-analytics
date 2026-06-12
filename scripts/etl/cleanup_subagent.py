"""Sprint 6 P0-3 (2026-06-07) — 第 6 层防护: subagent /tmp 孤儿清理

历史教训 (Sprint 5 deep dive 2026-06-06):
  Sprint 5 deep dive subagent 跑 5 真实验时, 复制 production 55GB × 8 次 = 440GB
  在 /private/tmp/p0_3_dive/. 5 层防护全都没拦, 因为 5 层防护是 ETL 跑批路径
  设计 (FQ_TMP_PREFIXES 白名单), subagent 走手动 Python shutil.copy2 不触发.
  本文件不依赖 ETL 触发, 由 launchd hourly plist 主动跑, 兜底 subagent 路径
  漏出来的非 fq_ 前缀巨型孤儿.

设计原则:
  1. 扫 /private/tmp + /tmp 下所有 不在 FQ_TMP_PREFIXES 白名单的 1h+ 1GB+ 文件
     (避开 macOS 系统服务, 只针对用户态巨型文件)
  2. 排除项目根 /Users/hutou/Desktop/fuqin-date/ 路径 (业务文件, 不会误删)
  3. 排除 FQ_TMP_PREFIXES 下文件 (留给 layer 1 atexit 处理)
  4. 排除 sub-process 活进程写入的标志文件 (避开当前 subagent / IDE 调试中的
     活文件; 1h+ 阈值是兜底, launchd hourly 跑意味着 1h 内会再扫一次)
  5. symlink 跳过 (跟 layer 1 一致; getmtime 跟随 target 误报, 保守不删)
  6. 单次 cap 5 文件 / 100GB (跟 layer 1 一致, 防御性)
  7. 软失败 + 持久 log /tmp/fuqing-subagent-cleanup.log

用法:
  CLI 手动跑:
    PYTHONPATH="$(pwd)" python3 scripts/etl/cleanup_subagent.py [--dry-run]
  作为 module 调:
    from scripts.etl.cleanup_subagent import cleanup_subagent_tmp
    result = cleanup_subagent_tmp(dry_run=False)  # -> dict

函数签名:
  cleanup_subagent_tmp(dry_run=False) -> dict
  返回 {deleted_count, freed_bytes, errors, candidates_scanned}
"""
from __future__ import annotations

import os
import sys
import time
import json
import argparse
from datetime import datetime, timezone

# ─────────────────────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────────────────────
# Layer 1 的 FQ_TMP_PREFIXES 白名单 — 避免跟 layer 1 冲突
_FQ_TMP_PREFIXES = (
    "/private/tmp/_fq_ro",   # Layer 1 业务白名单
    "/private/tmp/fuqing_",  # Layer 1 业务白名单
)

# 扫描根目录
_SCAN_ROOTS = (
    "/private/tmp",
    "/tmp",
)

# 排除路径前缀 (项目根, 不会误删业务文件)
_EXCLUDE_PATH_PREFIXES = (
    "/Users/hutou/Desktop/fuqin-date",
)

# Layer 1 自身 log + marker + launchd 锁 — 不能让 layer 6 误删这些
# (它们是 layer 1 自己的运维证据, 删了会让 layer 1 marker 状态混乱)
_PROTECTED_BASENAMES = {
    "fuqing-tmp-cleanup.log",
    "fuqing-etl-marker.json",
    "fuqing-backup-cleanup.log",
    "fuqing-backup-cleanup.lock",
    "fuqing-duckdb-backup.log",
    "fuqing-subagent-cleanup.log",  # 本文件自己的 log
    "fuqing-etl-health.json",
    "fuqing-crm-backend.log",
}

# 排除扩展名 (sub-process 调试临时脚本/源码, 不是巨型数据)
_EXCLUDE_EXTENSIONS = (
    ".py", ".sh", ".json", ".log", ".txt", ".md",
    ".yml", ".yaml", ".toml", ".lock", ".pid",
)

# Cap
_MAX_DELETE_PER_RUN = 5                    # 防御性: 单次最多删 5 个
_MAX_DELETE_BYTES_PER_RUN = 100 * 1024**3  # 100GB/次
_MIN_AGE_HOURS = 1                         # 1h+ (比 layer 1 的 24h 严,
                                            # 因为 hourly 跑, 1h 是安全缓冲)
_MIN_SIZE_BYTES = 1 * 1024**3              # 1GB+ (只针对巨型文件,
                                            # 小文件不影响磁盘)
_LOG_PATH = "/tmp/fuqing-subagent-cleanup.log"


def _log(msg: str) -> None:
    """持久日志 — 写 /tmp/fuqing-subagent-cleanup.log, 失败不 raise (软失败)."""
    try:
        ts = datetime.now(timezone.utc).isoformat()
        with open(_LOG_PATH, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except OSError:
        pass  # log 失败不阻塞 cleanup


def _is_protected(path: str) -> bool:
    """检查路径是否在保护名单 (layer 1 自身状态文件 + 项目根)."""
    base = os.path.basename(path)
    if base in _PROTECTED_BASENAMES:
        return True
    # 排除项目根
    for prefix in _EXCLUDE_PATH_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _is_in_whitelist(path: str) -> bool:
    """检查路径是否在 FQ_TMP_PREFIXES 白名单 (留给 layer 1 处理)."""
    for prefix in _FQ_TMP_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _is_excluded_ext(path: str) -> bool:
    """检查扩展名是否在排除名单 (代码/日志/锁文件, 不是巨型数据)."""
    _, ext = os.path.splitext(path)
    return ext.lower() in _EXCLUDE_EXTENSIONS


def _collect_candidates() -> list[tuple[str, int, float]]:
    """收集扫描根目录下所有 1h+ 1GB+ 不在白名单/保护名单的候选文件.

    Returns:
        list of (path, size_bytes, age_h) tuples, 按 age 倒序 (最老优先).
    """
    candidates: list[tuple[str, int, float]] = []
    seen_realpaths: set[str] = set()  # macOS /tmp -> /private/tmp symlink dedupe
    now = time.time()

    for root in _SCAN_ROOTS:
        if not os.path.isdir(root):
            continue
        try:
            entries = os.listdir(root)
        except OSError as e:
            _log(f"  [sub-cleanup] skip root {root}: {e}")
            continue
        for name in entries:
            path = os.path.join(root, name)
            # 跳过目录 (subagent 偶尔 mkdir 但 mkdir 不会吃盘)
            if os.path.isdir(path) and not os.path.islink(path):
                continue
            # 跳过 symlink (保守 — 跟 layer 1 一致)
            if os.path.islink(path) is True:
                continue
            # 跳过白名单 (留给 layer 1)
            if _is_in_whitelist(path):
                continue
            # 跳过保护名单
            if _is_protected(path):
                continue
            # 跳过非巨型扩展名
            if _is_excluded_ext(path):
                continue
            # macOS /tmp -> /private/tmp symlink 去重 (避免同一文件扫两次)
            try:
                realpath = os.path.realpath(path)
            except OSError:
                realpath = path
            if realpath in seen_realpaths:
                continue
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            age_h = (now - mtime) / 3600
            if age_h < _MIN_AGE_HOURS:
                continue
            try:
                size_bytes = os.path.getsize(path)
            except OSError:
                continue
            if size_bytes < _MIN_SIZE_BYTES:
                continue
            seen_realpaths.add(realpath)
            candidates.append((path, size_bytes, age_h))

    # 按 age 倒序 (最老优先)
    candidates.sort(key=lambda x: -x[2])
    return candidates


def cleanup_subagent_tmp(dry_run: bool = False) -> dict:
    """Sprint 6 P0-3 第 6 层防护: 兜底 subagent 漏出来的非 fq_ 前缀 /tmp 巨型孤儿.

    设计原则:
      1. 扫 /private/tmp + /tmp 下所有 不在 FQ_TMP_PREFIXES 白名单的 1h+ 1GB+ 文件
      2. 排除项目根路径 + layer 1 自身状态文件 + 代码/日志扩展名
      3. symlink 跳过 (跟 layer 1 一致)
      4. cap: 5 文件 / 100GB 单次 (跟 layer 1 一致, 防御性)
      5. 软失败: 删除失败只 log, 不 raise
      6. 持久 log 到 /tmp/fuqing-subagent-cleanup.log
      7. dry_run=True 时只扫描不删 (供 --dry-run 模式 + 测试用)

    Args:
        dry_run: True = 只扫描不删, 仍然 log 但 result 标注 dry_run=True.

    Returns:
        dict {deleted_count, freed_bytes, errors, candidates_scanned, dry_run}
    """
    result = {
        "deleted_count": 0,
        "freed_bytes": 0,
        "errors": [],
        "candidates_scanned": 0,
        "dry_run": dry_run,
    }

    candidates = _collect_candidates()
    result["candidates_scanned"] = len(candidates)

    if not candidates:
        _log(f"  [sub-cleanup] scanned {len(candidates)} candidate(s) in {list(_SCAN_ROOTS)}, nothing to clean"
             f"{' [DRY-RUN]' if dry_run else ''}")
        return result

    # log 候选清单 (即使 dry_run 也打, 方便审计)
    _log(f"  [sub-cleanup] scanned {len(candidates)} candidate(s):")
    for path, size_bytes, age_h in candidates[:_MAX_DELETE_PER_RUN]:
        _log(f"    - {path} ({size_bytes / (1024**3):.1f}GB, {age_h:.0f}h old)")

    if dry_run:
        _log(f"  [sub-cleanup] DRY-RUN: would clean up to "
             f"{_MAX_DELETE_PER_RUN} file(s) / {_MAX_DELETE_BYTES_PER_RUN / 1024**3:.0f}GB")
        return result

    bytes_deleted = 0
    for path, size_bytes, age_h in candidates:
        if result["deleted_count"] >= _MAX_DELETE_PER_RUN:
            _log(f"  [sub-cleanup] cap hit: max {_MAX_DELETE_PER_RUN} files per run")
            break
        if bytes_deleted + size_bytes > _MAX_DELETE_BYTES_PER_RUN:
            _log(f"  [sub-cleanup] cap hit: max {_MAX_DELETE_BYTES_PER_RUN / 1024**3:.0f}GB per run")
            break
        try:
            os.remove(path)
            result["deleted_count"] += 1
            result["freed_bytes"] += size_bytes
            bytes_deleted += size_bytes
            _log(f"  [sub-cleanup] DELETED: {path} ({size_bytes / (1024**3):.1f}GB, {age_h:.0f}h old)")
        except OSError as e:
            result["errors"].append(f"{path}: {e}")
            _log(f"  [sub-cleanup] skip {path}: {e}")

    _log(
        f"  [sub-cleanup] summary: deleted={result['deleted_count']} "
        f"freed={result['freed_bytes'] / 1024**3:.1f}GB "
        f"errors={len(result['errors'])}"
    )
    return result


def main() -> int:
    """CLI 入口 — 支持 --dry-run 模式 (供测试 + 运维验证用)."""
    parser = argparse.ArgumentParser(
        description="Sprint 6 P0-3 subagent /tmp 孤儿清理 (第 6 层防护)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只扫描不删, 仍然 log candidates, 但 result 标注 dry_run=True",
    )
    args = parser.parse_args()
    result = cleanup_subagent_tmp(dry_run=args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
