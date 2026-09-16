"""Background RFM cache prewarm for the dashboard's default windows."""

from __future__ import annotations

from datetime import date, timedelta
import logging
import os
import threading

from backend.semantic.time import DateRange, PeriodBuilder

logger = logging.getLogger(__name__)


def warehouse_cutoff_date() -> date | None:
    from backend.db.connection import get_connection
    from backend.services.dual_conn import get_request_connection, read_request_context

    def _query() -> date | None:
        conn = get_connection()
        row = conn.execute("SELECT CAST(max(pay_time) AS DATE) FROM orders").fetchone()
        if not row or row[0] is None:
            return None
        value = row[0]
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    if get_request_connection() is not None:
        return _query()
    with read_request_context("prewarm"):
        return _query()


def _clip_current_window(current: DateRange, cutoff: date) -> tuple[date, date] | None:
    if current.empty:
        return None
    start = date.fromisoformat(current.start)
    end = date.fromisoformat(current.end)
    if end > cutoff:
        end = cutoff
    if start > end:
        return None
    return start, end


def dashboard_windows(cutoff: date) -> list[tuple[date, date]]:
    """Filter-bar presets with warehouse cutoff as the last data day.

    PeriodBuilder treats ``today`` as exclusive (end = today - 1). Passing
    ``cutoff + 1 day`` makes yesterday equal the warehouse last day.
    Future quarter ranges are clipped or dropped so prewarm never asks
    for dates after cutoff.
    """
    today = cutoff + timedelta(days=1)
    builders = (
        PeriodBuilder.yesterday,
        PeriodBuilder.wtd,
        PeriodBuilder.mtd,
        PeriodBuilder.ytd,
        PeriodBuilder.last180days,
        PeriodBuilder.last365days,
        PeriodBuilder.q1,
        PeriodBuilder.q2,
        PeriodBuilder.q3,
        PeriodBuilder.q4,
    )
    seen: set[tuple[date, date]] = set()
    out: list[tuple[date, date]] = []
    for builder in builders:
        pair = _clip_current_window(builder(today=today)["current"], cutoff)
        if pair is None or pair in seen:
            continue
        seen.add(pair)
        out.append(pair)
    return out


def prewarm_common_windows() -> None:
    """Fill rfm_analysis_cache for every dashboard period ending at cutoff."""

    from backend.services.dual_conn import read_request_context
    from backend.services.health.rfm_analysis import get_rfm_analysis

    with read_request_context("prewarm"):
        cutoff = warehouse_cutoff_date()
        if cutoff is None:
            logger.warning("RFM prewarm skipped: orders.max(pay_time) is empty")
            return
        for start, end in dashboard_windows(cutoff):
            start_s, end_s = start.isoformat(), end.isoformat()
            try:
                get_rfm_analysis(
                    start_date=start_s,
                    end_date=end_s,
                    metric_type="GSV",
                    allow_live_compute=True,
                )
                logger.info("RFM prewarm ok %s..%s", start_s, end_s)
            except Exception as exc:  # noqa: BLE001
                logger.warning("RFM prewarm failed %s..%s: %s", start_s, end_s, exc)


def maybe_start_prewarm_thread() -> None:
    if os.environ.get("FQ_DB_MODE", "production") != "production":
        return
    if os.environ.get("FQ_RFM_PREWARM", "1") != "1":
        return
    thread = threading.Thread(target=prewarm_common_windows, name="rfm-prewarm", daemon=True)
    thread.start()
    logger.info("RFM prewarm thread started")
