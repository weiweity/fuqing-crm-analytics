"""Competition analysis assets and isolated board namespace.

HTTP registration stays with the integrator. This package is NOT_CONNECTED.
"""

from backend.services.analytics.competition_assets.service import (
    HTTP_WIRING,
    CompetitionAssetService,
    as_competition_error,
    operation_payload_hash,
    stable_id,
)
from backend.services.analytics.competition_assets.store import (
    APPLICATION_ID,
    CompetitionAssetStore,
)

__all__ = [
    "APPLICATION_ID",
    "HTTP_WIRING",
    "CompetitionAssetService",
    "CompetitionAssetStore",
    "as_competition_error",
    "operation_payload_hash",
    "stable_id",
]
