"""项目专属私有临时目录 (0700) + 安全文件创建 (0600).

PR3 运维临时文件安全:
  - 禁止在全局 /tmp 使用固定可预测文件名落盘业务导出/审计日志
  - 目录 mode 0700, 文件 mode 0600
  - 路径 resolve 后必须仍在允许根内

环境变量:
  FQ_PRIVATE_TMP  — 覆盖默认私有目录 (绝对路径)
"""
from __future__ import annotations

import os
import secrets
import stat
import tempfile
from pathlib import Path
from typing import Iterable

# 已知安全前缀 (历史 ETL /tmp 产物). resolve 后必须匹配这些之一
# 才允许 tracker 登记文件被 cleanup 删除 (防 tracker 被投毒删出界).
_FQ_SAFE_PREFIXES = (
    "/private/tmp/fuqing_",
    "/private/tmp/_fq_ro",
    "/tmp/fuqing_",
    "/tmp/_fq_ro",
)


def _default_private_tmp_base() -> Path:
    """默认: $TMPDIR/fuqing-crm-tmp-<uid> (非世界可写名, 仍靠 0700 隔离)."""
    return Path(tempfile.gettempdir()) / f"fuqing-crm-tmp-{os.getuid()}"


def get_private_tmp_dir(create: bool = True) -> Path:
    """返回项目专属 0700 临时目录 (resolve 后的绝对路径).

    Raises:
        RuntimeError: 目录被他人拥有, 或不是目录 / 权限异常.
    """
    raw = os.environ.get("FQ_PRIVATE_TMP", "").strip()
    base = Path(raw).expanduser() if raw else _default_private_tmp_base()
    if create:
        base.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(base, 0o700)
        except OSError:
            pass
    resolved = base.resolve()
    if not resolved.is_dir():
        raise RuntimeError(f"private tmp is not a directory: {resolved}")
    try:
        st = resolved.stat()
    except OSError as e:
        raise RuntimeError(f"private tmp stat failed: {resolved}: {e}") from e
    if st.st_uid != os.getuid():
        raise RuntimeError(
            f"private tmp owned by uid={st.st_uid}, expected {os.getuid()}: {resolved}"
        )
    mode = stat.S_IMODE(st.st_mode)
    if mode & 0o077:
        # 尽力收紧; 收不紧也继续用但记录不是世界可写的 700 理想态
        try:
            os.chmod(resolved, 0o700)
        except OSError as e:
            raise RuntimeError(
                f"private tmp mode {oct(mode)} not 0700 and chmod failed: {resolved}: {e}"
            ) from e
    return resolved


def allowed_delete_roots(private_tmp: Path | None = None) -> tuple[Path, ...]:
    """cleanup 允许删除的 resolve 根集合."""
    roots: list[Path] = []
    try:
        roots.append(private_tmp or get_private_tmp_dir(create=False))
    except RuntimeError:
        if private_tmp is not None:
            roots.append(private_tmp.resolve())
    # 也允许「安全前缀」下的路径 (tracker 登记的 ETL 临时 duckdb)
    # 以父目录形式登记: /private/tmp 本身太宽, 用 prefix 字符串检查更准.
    return tuple(roots)


def is_under_allowed_root(
    path: str | Path,
    private_tmp: Path | None = None,
    extra_roots: Iterable[Path] = (),
) -> bool:
    """路径 resolve 后是否在允许删除边界内.

    允许:
      1. 项目专属 private tmp 目录内
      2. 已知 FQ 安全前缀 (fuqing_ / _fq_ro)
      3. extra_roots (测试注入)
    """
    try:
        resolved = Path(path).resolve()
    except OSError:
        return False
    resolved_s = str(resolved)

    for prefix in _FQ_SAFE_PREFIXES:
        if resolved_s.startswith(prefix):
            return True

    candidates: list[Path] = list(extra_roots)
    try:
        candidates.append(private_tmp or get_private_tmp_dir(create=False))
    except RuntimeError:
        if private_tmp is not None:
            candidates.append(Path(private_tmp).resolve())

    for root in candidates:
        try:
            root_r = Path(root).resolve()
            resolved.relative_to(root_r)
            return True
        except (ValueError, OSError):
            continue
    return False


def secure_open_path(
    prefix: str = "fq-",
    suffix: str = "",
    dir: Path | None = None,
) -> Path:
    """在 private tmp 内创建 O_EXCL 临时文件路径, mode 0600.

    文件名含 secrets.token_hex, 不可预测.
    """
    base = dir or get_private_tmp_dir(create=True)
    while True:
        name = f"{prefix}{secrets.token_hex(8)}{suffix}"
        candidate = base / name
        try:
            fd = os.open(
                str(candidate),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            os.close(fd)
            return candidate
        except FileExistsError:
            continue


def ensure_file_mode_600(path: str | Path) -> None:
    """尽力把文件权限收到 0600 (软失败)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def redact_sensitive(text: str, max_len: int = 200) -> str:
    """日志脱敏: 去掉 bearer / password / 过长 SQL 参数字面量."""
    import re

    if not text:
        return text
    out = text
    # Bearer tokens
    out = re.sub(
        r"(?i)(authorization\s*[:=]\s*['\"]?Bearer\s+)[^\s'\"]+",
        r"\1***",
        out,
    )
    out = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._\-+=/]+", r"\1***", out)
    # password fields
    out = re.sub(
        r"(?i)(password\s*[:=]\s*)([^\s,;'\"]+)",
        r"\1***",
        out,
    )
    out = re.sub(
        r"(?i)(passwd|pwd|secret|api[_-]?key|token)\s*[:=]\s*([^\s,;'\"]+)",
        r"\1=***",
        out,
    )
    # SQL string literals longer than 32 chars → truncated
    out = re.sub(
        r"'([^']{32,})'",
        lambda m: f"'{m.group(1)[:12]}…(redacted,{len(m.group(1))}c)'",
        out,
    )
    out = re.sub(
        r'"([^"]{32,})"',
        lambda m: f'"{m.group(1)[:12]}…(redacted,{len(m.group(1))}c)"',
        out,
    )
    if len(out) > max_len:
        out = out[:max_len] + f"…(+{len(out) - max_len}c)"
    return out


__all__ = [
    "get_private_tmp_dir",
    "allowed_delete_roots",
    "is_under_allowed_root",
    "secure_open_path",
    "ensure_file_mode_600",
    "redact_sensitive",
]
