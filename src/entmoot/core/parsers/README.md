# KML/KMZ Parser Module

## Overview

This module provides comprehensive parsing and validation for KML and KMZ files, the primary input format for property boundaries and geographic data in the Entmoot property management system.

## Quick Start

```python
from entmoot.core.parsers import parse_kml_file, parse_kmz_file

# Parse a KML file
kml_result = parse_kml_file("property.kml")
print(f"Found {kml_result.placemark_count} placemarks")

# Parse a KMZ file (automatically extracts and parses)
kmz_result = parse_kmz_file("property.kmz")
for placemark in kmz_result.placemarks:
    print(f"{placemark.name}: {placemark.geometry_type}")
```

## Modules

### `geometry.py`
Geometry conversion utilities for KML coordinates to Shapely objects.

**Key Functions:**
- `parse_kml_coordinates(coord_string)` - Parse KML coordinate strings
- `kml_to_shapely(geometry_type, ...)` - Convert KML to Shapely geometry
- `extract_elevation_from_text(text)` - Extract elevation from contour labels
- `is_contour_line(name, description)` - Identify topographic contour lines

**Classes:**
- `GeometryType` - Enum of supported geometry types
- `ParsedGeometry` - Container for geometry with metadata

### `kml_validator.py`
KML XML validation before parsing.

**Classes:**
- `KMLValidator` - Validates KML structure and content
- `KMLValidationResult` - Validation results with errors/warnings

**Functions:**
- `validate_kml_file(file_path)` - Validate KML file
- `validate_kml_string(kml_content)` - Validate KML string

### `kml_parser.py`
Main KML parsing implementation.

**Classes:**
- `KMLParser` - Parses KML files and extracts data
- `ParsedKML` - Parsed KML data with placemarks
- `Placemark` - Individual KML placemark with geometry

**Functions:**
- `parse_kml_file(file_path)` - Parse KML file
- `parse_kml_string(kml_content)` - Parse KML string

### `kmz_validator.py`
KMZ (zipped KML) validation.

**Classes:**
- `KMZValidator` - Validates KMZ ZIP structure
- `KMZValidationResult` - Validation results

**Functions:**
- `validate_kmz_file(file_path)` - Validate KMZ file

### `kmz_parser.py`
KMZ extraction and parsing.

**Classes:**
- `KMZParser` - Extracts and parses KMZ files

**Functions:**
- `parse_kmz_file(file_path)` - Parse KMZ file

## Common Use Cases

### 1. Parse Property Boundaries

```python
from entmoot.core.parsers import parse_kml_file

result = parse_kml_file("property.kml")
boundaries = result.get_property_boundaries()

for boundary in boundaries:
    print(f"Parcel: {boundary.name}")
    print(f"Area: {boundary.geometry.area} sq units")
    print(f"Properties: {boundary.properties}")
```

### 2. Extract Topographic Contours

```python
from entmoot.core.parsers import parse_kml_file

result = parse_kml_file("topo.kml")
contours = result.get_contours()

for contour in contours:
    print(f"Elevation: {contour.elevation}ft")
    print(f"Length: {contour.geometry.length} units")
```

### 3. Validate Before Parsing

```python
from entmoot.core.parsers import validate_kml_file, parse_kml_file

validation = validate_kml_file("property.kml")
if not validation.is_valid:
    print(f"Errors: {validation.errors}")
    return

result = parse_kml_file("property.kml")
# Safe to use result
```

### 4. Handle KMZ Archives

```python
from entmoot.core.parsers import KMZParser

parser = KMZParser()

# List contents without extracting
contents = parser.list_contents("property.kmz")
print(f"KML files: {contents['kml_files']}")
print(f"Images: {contents['image_files']}")

# Extract all files
output_dir = parser.extract_all("property.kmz", "extracted/")
print(f"Extracted to: {output_dir}")

# Or just parse directly
result = parser.parse("property.kmz")
```

### 5. Filter by Geometry Type

```python
from entmoot.core.parsers import parse_kml_file, GeometryType

result = parse_kml_file("complex.kml")

# Get all polygons
polygons = result.get_placemarks_by_type(GeometryType.POLYGON)

# Get all line strings
lines = result.get_placemarks_by_type(GeometryType.LINE_STRING)

# Get all points
points = result.get_placemarks_by_type(GeometryType.POINT)
```

### 6. Access Metadata

