"""FUNNEL pack gate. Default on so 18082 and pytest keep current facts."""
from __future__ import annotations

import os


def funnel_pack_enabled() -> bool:
    raw = os.environ.get("SHINE_FUNNEL", "on")
    return str(raw).strip().lower() not in {"0", "false", "off", "no"}
