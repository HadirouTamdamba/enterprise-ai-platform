#!/usr/bin/env python3
"""Import YAML prompt templates from prompts/ into a project's Prompt Registry.

Usage:
    python scripts/import_prompts.py --api http://localhost:8000/api/v1 \
        --email admin@example.com --password ... --project-id <uuid>
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _request(url: str, data: dict | None = None, token: str = "", form: bool = False):
    if form and data:
        body = "&".join(f"{k}={v}" for k, v in data.items()).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
    else:
        body = json.dumps(data).encode() if data else None
        headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req) as response:  # noqa: S310 — operator-provided URL
        return json.loads(response.read())


def _parse_simple_yaml(path: Path) -> dict:
    """Parse the flat prompt YAML files without a YAML dependency."""
    data: dict = {}
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("template: |"):
            block = []
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                block.append(lines[i][2:])
                i += 1
            data["template"] = "\n".join(block).strip()
            continue
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                data[key.strip()] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
            else:
                data[key.strip()] = value
        i += 1
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000/api/v1")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--project-id", required=True)
    args = parser.parse_args()

    tokens = _request(
        f"{args.api}/auth/login",
        {"username": args.email, "password": args.password},
        form=True,
    )
    token = tokens["access_token"]

    imported = 0
    for yaml_file in sorted(PROMPTS_DIR.rglob("*.yaml")):
        spec = _parse_simple_yaml(yaml_file)
        payload = {
            "name": spec.get("name", yaml_file.stem),
            "description": spec.get("description", ""),
            "project_id": args.project_id,
            "template": spec.get("template", ""),
            "variables": spec.get("variables", []),
            "model_hint": spec.get("model_hint", ""),
            "tags": ["imported"],
        }
        try:
            _request(f"{args.api}/prompts", payload, token=token)
            imported += 1
            print(f"imported: {payload['name']}")  # noqa: T201 — CLI
        except Exception as exc:  # conflict = already imported
            print(f"skipped {payload['name']}: {exc}")  # noqa: T201 — CLI
    print(f"done — {imported} prompts imported")  # noqa: T201 — CLI
    return 0


if __name__ == "__main__":
    sys.exit(main())
