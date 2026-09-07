"""Setup-only sealed synthetic query fixture. Does not change goldens or SQL."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from backend.analytics_query_fixture import create_channel_followup_fixture
from backend.contracts.analytics_query import ChannelFollowupSnapshot

SNAPSHOT = Path(__file__).resolve().parents[2] / "backend/tests/fixtures/analytics_channel_followup_v1.json"


def main() -> None:
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_absolute():
        raise SystemExit("usage: python setup-query-fixture.py /absolute/private/empty/directory")
    snapshot = ChannelFollowupSnapshot.model_validate_json(SNAPSHOT.read_bytes())
    print(json.dumps(asdict(create_channel_followup_fixture(sys.argv[1], snapshot))))


if __name__ == "__main__":
    main()
