#!/usr/bin/env python3
"""Generate sample files for testing Entmoot uploads.

Creates:
  - property_boundary.kmz (from the .kml file)
  - elevation.tif (synthetic DEM GeoTIFF covering the sample property)

Run from the samples/ directory:
    python create_samples.py
"""

import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds

HERE = Path(__file__).parent


def create_kmz():
    """Package the KML file into a KMZ archive."""
    kml_path = HERE / "property_boundary.kml"
    kmz_path = HERE / "property_boundary.kmz"
    with zipfile.ZipFile(kmz_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(kml_path, "doc.kml")
    print(f"Created {kmz_path} ({kmz_path.stat().st_size} bytes)")


def create_geotiff():
    """Create a synthetic elevation GeoTIFF covering the sample property.

    Generates a 100x100 pixel raster with gentle terrain:
    - Base elevation ~1650m (Denver area)
    - Gradual slope rising to the northwest
    - Small ridge feature
    """
    tif_path = HERE / "elevation.tif"

    # Bounding box slightly larger than the property polygon
    west, south, east, north = -104.823, 39.744, -104.816, 39.750
    width, height = 100, 100

    transform = from_bounds(west, south, east, north, width, height)

    # Create terrain: base elevation + slope + ridge
    x = np.linspace(0, 1, width)
    y = np.linspace(0, 1, height)
    xx, yy = np.meshgrid(x, y)

    elevation = (
        1650.0  # base elevation (meters)
        + 15.0 * yy  # gentle north-south slope
        + 8.0 * xx  # slight east-west slope
        + 5.0 * np.sin(xx * 3.14) * np.cos(yy * 3.14)  # ridge
        + np.random.default_rng(42).normal(0, 0.3, (height, width))  # noise
    )
    elevation = elevation.astype(np.float32)

    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(elevation, 1)
        dst.update_tags(AREA_OR_POINT="Point")
        dst.set_band_description(1, "Elevation (meters)")

    print(f"Created {tif_path} ({tif_path.stat().st_size} bytes)")


if __name__ == "__main__":
    create_kmz()
    create_geotiff()
    print("\nAll sample files created. You can upload these through the Entmoot UI.")
