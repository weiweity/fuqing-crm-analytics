"""Generate real computed synthetic v2 fixtures; never rewrite the v1 golden."""
import json
from pathlib import Path
import tempfile

from backend.services.analytics.competition_diagnosis.computed import compute_result
from backend.services.analytics.competition_diagnosis.synthetic import demo_snapshot, materialize_synthetic_source
from backend.tests.test_competition_computed_results import PRINCIPAL, condition


def fixtures():
    cases = {}
    with tempfile.TemporaryDirectory(prefix="computed-unit-fixtures-") as directory:
        for name in ("unknown", "major", "minor"):
            folder = Path(directory) / name
            folder.mkdir(mode=0o700)
            payload = demo_snapshot()
            if name != "unknown":
                payload["money_unit"] = {"status": "KNOWN", "currency": "CNY", "amount_unit": name}
            source = materialize_synthetic_source(folder, payload)
            result = compute_result(source, PRINCIPAL, condition(), "diag.gsv", session_id="unit-ui", request_id=name)
            result = result.model_copy(update={"analysis_id": "analysis_diag_" + result.run_id.removeprefix("run_diag_")})
            cases[name] = result.model_dump(mode="json")
    return cases


if __name__ == "__main__":
    Path(__file__).with_name("unit-results.json").write_text(json.dumps(fixtures(), ensure_ascii=False, indent=2) + "\n")
