"""Display-only category labels. SQL grouping still uses raw names."""

from __future__ import annotations

import threading
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

EXACT = {
    "凉茶次抛": "爆款次抛",
    "经典膜": "爆款面膜",
    "医用洁面": "爆款洁面",
}

_SUFFIXES = (
    "次抛",
    "面膜",
    "洁面",
    "护理液",
    "美瞳",
    "面霜",
    "水乳",
    "凝胶",
    "棉片",
    "护理贴",
)


_PASSTHROUGH = {
    "合计",
    "TTL",
    "全部",
    "全店",
    "流失",
    "其他",
    "沉默流失",
    "无",
}

ALLOWED_CATEGORY_COLUMNS = frozenset({
    "spu_category",
    "spu_type",
    "spu_tier",
    "spu_product_class",
    "spu_product_subclass",
    "spu_cosmetic",
    "spu_spec",
})

_CATALOG_CACHE_MAX = 64
_catalog_cache: dict[tuple[int, str], dict[str, str]] = {}
_catalog_cache_lock = threading.Lock()


def _conn_cache_id(conn: Any) -> int:
    """Prefer the inner DuckDB connection: HTTP get_connection() wraps a new object per call."""
    inner = getattr(conn, "_conn", None)
    return id(inner if inner is not None else conn)


def mask_category_name(name: str | None) -> str:
    raw = (name or "").strip()
    if not raw or raw in _PASSTHROUGH:
        return raw
    if raw.startswith("爆款"):
        return raw
    if raw in EXACT:
        return EXACT[raw]
    for suffix in _SUFFIXES:
        if suffix in raw:
            return f"爆款{suffix}"
    return "爆款品类"


def _abc_suffix(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    chars: list[str] = []
    n = index
    while True:
        chars.append(chr(ord("A") + n % 26))
        n = n // 26 - 1
        if n < 0:
            break
    return "".join(reversed(chars))


def unique_display_names(names: Iterable[str | None]) -> dict[str, str]:
    """Map each raw name to a unique display label.

    Colliding masks become 爆款面膜A, 爆款面膜B, ... in stable raw-name order.
    Query keys stay the raw names. Pass the full catalog, not a page subset.
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for name in names:
        raw = (name or "").strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)
        ordered.append(raw)

    groups: dict[str, list[str]] = {}
    for raw in ordered:
        groups.setdefault(mask_category_name(raw), []).append(raw)

    result: dict[str, str] = {}
    for base, members in groups.items():
        members_sorted = sorted(members)
        if len(members_sorted) == 1:
            result[members_sorted[0]] = base
            continue
        for index, raw in enumerate(members_sorted):
            result[raw] = f"{base}{_abc_suffix(index)}"
    return result


def catalog_display_map(conn: Any, column: str) -> dict[str, str]:
    """Stable raw->display map from DISTINCT names on ``orders``."""
    if column not in ALLOWED_CATEGORY_COLUMNS:
        raise ValueError(f"unsupported category column: {column}")
    cache_key = (_conn_cache_id(conn), column)
    with _catalog_cache_lock:
        cached = _catalog_cache.get(cache_key)
        if cached is not None:
            return cached
    rows = conn.execute(
        f"SELECT DISTINCT COALESCE(TRIM({column}), '未知') FROM orders"
    ).fetchall()
    mapping = unique_display_names([row[0] for row in rows] + sorted(_PASSTHROUGH))
    with _catalog_cache_lock:
        if len(_catalog_cache) >= _CATALOG_CACHE_MAX:
            _catalog_cache.pop(next(iter(_catalog_cache)))
        _catalog_cache[cache_key] = mapping
    return mapping


def lookup_display_name(mapping: Mapping[str, str], name: str | None) -> str:
    raw = (name or "").strip()
    if not raw:
        return ""
    return mapping.get(raw, mask_category_name(raw))


def apply_catalog_display_names(
    conn: Any,
    rows: Sequence[MutableMapping[str, object]],
    column: str,
    name_key: str = "name",
    display_key: str = "display_name",
) -> dict[str, str]:
    """Stamp catalog display_name onto each row. Does not rewrite extra keys."""
    mapping = catalog_display_map(conn, column)
    for row in rows:
        raw = str(row.get(name_key) or "").strip()
        row[display_key] = lookup_display_name(mapping, raw)
    return mapping
