# Terrain Analysis - Slope & Aspect Calculation

This document describes the slope and aspect calculation functionality implemented for Entmoot Story 2.2.

## Overview

The terrain analysis module provides comprehensive algorithms for calculating slope and aspect from Digital Elevation Models (DEMs). These calculations are critical for:

- **Buildability assessment** - Determining suitable areas for construction
- **Drainage analysis** - Understanding water flow patterns
- **Solar exposure** - Optimizing building orientation and solar panel placement
- **Wind exposure** - Wind turbine siting and wind load analysis
- **Environmental studies** - Ecological and hydrological modeling

## Features Implemented

### 1. Slope Calculation (`src/entmoot/core/terrain/slope.py`)

#### Multiple Algorithms
- **Horn's method** (default) - Industry standard used in ArcGIS and QGIS
- **Fleming and Hoffer method** - Simple finite differences
- **Zevenbergen and Thorne method** - Polynomial surface fitting

#### Output Formats
- Degrees (0-90°)
- Percentage (0-100%+)

#### Key Features
- Vectorized numpy operations (no loops) for performance
- Proper edge pixel handling with padding
- Z-factor support for vertical exaggeration
- Configurable cell size (resolution)

#### Classification System
Slopes are classified into buildability categories:
- **Flat (0-5%)** - Easily buildable
- **Moderate (5-15%)** - Buildable with grading
- **Steep (15-25%)** - Difficult, requires engineering
- **Very Steep (25%+)** - Generally unbuildable

### 2. Aspect Calculation (`src/entmoot/core/terrain/aspect.py`)

#### Core Functionality
- Calculates compass direction of maximum slope (0-360°, North=0°)
- Handles flat areas (undefined aspect = -1)
- Configurable slope threshold for flat area detection

#### Cardinal Direction Mapping
Converts aspect to 8 cardinal/intercardinal directions:
- N, NE, E, SE, S, SW, W, NW, FLAT

#### Analysis Tools
- **Aspect distribution** - Statistical breakdown by direction
- **Solar exposure index** - Based on latitude, aspect, and slope
- **Wind exposure metrics** - Based on prevailing wind direction

### 3. Solar Exposure Analysis

Calculates solar exposure index (0-1) considering:
- Hemisphere (northern vs southern)
- Aspect (direction slope faces)
- Slope angle
- Latitude

**Northern Hemisphere:** South-facing slopes receive maximum sun
**Southern Hemisphere:** North-facing slopes receive maximum sun

### 4. Wind Exposure Analysis

Calculates wind exposure index (0-1) considering:
- Prevailing wind direction
- Aspect (exposure to wind)
- Slope steepness (amplification factor)

## API Reference

### Basic Usage

```python
import numpy as np
from entmoot.core.terrain.slope import calculate_slope, classify_slope
from entmoot.core.terrain.aspect import calculate_aspect, calculate_solar_exposure

# Load your DEM (example with synthetic data)
dem = np.random.rand(100, 100) * 50 + 1000  # 100x100 DEM

# Calculate slope
slope_degrees = calculate_slope(dem, cell_size=1.0, units='degrees')
slope_percent = calculate_slope(dem, cell_size=1.0, units='percent')

# Classify slope for buildability
classified = classify_slope(slope_percent)

# Calculate aspect
aspect = calculate_aspect(dem, cell_size=1.0, slope_threshold=1.0)

# Calculate solar exposure (40°N latitude)
solar = calculate_solar_exposure(aspect, slope_degrees, latitude=40.0)
```

### Advanced Usage

```python
from entmoot.core.terrain.slope import SlopeCalculator, SlopeMethod
from entmoot.core.terrain.aspect import AspectCalculator, aspect_to_cardinal

# Use specific algorithm
calculator = SlopeCalculator(
    cell_size=1.0,
    method=SlopeMethod.HORN,
    units='degrees'
)
slope = calculator.calculate(dem, z_factor=1.0)

# Get slope with metadata
result = calculator.calculate_with_metadata(dem)
print(f"Mean slope: {result['mean']}°")
print(f"Max slope: {result['max']}°")

# Calculate aspect with cardinal directions
aspect_calc = AspectCalculator(cell_size=1.0)
aspect, cardinal_codes = aspect_calc.calculate_with_cardinal(dem)

# Convert aspect value to cardinal direction
direction = aspect_to_cardinal(180.0)  # Returns CardinalDirection.S
```

