"""Module 02 tests: contracts exist, are internally consistent, and the
check_specs script actually catches violations (not merely passes by
default)."""
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CHECK_SPECS = ROOT / "tools" / "check_specs.py"
REAL_FIXTURE = ROOT / "specs" / "domains" / "fixtures" / "farm-001.json"
BROKEN_FIXTURE = ROOT / "tests" / "fixtures_broken" / "farm-broken.json"


def test_contract_files_exist():
    for rel in [
        "docs/conventions.md",
        "specs/core/schema.yaml",
        "specs/core/enums.md",
        "specs/core/openapi.yaml",
        "specs/core/repository-interface.md",
        "specs/domains/fixtures/farm-001.json",
        "tools/check_specs.py",
        ".gitattributes",
        "modules/02-contracts/STATUS",
    ]:
        assert (ROOT / rel).exists(), f"missing: {rel}"


def test_check_specs_passes_on_real_fixture():
    result = subprocess.run(
        [sys.executable, str(CHECK_SPECS), "--fixture", str(REAL_FIXTURE)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"check_specs unexpectedly failed on {REAL_FIXTURE.name}:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_check_specs_rejects_broken_fixture():
    result = subprocess.run(
        [sys.executable, str(CHECK_SPECS), "--fixture", str(BROKEN_FIXTURE)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode != 0, (
        "check_specs unexpectedly passed on the deliberately-broken fixture — "
        "the enforcement script is not actually enforcing.\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "not a UUIDv4" in combined
    assert "not in enum 'language_code'" in combined
    assert "does not exist in Farmer.id" in combined


def test_schema_and_openapi_agree_on_entity_names():
    schema = yaml.safe_load((ROOT / "specs/core/schema.yaml").read_text())
    openapi = yaml.safe_load((ROOT / "specs/core/openapi.yaml").read_text())
    entities = set(schema["entities"].keys())
    openapi_schemas = set(openapi["components"]["schemas"].keys())
    for name in ["Farmer", "Field", "CropRecommendation", "IrrigationAdvice",
                 "DiseaseRiskAlert", "Advisory", "FeedbackEntry"]:
        assert name in entities, f"schema.yaml missing entity {name}"
        assert name in openapi_schemas, f"openapi.yaml missing schema {name}"


def test_module_02_has_status_marker():
    status = (ROOT / "modules" / "02-contracts" / "STATUS").read_text().strip()
    assert status in {"not-started", "in-progress", "done"}
