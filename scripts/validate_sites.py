#!/usr/bin/env python3
"""Validate AI Village Directory data files.

Checks:
- data/sites.json matches schema/data-sites.schema.json
- metadata.total_sites == len(sites)
- metadata.live_sites == count(status == "live")
- site IDs are unique positive integers
- sites.json (compatibility array or canonical mirror) matches the canonical sites list
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CANON_PATH = ROOT / "data" / "sites.json"
COMPAT_PATH = ROOT / "sites.json"
SCHEMA_PATH = ROOT / "schema" / "data-sites.schema.json"


def load_json(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Missing required file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_against_schema(data, schema):
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        lines = ["Schema validation errors (data/sites.json):"]
        for err in errors:
            loc = "/".join(str(p) for p in err.path)
            lines.append(f" - {loc or '<root>'}: {err.message}")
        raise ValueError("\n".join(lines))


def ensure_metadata_consistency(data):
    errors = []
    sites = data.get("sites", [])
    metadata = data.get("metadata", {})

    total_sites = len(sites)
    if metadata.get("total_sites") != total_sites:
        errors.append(
            f"metadata.total_sites={metadata.get('total_sites')} does not match len(sites)={total_sites}"
        )

    live_sites = sum(1 for s in sites if s.get("status") == "live")
    if metadata.get("live_sites") != live_sites:
        errors.append(
            f"metadata.live_sites={metadata.get('live_sites')} does not match count(status=='live')={live_sites}"
        )

    ids = [s.get("id") for s in sites]
    if len(ids) != len(set(ids)):
        errors.append("site ids are not unique")

    if any((not isinstance(i, int)) or i < 1 for i in ids):
        errors.append("all site ids must be positive integers")

    return errors


def ensure_compatibility_alignment(canon, compat):
    errors = []

    canon_sites = canon.get("sites", [])

    # Legacy compatibility view: array of site objects with a subset of fields
    if isinstance(compat, list):
        if len(compat) != len(canon_sites):
            errors.append(
                f"sites.json length={len(compat)} does not match data/sites.json sites length={len(canon_sites)}"
            )
            return errors

        fields = ["name", "repo", "url", "type", "description", "status"]

        for idx, (c_site, s_site) in enumerate(zip(canon_sites, compat)):
            for field in fields:
                c_val = c_site.get(field)
                s_val = s_site.get(field)
                if c_val != s_val:
                    errors.append(
                        f"mismatch at index {idx} field '{field}': data/sites.json has {c_val!r}, sites.json has {s_val!r}"
                    )

        return errors

    if not isinstance(compat, dict):
        errors.append("sites.json must be either a JSON array or an object mirroring data/sites.json")
        return errors

    if "metadata" not in compat or "sites" not in compat:
        errors.append("sites.json must include 'metadata' and 'sites' when provided as an object")
        return errors

    if compat.get("metadata") != canon.get("metadata"):
        errors.append("metadata in sites.json does not match data/sites.json")

    compat_sites = compat.get("sites")
    if not isinstance(compat_sites, list):
        errors.append("sites.json 'sites' must be a list when provided as an object")
        return errors

    if len(compat_sites) != len(canon_sites):
        errors.append(
            f"sites.json length={len(compat_sites)} does not match data/sites.json sites length={len(canon_sites)}"
        )
        return errors

    fields = ["id", "name", "repo", "url", "type", "section", "description", "status"]

    for idx, (c_site, s_site) in enumerate(zip(canon_sites, compat_sites)):
        for field in fields:
            if c_site.get(field) != s_site.get(field):
                errors.append(
                    f"mismatch at index {idx}: site differs between data/sites.json and sites.json"
                )
                break

    return errors


def main() -> int:
    try:
        schema = load_json(SCHEMA_PATH)
        canon = load_json(CANON_PATH)
        compat = load_json(COMPAT_PATH)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON: {e}")
        return 1

    try:
        validate_against_schema(canon, schema)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    errors = []
    errors.extend(ensure_metadata_consistency(canon))
    errors.extend(ensure_compatibility_alignment(canon, compat))

    if errors:
        print("Validation failed with the following issues:")
        for err in errors:
            print(f" - {err}")
        return 1

    print("All directory checks passed for data/sites.json and sites.json.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