## Performance

### Benchmarks
- **100-acre site** (636x636 pixels at 1m resolution): <10 seconds
- **1000x1000 array**: <5 seconds

All tests pass performance requirements with vectorized numpy operations.

### Optimization Techniques
- Numpy array slicing for kernel operations (no loops)
- Efficient gradient calculation
- Edge padding strategy
- Memory-efficient operations

## Testing

### Test Coverage
- **Slope module**: 98.95% coverage (94/95 statements)
- **Aspect module**: 100% coverage (126/126 statements)
- **Total**: 87 tests, all passing

### Test Categories
1. **Algorithm correctness** - Validated with synthetic DEMs of known slopes
2. **Edge cases** - Flat terrain, steep slopes, boundary pixels
3. **Performance** - Benchmarks for large arrays
4. **Real-world scenarios** - Hills, valleys, ridges, plateaus
5. **Data types** - float32, float64, integer inputs
6. **Integration** - Combined slope/aspect/exposure workflows

### Running Tests
```bash
# Run all terrain tests
pytest tests/test_terrain/test_slope.py tests/test_terrain/test_aspect.py -v

# Run with coverage
pytest tests/test_terrain/ --cov=src/entmoot/core/terrain --cov-report=term-missing

# Run performance tests
pytest tests/test_terrain/ -v -m slow
```

## Examples

See `examples/terrain_analysis_demo.py` for comprehensive demonstrations of:
1. Basic slope calculation
2. Slope classification
3. Aspect calculation
4. Method comparison
5. Solar exposure analysis
6. Wind exposure analysis
7. Complete terrain analysis workflow

Run the demo:
```bash
python examples/terrain_analysis_demo.py
```

## Technical Details

### Coordinate System
- **Rows**: Y-axis (North-South), row 0 is North
- **Columns**: X-axis (East-West), column 0 is West
- **Aspect**: 0° = North, 90° = East, 180° = South, 270° = West (clockwise)

### Horn's Method Formula
The standard 3x3 kernel approach:

```
Gradient calculation:
dz/dx = ((c + 2f + i) - (a + 2d + g)) / (8 * cell_size)
dz/dy = ((g + 2h + i) - (a + 2b + c)) / (8 * cell_size)

Where pixels are:
[a b c]
[d e f]
[g h i]

Slope = arctan(sqrt(dz/dx² + dz/dy²))
Aspect = 90° - arctan2(dz/dy, -dz/dx)
```

### Edge Pixel Handling
Uses `np.pad()` with `mode='edge'` to replicate edge values, providing reasonable estimates for boundary pixels while maintaining array dimensions.

## Validation

### Accuracy
- Tested against known slopes (0°, 45°, 63.4°, etc.)
- Edge pixels may have slightly less accuracy due to padding
- Center pixels have highest accuracy

### Comparison to GIS Software
The implementation uses the same algorithms as:
- **ArcGIS**: Horn's method for slope/aspect
- **QGIS**: Horn's method (default)
- Produces comparable results when validated

## Dependencies

- `numpy>=1.24.0` - Array operations
- `scipy>=1.10.0` - Scientific computing (future use)

All dependencies are already in `pyproject.toml`.

## Future Enhancements

Potential additions for future stories:
1. Curvature calculation (profile, plan, tangential)
2. Viewshed analysis
3. Hillshade generation for visualization
4. Topographic Position Index (TPI)
5. Terrain Ruggedness Index (TRI)
6. Parallel processing for very large DEMs
7. GeoTIFF export with proper georeferencing

## References

- Burrough, P. A., and McDonell, R. A., 1998. *Principles of Geographical Information Systems*
- Horn, B. K. P., 1981. "Hill shading and the reflectance map", *Proceedings of the IEEE*
- Zevenbergen, L. W., and Thorne, C. R., 1987. "Quantitative analysis of land surface topography"
- ESRI ArcGIS Documentation: Slope and Aspect algorithms

## Authors

Implementation by DEV-2 for Entmoot Story 2.2

## License

MIT License - See LICENSE file for details
