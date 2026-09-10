"""Exercise actual pinned old/new readers against a tiny isolated mixed store."""
from pathlib import Path
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

OLD_HEAD = "24a3722b6681bd58ec8045101078be3d41984e75"


def main():
    repo = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
    old = repo.parent / "competition-product-readiness"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=old, text=True).strip() == OLD_HEAD
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=old, text=True).strip()
    create = """
from pathlib import Path
import json, sys
from backend.services.analytics.competition_diagnosis.synthetic import demo_snapshot, materialize_synthetic_source
from backend.services.analytics.competition_diagnosis.computed import compute_result
from backend.services.analytics.competition_diagnosis.store import ComputedResultStore
from backend.tests.test_competition_computed_results import PRINCIPAL, condition
root=Path(sys.argv[1]); name=sys.argv[2]
folder=root/name; folder.mkdir(mode=0o700)
source=materialize_synthetic_source(folder,demo_snapshot())
result=compute_result(source,PRINCIPAL,condition(),"diag.gsv",session_id=name,request_id="r1")
result=ComputedResultStore(root/"state").save(PRINCIPAL,name,"r1","f"*64,result)
print(json.dumps(result.model_dump(mode="json")))
"""
    read = """
from pathlib import Path
import json, sys
from backend.services.analytics.competition_diagnosis.store import ComputedResultStore
from backend.services.analytics.access import AnalyticsError
from backend.tests.test_competition_computed_results import PRINCIPAL
try:
    record=ComputedResultStore(Path(sys.argv[1])/"state").get(PRINCIPAL,sys.argv[2])
    print(json.dumps({"status":"READ","facts":record.facts}))
except AnalyticsError as error:
    print(json.dumps({"status":"REJECT","code":error.code,"http_status":error.status}))
"""
    with tempfile.TemporaryDirectory(prefix="unit-reader-compat-") as directory:
        root = Path(directory)
        (root / "state").mkdir(mode=0o700)

        def run(checkout, code, arg):
            process = subprocess.run([sys.executable, "-c", code, directory, arg], cwd=root,
                                     env={"PATH": os.defpath, "PYTHONPATH": str(checkout), "PYTHON_DOTENV_DISABLED": "1",
                                          "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"},
                                     check=True, text=True, capture_output=True, timeout=30)
            return json.loads(process.stdout)

        first = run(old, create, "legacy-v1")
        assert first["facts"]["schema_version"] == "competition-gsv-facts/v1"
        assert "money_unit" not in first["facts"]
        path = root / "state/diagnosis_results.sqlite3"
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            original_bytes = conn.execute("SELECT result_json FROM results").fetchone()[0]
        new_reads_old = run(repo, read, first["analysis_id"])
        assert new_reads_old == {"status": "READ", "facts": first["facts"]}
        second = run(repo, create, "current-v2")
        assert second["facts"]["schema_version"] == "competition-gsv-facts/v2"
        assert second["facts"]["money_unit"]["status"] == "UNKNOWN"
        assert first["data_digest"] == second["data_digest"]
        new_reads_new = run(repo, read, second["analysis_id"])
        assert new_reads_new == {"status": "READ", "facts": second["facts"]}
        old_reads_new = run(old, read, second["analysis_id"])
        assert old_reads_new == {"status": "REJECT", "code": "BINDING_CORRUPT", "http_status": 409}
        assert run(old, read, first["analysis_id"]) == new_reads_old
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            assert conn.execute("SELECT count(*) FROM results").fetchone()[0] == 2
            assert conn.execute("SELECT result_json FROM results WHERE analysis_id=?", (first["analysis_id"],)).fetchone()[0] == original_bytes
        report = {"old_head": OLD_HEAD, "old_reader_new_v2": old_reads_new,
                  "new_reader_old_v1": "PASS; original JSON and evidence unchanged",
                  "new_reader_new_v2": "PASS; separate process",
                  "old_reader_old_v1_after_new_write": "PASS",
                  "unchanged_source_digest": first["data_digest"],
                  "state": "temporary synthetic SQLite only; no candidate or archived database touched",
                  "rollback_requirement": "Restore an isolated pre-upgrade state with the old reader; preserve all new state."}
        Path(__file__).with_name("reader-compatibility.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
