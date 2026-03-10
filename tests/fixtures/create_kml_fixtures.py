"""
Script to create KML/KMZ test fixtures.

Run this script to generate the fixture files needed for KML and KMZ parser tests.

Usage:
    python tests/fixtures/create_kml_fixtures.py
"""

import zipfile
from pathlib import Path


def main():
    """Create KML and KMZ fixture files for testing."""
    fixtures_dir = Path(__file__).parent

    # Read the simple.kml content to embed in the KMZ
    simple_kml_path = fixtures_dir / "simple.kml"
    simple_kml_content = simple_kml_path.read_text()

    # Create simple.kmz containing doc.kml
    kmz_path = fixtures_dir / "simple.kmz"
    with zipfile.ZipFile(kmz_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", simple_kml_content)

    print(f"Created {kmz_path}")
    print(f"Size: {kmz_path.stat().st_size} bytes")

    # Verify
    with zipfile.ZipFile(kmz_path, "r") as zf:
        print(f"Contents: {zf.namelist()}")

    print("All KML/KMZ fixtures created successfully.")


if __name__ == "__main__":
    main()
