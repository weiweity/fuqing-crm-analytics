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


def prewarm_common_windows() -> None:
    """Fill rfm_analysis_cache for 365d / 180d / MTD ending at warehouse cutoff."""

    from backend.services.dual_conn import read_request_context
    from backend.services.health.rfm_analysis import get_rfm_analysis

    with read_request_context("prewarm"):
        cutoff = warehouse_cutoff_date()
        if cutoff is None:
            logger.warning("RFM prewarm skipped: orders.max(pay_time) is empty")
            return
        month_start = cutoff.replace(day=1)
        windows = [
            (cutoff - timedelta(days=364), cutoff),
            (cutoff - timedelta(days=179), cutoff),
            (month_start, cutoff),
        ]
        for start, end in windows:
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
