#!/usr/bin/env python3
"""Generate a versioned OpenAPI schema from the FastAPI application.

Usage:
    python scripts/generate_openapi.py          # writes docs/openapi.yaml
    python scripts/generate_openapi.py --check   # exits non-zero if out of date
"""

import argparse
import sys
from pathlib import Path

# Ensure src/ is importable when running the script directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml  # type: ignore[import-untyped]

from entmoot.api.main import app


def main() -> None:
    """Generate the OpenAPI schema JSON file."""
    parser = argparse.ArgumentParser(description="Generate OpenAPI schema")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check that the committed schema is up to date (for CI).",
    )
    args = parser.parse_args()

    schema = app.openapi()

    output_path = Path(__file__).resolve().parent.parent / "docs" / "openapi.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generated = yaml.dump(schema, sort_keys=False, allow_unicode=True)

    if args.check:
        if not output_path.exists():
            print(f"ERROR: {output_path} does not exist. Run this script without --check first.")
            sys.exit(1)
        existing_schema = yaml.safe_load(output_path.read_text())
        if existing_schema != schema:
            print(f"ERROR: {output_path} is out of date. Regenerate with:")
            print(f"  python {Path(__file__).name}")
            sys.exit(1)
        print("OpenAPI schema is up to date.")
        return

    output_path.write_text(generated)
    print(f"Wrote OpenAPI schema to {output_path}")


if __name__ == "__main__":
    main()
