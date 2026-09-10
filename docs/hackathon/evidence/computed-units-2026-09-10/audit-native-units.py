"""Read only the two explicitly bound evaluation sessions; export tool metadata."""
from pathlib import Path
import compression.zstd as zstd
import hashlib
import json


def main():
    repo = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
    scratch = repo / ".context/t13-citation-live"
    output = Path(__file__).parent
    findings = {}
    for case in ("A3", "B2"):
        request = json.loads((scratch / f"{case}-request.json").read_text())
        session = Path(json.loads((scratch / f"{case}-session.json").read_text())["session_path"])
        raw = (session / "session.v2.jsonl.zstd").read_bytes()
        text = zstd.decompress(raw).decode()
        assert request["prompt"] in text
        rows = [json.loads(line) for line in text.splitlines()]
        assert rows[-1]["type"] == "turn/end"
        catalogs = []
        for row in rows:
            if row["type"] != "tool/result":
                continue
            for block in row["data"]["message"]["content"]:
                for item in block.get("content", []):
                    if item.get("type") != "text":
                        continue
                    try:
                        body = json.loads(item["text"])
                    except ValueError:
                        continue
                    if isinstance(body, dict) and "source_context" in body and "capabilities" in body:
                        catalogs.append(body)
        assert catalogs
        money_fields = []

        def visit(value, path):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in {"money_unit", "currency", "amount_unit"}:
                        money_fields.append(path + "." + key)
                    visit(child, path + "." + key)
            elif isinstance(value, list):
                for i, child in enumerate(value):
                    visit(child, f"{path}[{i}]")

        visit(catalogs, "catalogs")
        assert not money_fields, money_fields
        findings[case] = {
            "native_log_sha256": hashlib.sha256(raw).hexdigest(),
            "session_id": session.name,
            "capability_returns": len(catalogs),
            "source_context": [c["source_context"] for c in catalogs],
            "currency_or_amount_unit_fields_in_actual_catalog": money_fields,
            "finding": "CNY/minor claims are unsupported; the actual catalog declares no monetary unit.",
        }
    (output / "native-unit-source-audit.json").write_text(json.dumps(findings, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"cases": list(findings), "finding": "unsupported unit attribution confirmed"}))


if __name__ == "__main__":
    main()