```python
from entmoot.core.parsers import parse_kml_file

result = parse_kml_file("property.kml")

print(f"Document: {result.document_name}")
print(f"Description: {result.document_description}")
print(f"Folders: {result.folders}")
print(f"Styles: {result.styles}")

for placemark in result.placemarks:
    print(f"\nPlacemark: {placemark.name}")
    print(f"  Description: {placemark.description}")
    print(f"  Properties: {placemark.properties}")
    print(f"  Folder path: {'/'.join(placemark.folder_path)}")
    print(f"  Style: {placemark.style_url}")
```

## Data Structures

### ParsedKML

Main result object from KML parsing:

```python
result = parse_kml_file("property.kml")

# Properties
result.placemarks          # List[Placemark]
result.document_name       # Optional[str]
result.document_description # Optional[str]
result.folders             # List[str]
result.styles              # Dict[str, Dict]
result.properties          # Dict[str, Any]
result.namespace           # Optional[str]
result.parse_errors        # List[str]

# Computed properties
result.placemark_count     # int
result.geometry_count      # int
result.contour_count       # int

# Methods
result.get_placemarks_by_type(GeometryType.POLYGON)
result.get_contours()
result.get_property_boundaries()
```

### Placemark

Individual placemark with geometry:

```python
placemark = result.placemarks[0]

# Properties
placemark.id               # Optional[str]
placemark.name             # Optional[str]
placemark.description      # Optional[str]
placemark.geometry         # BaseGeometry (Shapely)
placemark.geometry_type    # GeometryType
placemark.properties       # Dict[str, Any]
placemark.style_url        # Optional[str]
placemark.folder_path      # List[str]
placemark.is_contour       # bool
placemark.elevation        # Optional[float]

# Methods
placemark.to_dict()        # Convert to dictionary
```

### Validation Results

```python
from entmoot.core.parsers import validate_kml_file

validation = validate_kml_file("property.kml")

# Properties
validation.is_valid        # bool
validation.errors          # List[str]
validation.warnings        # List[str]
validation.has_placemarks  # bool
validation.has_geometries  # bool
validation.geometry_count  # int
validation.namespace       # Optional[str]
```

## Supported Geometries

- **Point** - Single coordinate (well, marker, etc.)
- **LineString** - Connected line segments (roads, contours, etc.)
- **Polygon** - Closed shape with optional holes (property boundaries, lakes, etc.)
- **LinearRing** - Closed line (polygon boundary)
- **MultiGeometry** - Multiple geometries (currently parses first child)

## Error Handling

All parsing functions handle errors gracefully:

```python
from entmoot.core.parsers import parse_kml_file

try:
    result = parse_kml_file("property.kml")
    if result.parse_errors:
        print(f"Warnings: {result.parse_errors}")
except ValueError as e:
    print(f"Invalid KML: {e}")
except FileNotFoundError as e:
    print(f"File not found: {e}")
```

## Performance

- Simple files (1-10 placemarks): < 10ms
- Medium files (10-100 placemarks): < 50ms
- Large files (100+ placemarks): < 200ms
- KMZ files: Add 20-100ms for extraction

Memory usage is proportional to file size, typically < 50MB for large files.

## Limitations

1. **MultiGeometry**: Currently parses first child geometry only
2. **3D Coordinates**: Altitude parsed but not used (only X,Y)
3. **Network Links**: Not supported
4. **Ground Overlays**: Detected but not georeferenced

These don't affect property boundary and topographic use cases.

## Testing

Comprehensive test suite with 62 tests covering all functionality:

```bash
# Run all parser tests
pytest tests/test_kml_parser.py tests/test_kmz_parser.py -v

# Run specific test class
pytest tests/test_kml_parser.py::TestKMLParser -v

# Quick validation
pytest tests/test_kml_parser.py tests/test_kmz_parser.py -q
```

## Dependencies

- `shapely>=2.0.0` - Geometry objects
- `xml.etree.ElementTree` - XML parsing (built-in)
- `zipfile` - ZIP handling (built-in)
- `pathlib` - Path handling (built-in)

## Development

### Adding New Geometry Types

1. Add to `GeometryType` enum in `geometry.py`
2. Implement parsing in `kml_to_shapely()` in `geometry.py`
3. Add validation in `KMLValidator._validate_geometry_element()`
4. Update parser in `KMLParser._parse_geometry_element()`
5. Add tests

### Adding New Validation Rules

1. Add check method to `KMLValidator`
2. Call from `validate()` method
3. Add error/warning to `KMLValidationResult`
4. Add tests

## Support

For issues or questions:
1. Check test files for usage examples
2. Review docstrings in source code
3. See `STORY_1.3_COMPLETION_REPORT.md` for detailed documentation

## License

Part of the Entmoot Property Management System.
