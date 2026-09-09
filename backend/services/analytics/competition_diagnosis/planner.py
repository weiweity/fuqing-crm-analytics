"""Offline stub planner. Not a real model. Does not expand tool permissions."""

from __future__ import annotations

from typing import Any

from backend.contracts.competition_c0 import success_condition
from backend.services.analytics.competition_diagnosis.chain import (
    FORBIDDEN_EXPANSIONS,
    REGISTERED_TOOLS,
    STUB_PLANNER,
)
from backend.services.analytics.competition_diagnosis.errors import (
    DiagnosisFault,
    injection_refused,
    roi_unsupported,
)

_ROI = ("最佳投放", "最优roi", "best roi", "投放回报最高", "砸钱")
_INJECT = ("忽略skill", "ignore previous", "全部路由", "old routes", "执行sql", "run shell")
_RECOMPUTE = ("重算历史", "exclude_and_recompute", "历史口径已重算")
_EXCLUDE = ("剔除小样", "排除小样", "不要小样")
_RFM = ("rfm", "最近一次购买", "消费频次")
_COHORT = ("去年f", "固定cohort", "固定同期", "f≥4", "f>=4")
_ABSENT = ("未回购", "没回来", "未复购")
_LAST_WEEK = ("上周同星期", "上周同一星期")
_PROMO = ("大促", "自选两段", "双窗")
_STYLE = ("改标题", "换颜色", "样式", "只改外观")
_FILTER = ("改筛选", "只要这个渠道", "filter_change")


def _has(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(item in lowered for item in needles)


def plan_stub(
    utterance: str,
    *,
    request_id: str,
    has_prior: bool,
) -> dict[str, Any]:
    text = utterance.strip()
    if _has(text, _INJECT) or any(item in text for item in FORBIDDEN_EXPANSIONS):
        raise injection_refused(request_id, "utterance")
    if _has(text, _ROI):
        raise roi_unsupported(request_id)
    tools = list(REGISTERED_TOOLS)
    calls: list[dict[str, Any]] = []
    if _has(text, _STYLE):
        calls.append({"tool": "competition_growth_patch", "intent": "STYLE_ONLY", "queries": False})
        return _plan(calls, tools, "STYLE_ONLY")
    if _has(text, _FILTER):
        calls.append({"tool": "competition_growth_patch", "intent": "FILTER_CHANGE", "queries": True, "creates_new_run": True})
        return _plan(calls, tools, "FILTER_CHANGE")
    condition_mode = "INHERIT" if has_prior and "改成" not in text and "改为" not in text else "EXPLICIT"
    if has_prior and not _has(text, ("改日期", "改成", "改为", "换到", "换成")):
        condition_mode = "INHERIT"
    if _has(text, _COHORT):
        capability = "diag.fixed_cohort"
    elif _has(text, _ABSENT):
        capability = "diag.non_repurchase"
    elif _has(text, _RFM):
        capability = "diag.rfm"
    elif _has(text, _RECOMPUTE):
        capability = "diag.sample_recompute_history"
    elif _has(text, _EXCLUDE):
        capability = "diag.sample_exclude_current"
    elif _has(text, _LAST_WEEK):
        capability = "diag.last_week_same_weekday"
    elif _has(text, _PROMO):
        capability = "diag.promo_dual_window"
    elif "渠道" in text:
        capability = "diag.channel"
    elif "新老" in text:
        capability = "diag.new_old"
    elif "会员" in text:
        capability = "diag.member"
    elif "产品" in text or "spu" in text.lower():
        capability = "diag.product"
    elif "草稿" in text:
        capability = "action.draft"
    else:
        capability = "diag.gsv"
        if "同比" in text or "去年同期" in text:
            capability = "diag.yoy"
    calls.append({
        "tool": "competition_growth_step",
        "capability_id": capability,
        "condition_mode": condition_mode,
        "queries": capability != "diag.sample_recompute_history",
    })
    return _plan(calls, tools, capability)


def _plan(calls: list[dict[str, Any]], tools: list[str], focus: str) -> dict[str, Any]:
    first = calls[0] if calls else {}
    return {
        "planner": STUB_PLANNER,
        "registered_tools": tools,
        "calls": calls,
        "focus": focus,
        "capability_id": first.get("capability_id"),
        "intent": first.get("intent"),
        "condition_mode": first.get("condition_mode"),
        "queries": first.get("queries"),
        "creates_new_run": first.get("creates_new_run", False),
        "expanded_tools": False,
        "not_a_real_model": True,
    }


def default_condition() -> dict[str, Any]:
    return success_condition().model_dump(mode="json")


def dump_fault(fault: DiagnosisFault) -> dict[str, Any]:
    return {
        "planner": STUB_PLANNER,
        "registered_tools": list(REGISTERED_TOOLS),
        "calls": [],
        "expanded_tools": False,
        "not_a_real_model": True,
        "error": fault.error.model_dump(mode="json"),
    }
