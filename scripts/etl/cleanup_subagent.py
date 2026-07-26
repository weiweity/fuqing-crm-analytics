"""PR3 — Layer 6 安全边界重写: 临时文件清理 (禁止扫全局 /tmp)

历史教训 (Sprint 5 deep dive):
  subagent 复制 production 55GB × 8 到 /private/tmp/p0_3_dive/。
  旧 Layer 6 扫全局 /tmp 任意 1h+1GB 文件, 误删面过大。

PR3 安全边界 (硬约束):
  1. **禁止**扫描删除全局 /tmp 任意文件
  2. **只能删**:
       a) TrackerDB 已登记且过期的文件
       b) 项目专属 0700 临时目录内 (顶层) 过期文件
  3. 路径 resolve 后必须在允许根内 (private tmp 或 FQ 安全前缀)
  4. 跳过: 目录 / symlink / 非当前 UID / 硬链接 (nlink!=1)
  5. lsof 缺失/超时/报错 **fail-closed**: 跳过删除
  6. **默认 dry-run**; 正式删除需显式 --execute
  7. 保留文件数 / 总容量 cap
  8. 嵌套目录不递归扫; 仅当路径在 TrackerDB 中才处理

用法:
  PYTHONPATH="$(pwd)" python3 scripts/etl/cleanup_subagent.py           # dry-run
  PYTHONPATH="$(pwd)" python3 scripts/etl/cleanup_subagent.py --execute # 真删
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.etl.common.open_check import is_open_by_any_process  # noqa: E402
from scripts.etl.common.private_tmp import (  # noqa: E402
    get_private_tmp_dir,
    is_under_allowed_root,
)
from scripts.etl.common.tmp_tracker import TrackerDB  # noqa: E402

# ─────────────────────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────────────────────
# 历史保护 basenames (运维状态, 永不删) — 即便误登记到 tracker 也跳过
_PROTECTED_BASENAMES = {
    "fuqing-tmp-cleanup.log",
    "fuqing-etl-marker.json",
    "fuqing-backup-cleanup.log",
    "fuqing-backup-cleanup.lock",
    "fuqing-duckdb-backup.log",
    "fuqing-subagent-cleanup.log",
    "fuqing-etl-health.json",
    "fuqing-crm-backend.log",
    "fuqing-tmp-tracker.db",
    "fuqing-tmp-tracker.db-wal",
    "fuqing-tmp-tracker.db-shm",
}

# Cap
_MAX_DELETE_PER_RUN = 5
_MAX_DELETE_BYTES_PER_RUN = 100 * 1024**3  # 100GB
_MIN_AGE_HOURS = 1.0
_MIN_SIZE_BYTES = 1 * 1024**3  # 1GB (private 顶层未跟踪文件阈值; 测试可 monkeypatch)
_TRACKER_MIN_AGE_HOURS = 1.0

# 日志只允许写入项目专属 private tmp；目录不可用时宁可不写。
_LOG_BASENAME = "fuqing-subagent-cleanup.log"


def _log_path() -> Path | None:
    try:
        return get_private_tmp_dir(create=True) / _LOG_BASENAME
    except (OSError, RuntimeError):
        return None


def _log_stat_is_safe(st: os.stat_result) -> bool:
    """日志对象必须是当前用户独占的普通文件."""
    if not stat.S_ISREG(st.st_mode):
        return False
    if getattr(st, "st_nlink", 1) != 1:
        return False
    getuid = getattr(os, "getuid", None)
    st_uid = getattr(st, "st_uid", None)
    return getuid is None or st_uid is None or st_uid == getuid()


def _log_mode_is_private(st: os.stat_result) -> bool:
    return stat.S_IMODE(st.st_mode) == 0o600


def _same_log_file(before: os.stat_result, after: os.stat_result) -> bool:
    """确认 lstat 与 open 后 fd 指向同一对象，覆盖无 O_NOFOLLOW 的平台."""
    before_dev = getattr(before, "st_dev", None)
    after_dev = getattr(after, "st_dev", None)
    before_ino = getattr(before, "st_ino", None)
    after_ino = getattr(after, "st_ino", None)
    if None in (before_dev, after_dev, before_ino, after_ino):
        return False
    return before_dev == after_dev and before_ino == after_ino


def _open_log_fd(log_path: Path) -> int | None:
    """Fail-closed 打开日志，拒绝 symlink/换文件竞态/错误属主."""
    try:
        before = os.lstat(log_path)
    except FileNotFoundError:
        before = None
    except OSError:
        return None

    if before is not None and not _log_stat_is_safe(before):
        return None

    flags = os.O_WRONLY | os.O_APPEND
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    if before is None:
        # O_EXCL 既避免覆盖，也在没有 O_NOFOLLOW 时拒绝预置 symlink。
        flags |= os.O_CREAT | os.O_EXCL

    try:
        fd = os.open(log_path, flags, 0o600)
    except OSError:
        return None

    keep_open = False
    try:
        opened = os.fstat(fd)
        if not _log_stat_is_safe(opened):
            return None
        if before is not None and not _same_log_file(before, opened):
            return None

        # 先确认 fd 身份，再通过 fd 收紧权限，避免 chmod 跟随换入的路径。
        if (
            before is None
            or not _log_mode_is_private(before)
            or not _log_mode_is_private(opened)
        ):
            fchmod = getattr(os, "fchmod", None)
            if fchmod is None:
                return None
            fchmod(fd, 0o600)

        verified = os.fstat(fd)
        if not _log_stat_is_safe(verified) or not _log_mode_is_private(verified):
            return None
        if not _same_log_file(opened, verified):
            return None
        keep_open = True
        return fd
    except OSError:
        return None
    finally:
        if not keep_open:
            try:
                os.close(fd)
            except OSError:
                pass


def _log(msg: str) -> None:
    """持久日志, 软失败."""
    fd: int | None = None
    try:
        ts = datetime.now(timezone.utc).isoformat()
        log_path = _log_path()
        if log_path is None:
            return
        fd = _open_log_fd(log_path)
        if fd is None:
            return
        stream = os.fdopen(fd, "a", encoding="utf-8")
        fd = None  # stream 接管 fd
        with stream as f:
            f.write(f"[{ts}] {msg}\n")
    except (OSError, ValueError):
        pass
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _is_protected(path: str) -> bool:
    return os.path.basename(path) in _PROTECTED_BASENAMES


def _safe_lstat(path: str) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except OSError:
        return None


def _passes_safety_gates(
    path: str,
    *,
    private_tmp: Path | None,
    require_tracked: bool,
    tracker: TrackerDB | None,
) -> tuple[bool, str]:
    """统一安全门: 通过返回 (True, ""); 否则 (False, reason)."""
    if _is_protected(path):
        return False, "protected basename"

    # symlink: lstat 不跟随; islink 跳过
    if os.path.islink(path):
        return False, "symlink"

    st = _safe_lstat(path)
    if st is None:
        return False, "lstat failed"

    if stat_is_dir(st):
        return False, "directory"

    if not stat_is_reg(st):
        return False, "not regular file"

    # 非当前 UID
    try:
        if st.st_uid != os.getuid():
            return False, f"uid mismatch (file={st.st_uid} self={os.getuid()})"
    except AttributeError:
        pass  # Windows 等无 st_uid 时跳过此项

    # 硬链接异常: nlink != 1
    if getattr(st, "st_nlink", 1) != 1:
        return False, f"hardlink anomaly nlink={st.st_nlink}"

    # resolve 后必须在允许根
    if not is_under_allowed_root(path, private_tmp=private_tmp):
        return False, "outside allowed roots"

    if require_tracked:
        if tracker is None or not tracker.is_available() or not tracker.is_tracked(path):
            return False, "not tracked (nested requires tracker)"

    return True, ""


def stat_is_dir(st: os.stat_result) -> bool:
    import stat as statmod

    return statmod.S_ISDIR(st.st_mode)


def stat_is_reg(st: os.stat_result) -> bool:
    import stat as statmod

    return statmod.S_ISREG(st.st_mode)


def _collect_candidates(
    tracker: TrackerDB | None = None,
    private_tmp: Path | None = None,
    now: float | None = None,
) -> list[tuple[str, int, float, str]]:
    """收集可删候选.

    Returns:
        list of (path, size_bytes, age_h, source)  source ∈ {tracker, private_top}
        按 age 倒序.
    """
    candidates: list[tuple[str, int, float, str]] = []
    seen: set[str] = set()
    now = now if now is not None else time.time()

    try:
        priv = private_tmp if private_tmp is not None else get_private_tmp_dir(create=True)
    except RuntimeError as e:
        _log(f"  [sub-cleanup] private tmp unavailable: {e}")
        priv = None

    # ── A) TrackerDB 过期登记 ──
    if tracker is not None and tracker.is_available():
        for path, size_bytes, age_h in tracker.list_expired(age_hours=_TRACKER_MIN_AGE_HOURS):
            ok, reason = _passes_safety_gates(
                path,
                private_tmp=priv,
                require_tracked=False,  # 已从 tracker 来
                tracker=tracker,
            )
            if not ok:
                _log(f"  [sub-cleanup] skip tracker candidate {path}: {reason}")
                continue
            try:
                real = str(Path(path).resolve())
            except OSError:
                real = path
            if real in seen:
                continue
            seen.add(real)
            # 再确认 size/age 以磁盘为准
            st = _safe_lstat(path)
            if st is None:
                continue
            size_bytes = st.st_size
            age_h = (now - st.st_mtime) / 3600.0
            if age_h < _TRACKER_MIN_AGE_HOURS:
                continue
            candidates.append((path, size_bytes, age_h, "tracker"))

    # ── B) 专属 private tmp 顶层文件 (不递归; 嵌套只走 tracker) ──
    if priv is not None and priv.is_dir():
        try:
            names = os.listdir(priv)
        except OSError as e:
            _log(f"  [sub-cleanup] listdir private tmp failed: {e}")
            names = []
        for name in names:
            path = str(priv / name)
            # 嵌套目录: 不递归; 若 tracker 有登记, A 已覆盖
            if os.path.isdir(path) and not os.path.islink(path):
                continue
            ok, reason = _passes_safety_gates(
                path,
                private_tmp=priv,
                require_tracked=False,
                tracker=tracker,
            )
            if not ok:
                continue
            st = _safe_lstat(path)
            if st is None:
                continue
            age_h = (now - st.st_mtime) / 3600.0
            if age_h < _MIN_AGE_HOURS:
                continue
            if st.st_size < _MIN_SIZE_BYTES:
                continue
            try:
                real = str(Path(path).resolve())
            except OSError:
                real = path
            if real in seen:
                continue
            seen.add(real)
            candidates.append((path, st.st_size, age_h, "private_top"))

    candidates.sort(key=lambda x: -x[2])
    return candidates


def cleanup_subagent_tmp(
    dry_run: bool = True,
    tracker: TrackerDB | None = None,
    private_tmp: Path | None = None,
) -> dict:
    """安全清理临时文件. 默认 dry_run=True (不真删).

    Args:
        dry_run: True 只扫描不删; False 需调用方显式关闭 (CLI --execute)
        tracker: 可注入 (测试); 默认 TrackerDB()
        private_tmp: 可注入项目专属临时根 (测试)

    Returns:
        dict with deleted_count, freed_bytes, errors, candidates_scanned,
        skipped_open_count, skipped_unsafe_count, dry_run
    """
    result: dict = {
        "deleted_count": 0,
        "freed_bytes": 0,
        "errors": [],
        "candidates_scanned": 0,
        "skipped_open_count": 0,
        "skipped_unsafe_count": 0,
        "dry_run": dry_run,
    }

    if tracker is None:
        tracker = TrackerDB()

    candidates = _collect_candidates(tracker=tracker, private_tmp=private_tmp)
    result["candidates_scanned"] = len(candidates)

    if not candidates:
        _log(
            f"  [sub-cleanup] no candidates"
            f"{' [DRY-RUN]' if dry_run else ''}"
        )
        return result

    _log(f"  [sub-cleanup] scanned {len(candidates)} candidate(s):")
    for path, size_bytes, age_h, source in candidates[:_MAX_DELETE_PER_RUN]:
        _log(
            f"    - [{source}] {path} "
            f"({size_bytes / (1024**3):.1f}GB, {age_h:.0f}h old)"
        )

    if dry_run:
        _log(
            f"  [sub-cleanup] DRY-RUN: would clean up to "
            f"{_MAX_DELETE_PER_RUN} file(s) / "
            f"{_MAX_DELETE_BYTES_PER_RUN / 1024**3:.0f}GB "
            f"(pass --execute to delete)"
        )
        return result

    bytes_deleted = 0
    for path, size_bytes, age_h, source in candidates:
        if result["deleted_count"] >= _MAX_DELETE_PER_RUN:
            _log(f"  [sub-cleanup] cap hit: max {_MAX_DELETE_PER_RUN} files")
            break
        if bytes_deleted + size_bytes > _MAX_DELETE_BYTES_PER_RUN:
            _log(
                f"  [sub-cleanup] cap hit: max "
                f"{_MAX_DELETE_BYTES_PER_RUN / 1024**3:.0f}GB"
            )
            break

        # 删前再次 resolve + 边界检查 (TOCTOU 收窄)
        try:
            resolved = str(Path(path).resolve())
        except OSError as e:
            result["skipped_unsafe_count"] += 1
            _log(f"  [sub-cleanup] skip resolve fail {path}: {e}")
            continue
        if not is_under_allowed_root(resolved, private_tmp=private_tmp):
            result["skipped_unsafe_count"] += 1
            _log(f"  [sub-cleanup] skip outside root after resolve: {resolved}")
            continue
        if os.path.islink(path):
            result["skipped_unsafe_count"] += 1
            _log(f"  [sub-cleanup] skip symlink: {path}")
            continue

        # lsof fail-closed
        is_open, reason = is_open_by_any_process(resolved)
        if is_open:
            result["skipped_open_count"] += 1
            _log(f"  [sub-cleanup] skip (lsof/fail-closed): {path} — {reason}")
            continue

        try:
            os.remove(resolved)
            result["deleted_count"] += 1
            result["freed_bytes"] += size_bytes
            bytes_deleted += size_bytes
            if tracker is not None and tracker.is_available():
                tracker.remove(resolved)
            _log(
                f"  [sub-cleanup] DELETED [{source}]: {resolved} "
                f"({size_bytes / (1024**3):.1f}GB, {age_h:.0f}h old)"
            )
        except OSError as e:
            result["errors"].append(f"{resolved}: {e}")
            _log(f"  [sub-cleanup] skip {resolved}: {e}")

    _log(
        f"  [sub-cleanup] summary: deleted={result['deleted_count']} "
        f"freed={result['freed_bytes'] / 1024**3:.1f}GB "
        f"skipped_open={result['skipped_open_count']} "
        f"skipped_unsafe={result['skipped_unsafe_count']} "
        f"errors={len(result['errors'])}"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR3 Layer 6: 安全临时文件清理 (默认 dry-run)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="只扫描不删 (默认即 dry-run; 保留兼容 flag)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="显式开启真删 (否则一律 dry-run)",
    )
    args = parser.parse_args()
    # 只有 --execute 才真删; --dry-run 与默认都是 dry-run
    dry_run = not args.execute
    if args.dry_run:
        dry_run = True
    result = cleanup_subagent_tmp(dry_run=dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
