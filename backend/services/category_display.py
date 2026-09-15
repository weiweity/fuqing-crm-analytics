"""Display-only category labels. SQL grouping still uses raw names."""

from __future__ import annotations

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


_PASSTHROUGH = {"合计", "TTL", "全部", "全店"}


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
