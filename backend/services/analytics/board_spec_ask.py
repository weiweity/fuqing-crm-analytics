"""BoardSpec ask → PATCH_BLOCK suggestion. Does not write facts or call Feishu."""

from __future__ import annotations

import re
from typing import Any

from backend.services.analytics.access import AnalyticsError

KINDS = ("METRIC", "BAR", "LINE", "TABLE", "EVIDENCE", "html_sandbox", "LINK")
KIND_SET = frozenset(KINDS)


def title_from_ask(ask: str) -> str:
    text = str(ask or "").strip()
    quoted = re.search(r'[「"]([^」"]+)[」"]', text)
    if quoted:
        return quoted.group(1).strip()
    stripped = re.sub(r"^把标题改成", "", text).strip()
    return stripped or text


def metric_from_ask(ask: str) -> str | None:
    text = str(ask or "")
    if not re.search(r"换成|改成|口径", text):
        return None
    if re.search(r"零售\s*GSV|retail_gsv", text):
        return "retail_gsv"
    return None


def is_facts_question(ask: str) -> bool:
    text = str(ask or "")
    if re.search(r"改成|换成|加一块|标题|口径", text):
        return False
    return bool(re.search(r"多少|是多少|GSV\s*是多少|这个数字", text))


def kind_from_ask(ask: str) -> str | None:
    text = str(ask or "")
    if not re.search(r"加一块|换成|改成", text):
        return None
    for kind in KINDS:
        if kind == "LINK":
            continue
        if kind in text:
            return kind
    if "折线" in text:
        return "LINE"
    if "柱" in text:
        return "BAR"
    if "表" in text:
        return "TABLE"
    return None


def propose_ask_patch(payload: dict[str, Any]) -> dict[str, Any]:
    block_id = payload.get("block_id")
    version = payload.get("version")
    ask = payload.get("ask")
    if not isinstance(block_id, str) or not block_id.strip():
        raise AnalyticsError(422, "CANVAS_NO_SELECTION", "先点选一块")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise AnalyticsError(422, "PATCH_BASE_VERSION", "base_version 须为 >= 1 的整数")
    if not isinstance(ask, str) or not ask.strip():
        raise AnalyticsError(422, "PATCH_TITLE", "set_title 需要 title")
    if is_facts_question(ask):
        raise AnalyticsError(422, "ASK_FACTS", "问数不改数字。打开画布按绑定刷新，未写入。")
    metric = metric_from_ask(ask)
    if metric is not None:
        return {
            "block_id": block_id.strip(),
            "base_version": version,
            "op": "set_metric_ref",
            "metric_ref": metric,
        }
    kind = kind_from_ask(ask)
    if kind is not None:
        if kind not in KIND_SET:
            raise AnalyticsError(422, "PATCH_KIND", f"set_kind 非法 kind: {kind}")
        return {
            "block_id": block_id.strip(),
            "base_version": version,
            "op": "set_kind",
            "kind": kind,
        }
    title = title_from_ask(ask)
    if not title:
        raise AnalyticsError(422, "PATCH_TITLE", "set_title 需要 title")
    return {
        "block_id": block_id.strip(),
        "base_version": version,
        "op": "set_title",
        "title": title,
    }
