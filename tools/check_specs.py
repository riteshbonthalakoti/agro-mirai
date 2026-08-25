#!/usr/bin/env python3
"""Enforce the contracts under specs/.

Three checks, per doctrine — generated/enforced, never just agreed:

  1. The golden fixture parses and validates against schema.yaml.
  2. Every enum value used in the fixture or openapi.yaml is documented
     in enums.md.
  3. Every $ref in openapi.yaml resolves to something that exists in the
     document.

Exit code is non-zero on any failure. Invocation:

    python tools/check_specs.py                       # default paths
    python tools/check_specs.py --fixture PATH        # override fixture

Used both from the Module 02 pytest suite and stand-alone.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "specs" / "core" / "schema.yaml"
ENUMS_PATH = ROOT / "specs" / "core" / "enums.md"
OPENAPI_PATH = ROOT / "specs" / "core" / "openapi.yaml"
DEFAULT_FIXTURE = ROOT / "specs" / "domains" / "fixtures" / "farm-001.json"


UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

FIXTURE_COLLECTION_TO_ENTITY = {
    "farmers": "Farmer",
    "fields": "Field",
    "weather_readings": "WeatherReading",
    "soil_samples": "SoilSample",
    "ndvi_readings": "NDVIReading",
    "crop_recommendations": "CropRecommendation",
    "irrigation_advices": "IrrigationAdvice",
    "disease_risk_alerts": "DiseaseRiskAlert",
    "advisories": "Advisory",
    "feedback_entries": "FeedbackEntry",
}


class SpecError(Exception):
    """A single spec violation. Aggregated by the caller."""


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_enum_doc(text: str) -> dict[str, set[str]]:
    """Extract enum name -> set of documented values from enums.md.

    Sections are ``## `<enum_name>``` headings; values are bullet lines
    whose first backtick-quoted token is the value.
    """
    enums: dict[str, set[str]] = {}
    current: str | None = None
    heading_re = re.compile(r"^##\s+`([A-Za-z_][A-Za-z0-9_]*)`\s*$")
    bullet_re = re.compile(r"^\s*[-*]\s+`([^`]+)`")
    for line in text.splitlines():
        m = heading_re.match(line)
        if m:
            current = m.group(1)
            enums.setdefault(current, set())
            continue
        if current is None:
            continue
        b = bullet_re.match(line)
        if b:
            enums[current].add(b.group(1))
    return enums


def _validate_value(value: Any, spec: dict[str, Any], path: str) -> list[str]:
    errs: list[str] = []
    t = spec.get("type")
    if value is None:
        errs.append(f"{path}: null value not permitted")
        return errs
    if t == "uuid":
        if not (isinstance(value, str) and UUID_RE.match(value)):
            errs.append(f"{path}: not a UUIDv4 string ({value!r})")
    elif t == "timestamp":
        if not isinstance(value, str):
            errs.append(f"{path}: timestamp must be a string")
        else:
            try:
                datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                errs.append(
                    f"{path}: timestamp must be ISO 8601 UTC 'YYYY-MM-DDTHH:MM:SSZ' ({value!r})"
                )
    elif t == "date":
        if not isinstance(value, str):
            errs.append(f"{path}: date must be a string")
        else:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                errs.append(f"{path}: date must be 'YYYY-MM-DD' ({value!r})")
    elif t == "string":
        if not isinstance(value, str):
            errs.append(f"{path}: expected string, got {type(value).__name__}")
    elif t == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            errs.append(f"{path}: expected int, got {type(value).__name__}")
    elif t == "float":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errs.append(f"{path}: expected number, got {type(value).__name__}")
    elif t == "bool":
        if not isinstance(value, bool):
            errs.append(f"{path}: expected bool, got {type(value).__name__}")
    elif t == "list":
        if not isinstance(value, list):
            errs.append(f"{path}: expected list, got {type(value).__name__}")
        else:
            item_spec = spec.get("item", {})
            for i, item in enumerate(value):
                errs.extend(_validate_value(item, item_spec, f"{path}[{i}]"))
    else:
        errs.append(f"{path}: unknown type {t!r}")

    if not errs:
        rng = spec.get("range")
        if rng is not None and isinstance(value, (int, float)):
            lo, hi = rng
            if value < lo or value > hi:
                errs.append(f"{path}: value {value} outside range {rng}")
        mn = spec.get("min")
        if mn is not None and isinstance(value, (int, float)) and value < mn:
            errs.append(f"{path}: value {value} below min {mn}")
    return errs


def _validate_entity(
    entity_name: str,
    record: dict[str, Any],
    schema: dict[str, Any],
    enums: dict[str, set[str]],
    known_ids: dict[str, set[str]],
    used_enum_values: dict[str, set[str]],
    idx: int,
) -> list[str]:
    """Validate one fixture record against its schema entity."""
    errs: list[str] = []
    entities = schema["entities"]
    if entity_name not in entities:
        errs.append(f"{entity_name}[{idx}]: entity not defined in schema")
        return errs
    espec = entities[entity_name]
    fields = espec["fields"]
    allowed = set(fields.keys())

    for extra in set(record.keys()) - allowed:
        errs.append(f"{entity_name}[{idx}].{extra}: unknown field")

    for fname, fspec in fields.items():
        path = f"{entity_name}[{idx}].{fname}"
        if fname not in record:
            if fspec.get("required"):
                errs.append(f"{path}: required field missing")
            continue
        value = record[fname]
        errs.extend(_validate_value(value, fspec, path))

        enum_name = fspec.get("enum")
        if enum_name:
            if isinstance(value, str):
                used_enum_values.setdefault(enum_name, set()).add(value)
                if enum_name in enums and value not in enums[enum_name]:
                    errs.append(
                        f"{path}: value {value!r} not in enum '{enum_name}'"
                    )
        if fspec.get("type") == "list" and fspec.get("item", {}).get("enum"):
            enm = fspec["item"]["enum"]
            if isinstance(value, list):
                for v in value:
                    if isinstance(v, str):
                        used_enum_values.setdefault(enm, set()).add(v)
                        if enm in enums and v not in enums[enm]:
                            errs.append(
                                f"{path}: value {v!r} not in enum '{enm}'"
                            )

        ref = fspec.get("ref")
        if ref and isinstance(value, str):
            target_entity, target_field = ref.split(".")
            if value not in known_ids.get(target_entity, set()):
                errs.append(
                    f"{path}: ref value {value!r} does not exist in "
                    f"{target_entity}.{target_field}"
                )

    return errs


def _collect_openapi_enums_and_refs(node: Any, enums_used: dict[str, set[str]], refs: list[str]) -> None:
    """Walk the openapi tree, collecting inline enum values and $refs.

    Enum values are collected only when the sibling `type: string` is
    present (avoids sweeping up non-vocabulary enums).
    """
    if isinstance(node, dict):
        if "$ref" in node and isinstance(node["$ref"], str):
            refs.append(node["$ref"])
        if node.get("type") == "string" and isinstance(node.get("enum"), list):
            for v in node["enum"]:
                if isinstance(v, str):
                    enums_used.setdefault("__openapi_string_enums__", set()).add(v)
        for v in node.values():
            _collect_openapi_enums_and_refs(v, enums_used, refs)
    elif isinstance(node, list):
        for item in node:
            _collect_openapi_enums_and_refs(item, enums_used, refs)


def _resolve_ref(ref: str, doc: dict[str, Any]) -> bool:
    if not ref.startswith("#/"):
        return False
    node: Any = doc
    for part in ref[2:].split("/"):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return False
    return True


def check_specs(fixture_path: Path) -> list[str]:
    problems: list[str] = []
    try:
        schema = _load_yaml(SCHEMA_PATH)
    except Exception as e:
        return [f"schema.yaml: cannot load ({e})"]
    try:
        openapi = _load_yaml(OPENAPI_PATH)
    except Exception as e:
        return [f"openapi.yaml: cannot load ({e})"]
    try:
        enums = _parse_enum_doc(ENUMS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"enums.md: cannot load ({e})"]
    try:
        fixture = _load_json(fixture_path)
    except Exception as e:
        return [f"{fixture_path.name}: cannot load ({e})"]

    # --- Check 1: fixture validates against schema ---
    known_ids: dict[str, set[str]] = {}
    for collection, entity_name in FIXTURE_COLLECTION_TO_ENTITY.items():
        for rec in fixture.get(collection, []):
            if isinstance(rec, dict) and isinstance(rec.get("id"), str):
                known_ids.setdefault(entity_name, set()).add(rec["id"])

    used_enum_values: dict[str, set[str]] = {}
    for collection, entity_name in FIXTURE_COLLECTION_TO_ENTITY.items():
        records = fixture.get(collection, [])
        if not isinstance(records, list):
            problems.append(f"{collection}: expected list of records")
            continue
        for idx, rec in enumerate(records):
            if not isinstance(rec, dict):
                problems.append(f"{collection}[{idx}]: expected object")
                continue
            problems.extend(
                _validate_entity(
                    entity_name, rec, schema, enums, known_ids, used_enum_values, idx
                )
            )

    # --- Check 2: enum values used are documented ---
    all_documented: set[str] = set().union(*enums.values()) if enums else set()

    for enum_name, values in used_enum_values.items():
        if enum_name not in enums:
            problems.append(
                f"enums.md: enum {enum_name!r} referenced by schema but not documented"
            )
            continue
        undocumented = values - enums[enum_name]
        for v in sorted(undocumented):
            problems.append(
                f"enums.md: value {v!r} used in fixture for enum '{enum_name}' but not documented"
            )

    openapi_enums: dict[str, set[str]] = {}
    openapi_refs: list[str] = []
    _collect_openapi_enums_and_refs(openapi, openapi_enums, openapi_refs)
    for v in sorted(openapi_enums.get("__openapi_string_enums__", set())):
        if v not in all_documented:
            problems.append(
                f"enums.md: value {v!r} used in openapi.yaml but not documented in any enum"
            )

    # --- Check 3: every $ref in openapi.yaml resolves ---
    for ref in openapi_refs:
        if not _resolve_ref(ref, openapi):
            problems.append(f"openapi.yaml: $ref {ref!r} does not resolve")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help=f"Fixture to validate (default: {DEFAULT_FIXTURE.relative_to(ROOT)})",
    )
    args = parser.parse_args(argv)

    problems = check_specs(args.fixture)
    if problems:
        print("check_specs: FAIL", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"check_specs: OK ({args.fixture.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
