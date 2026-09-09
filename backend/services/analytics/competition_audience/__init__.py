"""Fixed last-year cohort tracking, recall candidates, and action drafts.

Offline service only. HTTP registration stays with the integrator.
Does not copy RFM/ETL; A2 features are called if injected, otherwise fixtures.
"""

from backend.services.analytics.competition_audience.errors import (
    CompetitionAudienceError,
)
from backend.services.analytics.competition_audience.features import (
    CohortFeatureRow,
    CohortFeatureSource,
    FeatureBundle,
    FixtureFeatureSource,
    ObservationEvent,
    load_cohort_features,
)
from backend.services.analytics.competition_audience.golden import T05_GOLD
from backend.services.analytics.competition_audience.service import (
    CompetitionAudienceService,
    preview_candidates,
    save_draft,
)

__all__ = [
    "CompetitionAudienceError",
    "CompetitionAudienceService",
    "CohortFeatureRow",
    "CohortFeatureSource",
    "FeatureBundle",
    "FixtureFeatureSource",
    "ObservationEvent",
    "T05_GOLD",
    "load_cohort_features",
    "preview_candidates",
    "save_draft",
]
