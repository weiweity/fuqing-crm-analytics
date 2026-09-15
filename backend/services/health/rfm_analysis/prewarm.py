"""Background RFM cache prewarm for the dashboard's default windows."""

from __future__ import annotations

from datetime import date, timedelta
import logging
import os
import threading

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


def dashboard_windows(cutoff: date) -> list[tuple[date, date]]:
    """Same presets as the filter bar, with cutoff as the last data day."""
    yesterday = cutoff
    year = cutoff.year
    month_start = cutoff.replace(day=1)
    ytd_start = date(year, 1, 1)
    weekday = cutoff.weekday()  # Mon=0
    week_start = cutoff - timedelta(days=weekday)
    windows = [
        (yesterday, yesterday),
        (week_start, yesterday),
        (month_start, yesterday),
        (ytd_start, yesterday),
        (yesterday - timedelta(days=179), yesterday),
        (yesterday - timedelta(days=364), yesterday),
        (date(year, 1, 1), min(date(year, 3, 31), yesterday)),
        (date(year, 4, 1), min(date(year, 6, 30), yesterday)),
        (date(year, 7, 1), min(date(year, 9, 30), yesterday)),
        (date(year, 10, 1), min(date(year, 12, 31), yesterday)),
    ]
    seen: set[tuple[date, date]] = set()
    out: list[tuple[date, date]] = []
    for start, end in windows:
        if start > end:
            continue
        key = (start, end)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
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
