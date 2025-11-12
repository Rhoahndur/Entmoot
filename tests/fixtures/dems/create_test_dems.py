"""
Utility script to create test DEM fixtures.

This script creates synthetic DEMs for testing purposes.
"""

import numpy as np
from pathlib import Path

try:
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.crs import CRS
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False


def create_simple_dem(
    output_path: Path,
    width: int = 100,
    height: int = 100,
    resolution: float = 1.0,
) -> None:
    """
    Create a simple test DEM with gradual slope.

    Args:
        output_path: Output file path
        width: Width in pixels
        height: Height in pixels
        resolution: Pixel resolution
    """
    if not RASTERIO_AVAILABLE:
        raise ImportError("rasterio required to create test DEMs")

    # Create simple elevation gradient (flat slope)
    elevation = np.zeros((height, width), dtype=np.float32)
    for i in range(height):
        elevation[i, :] = 100 + i * 0.5  # Gradual slope

    # Define bounds
    bounds = (0, 0, width * resolution, height * resolution)
    transform = from_bounds(*bounds, width, height)

    # Write GeoTIFF
    with rasterio.open(
        output_path,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=1,
        dtype=elevation.dtype,
        crs=CRS.from_epsg(32633),  # UTM Zone 33N
        transform=transform,
        nodata=-9999,
    ) as dst:
        dst.write(elevation, 1)

    print(f"Created simple DEM: {output_path}")


def create_dem_with_gaps(
    output_path: Path,
    width: int = 100,
    height: int = 100,
    resolution: float = 1.0,
    gap_percentage: float = 10.0,
) -> None:
    """
    Create a test DEM with no-data gaps.

    Args:
        output_path: Output file path
        width: Width in pixels
        height: Height in pixels
        resolution: Pixel resolution
        gap_percentage: Percentage of pixels to set as no-data
    """
    if not RASTERIO_AVAILABLE:
        raise ImportError("rasterio required to create test DEMs")

    # Create elevation data
    elevation = np.zeros((height, width), dtype=np.float32)
    for i in range(height):
        elevation[i, :] = 100 + i * 0.5

    # Add random gaps
    num_gaps = int(width * height * gap_percentage / 100)
    gap_indices = np.random.choice(width * height, num_gaps, replace=False)
    elevation.flat[gap_indices] = -9999

    # Define bounds
    bounds = (0, 0, width * resolution, height * resolution)
    transform = from_bounds(*bounds, width, height)

    # Write GeoTIFF
    with rasterio.open(
        output_path,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=1,
        dtype=elevation.dtype,
        crs=CRS.from_epsg(32633),
        transform=transform,
        nodata=-9999,
    ) as dst:
        dst.write(elevation, 1)

    print(f"Created DEM with gaps: {output_path}")


def create_hilly_dem(
    output_path: Path,
    width: int = 100,
    height: int = 100,
    resolution: float = 1.0,
) -> None:
    """
    Create a test DEM with hills (sinusoidal terrain).

    Args:
        output_path: Output file path
        width: Width in pixels
        height: Height in pixels
        resolution: Pixel resolution
    """
    if not RASTERIO_AVAILABLE:
        raise ImportError("rasterio required to create test DEMs")

    # Create hilly terrain using sine waves
    x = np.linspace(0, 4 * np.pi, width)
    y = np.linspace(0, 4 * np.pi, height)
    X, Y = np.meshgrid(x, y)

    elevation = (
        200 +
        20 * np.sin(X) +
        15 * np.cos(Y) +
        10 * np.sin(X + Y)
    ).astype(np.float32)

    # Define bounds
    bounds = (0, 0, width * resolution, height * resolution)
    transform = from_bounds(*bounds, width, height)

    # Write GeoTIFF
    with rasterio.open(
        output_path,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=1,
        dtype=elevation.dtype,
        crs=CRS.from_epsg(32633),
        transform=transform,
        nodata=-9999,
    ) as dst:
        dst.write(elevation, 1)

    print(f"Created hilly DEM: {output_path}")


def create_ascii_grid(
    output_path: Path,
    width: int = 50,
    height: int = 50,
    cellsize: float = 1.0,
) -> None:
    """
    Create a test DEM in ASCII grid format.

    Args:
        output_path: Output file path
        width: Width in pixels
        height: Height in pixels
        cellsize: Cell size (resolution)
    """
    # Create elevation data
    elevation = np.zeros((height, width), dtype=np.float32)
    for i in range(height):
        elevation[i, :] = 100 + i * 0.3

    # Write ASCII grid
    with open(output_path, 'w') as f:
        # Write header
        f.write(f"ncols         {width}\n")
        f.write(f"nrows         {height}\n")
        f.write(f"xllcorner     0.0\n")
        f.write(f"yllcorner     0.0\n")
        f.write(f"cellsize      {cellsize}\n")
        f.write(f"NODATA_value  -9999\n")

        # Write data
        for row in elevation:
            f.write(" ".join(f"{val:.2f}" for val in row) + "\n")

    print(f"Created ASCII grid: {output_path}")


def create_small_dem(
    output_path: Path,
    width: int = 10,
    height: int = 10,
    resolution: float = 1.0,
) -> None:
    """
    Create a very small DEM for quick tests.

    Args:
        output_path: Output file path
        width: Width in pixels
        height: Height in pixels
        resolution: Pixel resolution
    """
    if not RASTERIO_AVAILABLE:
        raise ImportError("rasterio required to create test DEMs")

    # Create simple elevation data
    elevation = np.arange(width * height, dtype=np.float32).reshape(height, width)
    elevation = elevation + 100

    # Define bounds
    bounds = (0, 0, width * resolution, height * resolution)
    transform = from_bounds(*bounds, width, height)

    # Write GeoTIFF
    with rasterio.open(
        output_path,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=1,
        dtype=elevation.dtype,
        crs=CRS.from_epsg(32633),
        transform=transform,
        nodata=-9999,
    ) as dst:
        dst.write(elevation, 1)

    print(f"Created small DEM: {output_path}")


if __name__ == "__main__":
    # Create output directory
    output_dir = Path(__file__).parent
    output_dir.mkdir(exist_ok=True)

    if RASTERIO_AVAILABLE:
        # Create test fixtures
        create_simple_dem(output_dir / "simple_100x100.tif")
        create_dem_with_gaps(output_dir / "gaps_100x100.tif", gap_percentage=15.0)
        create_hilly_dem(output_dir / "hilly_100x100.tif")
        create_small_dem(output_dir / "small_10x10.tif")
        create_ascii_grid(output_dir / "simple_50x50.asc")
        print("\nAll test DEMs created successfully!")
    else:
        print("rasterio not available, skipping DEM creation")
