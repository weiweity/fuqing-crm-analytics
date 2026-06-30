"""
ad_hoc_queries.registry — QuerySpec 数据类 + QUERIES 注册表.

MVP 范围: 只注册 daily_gsv. 其他 4 个 (channel-slice / rfm-distribution / yoy-battle /
customer-segment) 留 TODO Sprint 62+.

设计原则 (跟 Sprint 54 L3 一致):
- 禁 inline SQL → 复用 backend/semantic/ 口径层
- 复用 backend/services/ 业务逻辑
- 复用 backend/contracts/schemas.py Pydantic 类型
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class QuerySpec:
    """单个 query 的元数据 + run 入口."""

    name: str
    description: str
    args: List[Dict[str, Any]]  # argparse 参数 spec
    headers: List[str]  # stdout / csv 输出列
    run: Callable[..., List[List[Any]]]  # 返 rows (list of list, 跟 headers 对齐)
    output_columns: Optional[List[str]] = None  # 备用, 跟 headers 重复时省略
    xlsx_writer: Optional[Callable[..., str]] = None  # 自定义 xlsx 写入器
    # Sprint 61+ 取数目录规则 (user 拍板)
    business_tag: str = ""  # 业务标签, e.g. "新老客数据" / "RFM分布" / "渠道切片"
    base_year_arg: str = "start"  # 用哪个 arg 的年份作为基期年份 (默认取 start 年)


QUERIES: Dict[str, QuerySpec] = {}


def register(spec: QuerySpec) -> QuerySpec:
    """装饰器: 注册 QuerySpec 到 QUERIES dict."""
    QUERIES[spec.name] = spec
    return spec


def get(name: str) -> QuerySpec:
    """按 name 查 QuerySpec, 找不到抛 KeyError (argparse 阶段就该拦截)."""
    if name not in QUERIES:
        raise KeyError(
            f"Unknown query: {name}. Available: {', '.join(sorted(QUERIES.keys()))}"
        )
    return QUERIES[name]


# 延迟导入避免循环依赖 + 启动慢
def _load_builtins() -> None:
    from scripts.ad_hoc_queries import daily_gsv  # noqa: F401
    from scripts.ad_hoc_queries import yoy_battle  # noqa: F401
    from scripts.ad_hoc_queries import channel_slice  # noqa: F401
    from scripts.ad_hoc_queries import two_year_overview  # noqa: F401
    from scripts.ad_hoc_queries import new_old_customer  # noqa: F401
    from scripts.ad_hoc_queries import rfm_repurchase  # noqa: F401
    from scripts.ad_hoc_queries import top_n  # noqa: F401
    from scripts.ad_hoc_queries import dq_report  # noqa: F401
    from scripts.ad_hoc_queries import export_excel  # noqa: F401
    from scripts.ad_hoc_queries import ask  # noqa: F401


def _run_list_endpoints() -> List[List[Any]]:
    """返回已注册 query 清单，供 CLI list-endpoints 使用。"""
    rows: List[List[Any]] = []
    for name, spec in sorted(QUERIES.items()):
        if name == "list-endpoints":
            continue
        formats = sorted({
            arg.get("default", "")
            for arg in spec.args
            if "--format" in arg.get("flags", ())
        })
        rows.append([name, spec.business_tag or "-", ",".join(f for f in formats if f), spec.description])
    return rows


_load_builtins()

register(QuerySpec(
    name="list-endpoints",
    description="列出 ad-hoc-query 已注册子命令",
    args=[],
    headers=["command", "business_tag", "default_format", "description"],
    run=lambda **kw: _run_list_endpoints(),
    business_tag="",
))
