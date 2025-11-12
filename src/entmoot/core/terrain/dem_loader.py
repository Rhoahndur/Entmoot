"""
DEM loader for reading Digital Elevation Models from various formats.

Supports GeoTIFF and ASCII grid formats with memory-efficient streaming
for large files.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple, Union
import warnings

import numpy as np
from pyproj import CRS

try:
    import rasterio
    from rasterio.windows import Window
    from rasterio.enums import Resampling
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

from entmoot.models.terrain import (
    DEMData,
    DEMMetadata,
    ElevationUnit,
)
from entmoot.core.errors import (
    ValidationError,
    ParseError,
)

logger = logging.getLogger(__name__)


class DEMLoader:
    """
    Load Digital Elevation Models from various file formats.

    Supports:
    - GeoTIFF (.tif, .tiff)
    - ASCII Grid (.asc, .grd)

    Features:
    - Memory-efficient streaming for large files
    - Automatic format detection
    - Metadata extraction
    - Unit conversion support
    """

    SUPPORTED_FORMATS = [".tif", ".tiff", ".asc", ".grd"]

    def __init__(self, max_memory_mb: int = 500) -> None:
        """
        Initialize DEM loader.

        Args:
            max_memory_mb: Maximum memory to use for loading (MB)
        """
        if not RASTERIO_AVAILABLE:
            raise ImportError(
                "rasterio is required for DEM loading. "
                "Install with: pip install rasterio"
            )
        self.max_memory_mb = max_memory_mb
        self.max_pixels = (max_memory_mb * 1024 * 1024) // 4  # Assume float32

    def load(
        self,
        file_path: Union[str, Path],
        target_unit: ElevationUnit = ElevationUnit.METERS,
        window: Optional[Window] = None,
        use_streaming: bool = True,
    ) -> DEMData:
        """
        Load a DEM file.

        Args:
            file_path: Path to DEM file
            target_unit: Target elevation unit
            window: Optional window to read (for partial loading)
            use_streaming: Use streaming for large files

        Returns:
            DEMData object containing elevation data and metadata

        Raises:
            ValidationError: If file format is not supported
            ParseError: If file cannot be loaded
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise ValidationError(f"DEM file not found: {file_path}")

        # Determine format
        suffix = file_path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            raise ValidationError(
                f"Unsupported DEM format: {suffix}. "
                f"Supported: {', '.join(self.SUPPORTED_FORMATS)}"
            )

        logger.info(f"Loading DEM from {file_path}")

        # Load based on format
        if suffix in [".tif", ".tiff"]:
            return self._load_geotiff(file_path, target_unit, window, use_streaming)
        elif suffix in [".asc", ".grd"]:
            return self._load_ascii_grid(file_path, target_unit)
        else:
            raise ValidationError(f"Unsupported format: {suffix}")

    def _load_geotiff(
        self,
        file_path: Path,
        target_unit: ElevationUnit,
        window: Optional[Window],
        use_streaming: bool,
    ) -> DEMData:
        """
        Load GeoTIFF DEM file.

        Args:
            file_path: Path to GeoTIFF file
            target_unit: Target elevation unit
            window: Optional window to read
            use_streaming: Use streaming for large files

        Returns:
            DEMData object
        """
        try:
            with rasterio.open(file_path) as src:
                # Extract metadata
                metadata = self._extract_geotiff_metadata(src, target_unit)

                # Check if streaming is needed
                total_pixels = src.width * src.height
                needs_streaming = use_streaming and total_pixels > self.max_pixels

                if needs_streaming and window is None:
                    logger.warning(
                        f"Large DEM detected ({total_pixels:,} pixels). "
                        "Consider using window parameter or cropping."
                    )

                # Read elevation data
                if window:
                    elevation = src.read(1, window=window)
                    # Update metadata for windowed read
                    metadata = self._update_metadata_for_window(
                        metadata, src, window
                    )
                else:
                    elevation = src.read(1)

                # Handle no-data values
                if src.nodata is not None:
                    # Convert no-data to NaN for easier processing
                    elevation = elevation.astype(np.float32)
                    elevation[elevation == src.nodata] = np.nan
                    metadata.no_data_value = np.nan
                else:
                    elevation = elevation.astype(np.float32)

                # Unit conversion if needed
                if target_unit != metadata.elevation_unit:
                    elevation = self._convert_units(
                        elevation, metadata.elevation_unit, target_unit
                    )
                    metadata.elevation_unit = target_unit

                logger.info(
                    f"Loaded GeoTIFF: {metadata.width}x{metadata.height}, "
                    f"resolution: {metadata.resolution}"
                )

                return DEMData(elevation=elevation, metadata=metadata)

        except rasterio.errors.RasterioIOError as e:
            raise ParseError(f"Failed to read GeoTIFF: {str(e)}") from e
        except Exception as e:
            raise ParseError(f"Error loading GeoTIFF: {str(e)}") from e

    def _extract_geotiff_metadata(
        self, src: "rasterio.DatasetReader", target_unit: ElevationUnit
    ) -> DEMMetadata:
        """
        Extract metadata from GeoTIFF file.

        Args:
            src: Rasterio dataset reader
            target_unit: Target elevation unit

        Returns:
            DEMMetadata object
        """
        # Get CRS
        crs = CRS.from_wkt(src.crs.to_wkt()) if src.crs else None

        # Get resolution from transform
        transform = src.transform
        x_res = abs(transform.a)
        y_res = abs(transform.e)

        # Get bounds
        bounds = src.bounds

        # Detect elevation unit from metadata or filename
        elevation_unit = self._detect_elevation_unit(src, target_unit)

        # Get transform parameters
        transform_tuple = (
            transform.a,
            transform.b,
            transform.c,
            transform.d,
            transform.e,
            transform.f,
        )

        return DEMMetadata(
            width=src.width,
            height=src.height,
            resolution=(x_res, y_res),
            bounds=(bounds.left, bounds.bottom, bounds.right, bounds.top),
            crs=crs,
            no_data_value=src.nodata,
            elevation_unit=elevation_unit,
            dtype=str(src.dtypes[0]),
            transform=transform_tuple,
        )

    def _update_metadata_for_window(
        self, metadata: DEMMetadata, src: "rasterio.DatasetReader", window: Window
    ) -> DEMMetadata:
        """
        Update metadata for windowed read.

        Args:
            metadata: Original metadata
            src: Rasterio dataset reader
            window: Window that was read

        Returns:
            Updated DEMMetadata
        """
        # Calculate new bounds from window
        window_transform = rasterio.windows.transform(window, src.transform)
        new_width = window.width or (src.width - window.col_off)
        new_height = window.height or (src.height - window.row_off)

        # Calculate new bounds
        min_x = window_transform.c
        max_y = window_transform.f
        max_x = min_x + new_width * metadata.resolution[0]
        min_y = max_y - new_height * metadata.resolution[1]

        return DEMMetadata(
            width=new_width,
            height=new_height,
            resolution=metadata.resolution,
            bounds=(min_x, min_y, max_x, max_y),
            crs=metadata.crs,
            no_data_value=metadata.no_data_value,
            elevation_unit=metadata.elevation_unit,
            dtype=metadata.dtype,
            transform=metadata.transform,
        )

    def _load_ascii_grid(
        self, file_path: Path, target_unit: ElevationUnit
    ) -> DEMData:
        """
        Load ASCII grid DEM file.

        ASCII Grid format:
            ncols         4
            nrows         6
            xllcorner     0.0
            yllcorner     0.0
            cellsize      50.0
            NODATA_value  -9999
            <data values>

        Args:
            file_path: Path to ASCII grid file
            target_unit: Target elevation unit

        Returns:
            DEMData object
        """
        try:
            with open(file_path, "r") as f:
                # Read header
                header = {}
                for _ in range(6):
                    line = f.readline().strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].lower()
                        value = parts[1]
                        header[key] = value

                # Validate required fields
                required = ["ncols", "nrows", "cellsize"]
                for field in required:
                    if field not in header:
                        raise ValidationError(
                            f"Missing required field in ASCII grid: {field}"
                        )

                # Parse header
                ncols = int(header["ncols"])
                nrows = int(header["nrows"])
                cellsize = float(header["cellsize"])
                nodata_value = float(header.get("nodata_value", -9999))

                # Get corner coordinates
                if "xllcorner" in header:
                    xll = float(header["xllcorner"])
                    yll = float(header["yllcorner"])
                elif "xllcenter" in header:
                    xll = float(header["xllcenter"]) - cellsize / 2
                    yll = float(header["yllcenter"]) - cellsize / 2
                else:
                    xll = 0.0
                    yll = 0.0

                # Calculate bounds
                bounds = (
                    xll,
                    yll,
                    xll + ncols * cellsize,
                    yll + nrows * cellsize,
                )

                # Read elevation data
                elevation = np.loadtxt(f)

                # Validate shape
                if elevation.shape != (nrows, ncols):
                    raise ValidationError(
                        f"Data shape {elevation.shape} does not match "
                        f"header dimensions ({nrows}, {ncols})"
                    )

                # Handle no-data values
                elevation = elevation.astype(np.float32)
                elevation[elevation == nodata_value] = np.nan

                # Create metadata
                metadata = DEMMetadata(
                    width=ncols,
                    height=nrows,
                    resolution=(cellsize, cellsize),
                    bounds=bounds,
                    crs=None,  # ASCII grids don't include CRS
                    no_data_value=np.nan,
                    elevation_unit=target_unit,
                    dtype="float32",
                )

                logger.info(
                    f"Loaded ASCII grid: {ncols}x{nrows}, cellsize: {cellsize}"
                )

                return DEMData(elevation=elevation, metadata=metadata)

        except Exception as e:
            raise ParseError(f"Error loading ASCII grid: {str(e)}") from e

    def _detect_elevation_unit(
        self, src: "rasterio.DatasetReader", default: ElevationUnit
    ) -> ElevationUnit:
        """
        Detect elevation unit from metadata or filename.

        Args:
            src: Rasterio dataset reader
            default: Default unit if detection fails

        Returns:
            Detected elevation unit
        """
        # Check metadata tags
        if hasattr(src, "tags"):
            tags = src.tags()
            unit_str = tags.get("units", "").lower()
            if "feet" in unit_str or "ft" in unit_str:
                return ElevationUnit.FEET
            elif "meter" in unit_str or "m" in unit_str:
                return ElevationUnit.METERS

        # Check filename
        filename = Path(src.name).stem.lower()
        if "feet" in filename or "_ft" in filename:
            return ElevationUnit.FEET
        elif "meter" in filename or "_m" in filename:
            return ElevationUnit.METERS

        return default

    def _convert_units(
        self,
        elevation: np.ndarray,
        from_unit: ElevationUnit,
        to_unit: ElevationUnit,
    ) -> np.ndarray:
        """
        Convert elevation units.

        Args:
            elevation: Elevation array
            from_unit: Current unit
            to_unit: Target unit

        Returns:
            Converted elevation array
        """
        if from_unit == to_unit:
            return elevation

        if from_unit == ElevationUnit.FEET and to_unit == ElevationUnit.METERS:
            return elevation * 0.3048
        elif from_unit == ElevationUnit.METERS and to_unit == ElevationUnit.FEET:
            return elevation / 0.3048
        else:
            raise ValueError(f"Unsupported unit conversion: {from_unit} to {to_unit}")

    def load_window(
        self,
        file_path: Union[str, Path],
        col_off: int,
        row_off: int,
        width: int,
        height: int,
        target_unit: ElevationUnit = ElevationUnit.METERS,
    ) -> DEMData:
        """
        Load a specific window from a DEM file.

        Useful for processing large DEMs in chunks.

        Args:
            file_path: Path to DEM file
            col_off: Column offset
            row_off: Row offset
            width: Window width in pixels
            height: Window height in pixels
            target_unit: Target elevation unit

        Returns:
            DEMData for the specified window
        """
        window = Window(col_off, row_off, width, height)
        return self.load(file_path, target_unit, window=window, use_streaming=False)

    def get_metadata(
        self, file_path: Union[str, Path]
    ) -> DEMMetadata:
        """
        Get DEM metadata without loading the full dataset.

        Args:
            file_path: Path to DEM file

        Returns:
            DEMMetadata object
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise ValidationError(f"DEM file not found: {file_path}")

        suffix = file_path.suffix.lower()

        if suffix in [".tif", ".tiff"]:
            with rasterio.open(file_path) as src:
                return self._extract_geotiff_metadata(src, ElevationUnit.METERS)
        elif suffix in [".asc", ".grd"]:
            # For ASCII grid, need to read header
            dem_data = self._load_ascii_grid(file_path, ElevationUnit.METERS)
            return dem_data.metadata
        else:
            raise ValidationError(f"Unsupported format: {suffix}")
