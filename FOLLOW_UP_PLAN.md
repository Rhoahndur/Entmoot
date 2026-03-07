# Follow-Up Plan: Wire In Unplugged Modules

Audit of implemented-but-never-wired code discovered during the `fix/ga-check-for-buildable-area` branch work. Each item has passing tests and is ready to integrate — no new algorithms needed, just plumbing.

---

## Priority 1 — Export Endpoint (3 modules → 1 API route)

The export API endpoint (`GET /projects/{id}/alternatives/{alt_id}/export/{format}`) is fully defined with OpenAPI docs in `api/projects.py:446-485` but returns hardcoded `501 Not Implemented`. Three modules exist to implement it:

### 1A. Geospatial Export (KMZ / GeoJSON / DXF)

- **Module**: `core/export/geospatial.py`
- **Classes**: `GeospatialExporter`, `KMZExporter`, `GeoJSONExporter`, `DXFExporter`
- **Tests**: 32 passing (`test_geospatial.py`)
- **Wire-in point**: `api/projects.py` export endpoint — match format param to exporter class
- **Input needed**: `LayoutAlternative` data (assets, roads, constraint zones, boundary)

### 1B. PDF Report Generator

- **Module**: `core/reports/pdf_generator.py`
- **Classes**: `PDFReportGenerator`, `ReportData`
- **Tests**: 26 passing (`test_pdf_generator.py`)
- **Wire-in point**: Same export endpoint, `format="pdf"` branch
- **Input needed**: `OptimizationResults`, project metadata, metrics

### 1C. 2D/3D Visualization

- **Module**: `core/visualization/map_2d.py`, `core/visualization/map_3d.py`
- **Classes**: `Map2DRenderer` (PNG/SVG), `Map3DRenderer` (interactive HTML via plotly)
- **Tests**: 79 passing (`test_map_2d.py`, `test_map_3d.py`)
- **Wire-in point**: Export endpoint for `format="png"/"svg"/"html"`, and/or embedded in PDF reports
- **Input needed**: Terrain data, assets, roads, boundary, constraint zones

### Implementation sketch

```python
# api/projects.py — replace the 501 block
if format == "pdf":
    generator = PDFReportGenerator()
    content = generator.generate(ReportData.from_results(results))
    return StreamingResponse(content, media_type="application/pdf")
elif format in ("kmz", "geojson", "dxf"):
    exporter = GeospatialExporter.for_format(format)
    content = exporter.export(alternative)
    return StreamingResponse(content, ...)
elif format in ("png", "svg"):
    renderer = Map2DRenderer(...)
    content = renderer.render(format)
    return StreamingResponse(content, ...)
```

---

## Priority 2 — Replace Inline Earthwork with Proper Module

### 2. Earthwork Analysis (Pre/Post Grading + Volume Calculator)

- **Module**: `core/earthwork/pre_grading.py`, `core/earthwork/post_grading.py`, `core/earthwork/volume_calculator.py`
- **Models**: `models/earthwork.py` (`SoilType`, `GradingZone`, `GradingZoneType`)
- **Tests**: 50 passing (`test_pre_grading.py`, `test_post_grading.py`, `test_volume_calculator.py`)
- **Current state**: `optimization_service.py` Step 9 uses inline `area * 0.5` / `area * 0.3` approximation for cut/fill
- **Wire-in point**: Replace Step 9 body with `VolumeCalculator` + `PreGradingModel` / `PostGradingModel`
- **Benefit**: Proper cross-section-based volumes, soil-type-aware cost estimation, grading zone classification

### Implementation sketch

```python
# optimization_service.py Step 9 — replace inline calculation
from entmoot.core.earthwork import PreGradingModel, PostGradingModel, VolumeCalculator

pre_model = PreGradingModel(terrain_data)
post_model = PostGradingModel(pre_model, placed_assets)
volume_calc = VolumeCalculator(pre_model, post_model)
earthwork_result = volume_calc.calculate()
# earthwork_result has .total_cut, .total_fill, .cost_estimate, .cross_sections
```

---

## Priority 3 — External Data Integrations

### 3A. FEMA Floodplain Data → Exclusion Zones

- **Module**: `integrations/fema/client.py`, `integrations/fema/parser.py`, `integrations/fema/cache.py`
- **Models**: `models/regulatory.py` (`FloodZone`, `FloodZoneType`, `FloodplainData`)
- **Tests**: 53 passing (`test_fema.py`)
- **Wire-in point**: `optimization_service.py` Step 2d, alongside OSM conditions fetch
- **Benefit**: Automatically identifies FEMA flood hazard zones and adds them as exclusion/constraint zones
- **Config**: Could gate behind a new `constraints.use_fema_data` flag (similar to `use_existing_conditions`)

### 3B. USGS Elevation Data → Auto-DEM

- **Module**: `integrations/usgs/client.py`, `integrations/usgs/parser.py`, `integrations/usgs/cache.py`
- **Models**: `models/elevation.py` (`ElevationPoint`, `DEMTileMetadata`)
- **Tests**: 60 passing (`test_usgs.py`)
- **Wire-in point**: `optimization_service.py` Step 2c, when `config.dem_upload_id` is None
- **Benefit**: Terrain-aware optimization (slope zones, earthwork, road grading) even without user-uploaded DEM
- **Fallback**: If USGS fetch fails, continue with flat terrain (current behavior)

### Implementation sketch

```python
# Step 2c — after the existing DEM upload block
if terrain_data is None and raw_boundary is not None:
    try:
        from entmoot.integrations.usgs import USGSClient
        usgs = USGSClient()
        dem_tiles = await usgs.fetch_dem_for_bounds(raw_boundary.bounds)
        terrain_data = prepare_terrain_data_from_tiles(dem_tiles, site_boundary, target_crs_epsg)
    except Exception as e:
        logger.warning(f"USGS auto-DEM failed, continuing flat: {e}")

# Step 2d — after OSM block
if config.constraints.use_fema_data and raw_boundary is not None:
    try:
        from entmoot.integrations.fema import FEMAClient
        fema = FEMAClient()
        flood_zones = await fema.get_flood_zones(raw_boundary)
        for zone in flood_zones:
            constraints.exclusion_zones.append(zone.geometry)
            existing_conditions_display.append(zone.to_constraint_zone())
    except Exception as e:
        logger.warning(f"FEMA floodplain fetch failed: {e}")
```

---

## Priority 4 — Optimizer Infrastructure Upgrades

### 4A. Collision Detector (R-tree Spatial Index)

- **Module**: `core/optimization/collision.py`
- **Class**: `CollisionDetector` — STRtree-based fast collision detection
- **Tests**: 37 passing (`test_collision.py`)
- **Current state**: GA has inline collision checking (O(n²) pairwise)
- **Wire-in point**: `GeneticOptimizer` population evaluation, and/or `project_service._detect_constraint_violations()`
- **Benefit**: Faster fitness evaluation for large asset counts, more precise polygon-polygon checks

### 4B. Boundary Extraction Service

- **Module**: `core/boundaries.py`
- **Class**: `BoundaryExtractionService` — multi-strategy boundary identification, geometry validation, auto-repair
- **Tests**: 32 passing (`test_boundaries.py`)
- **Current state**: Step 2 uses simple `parsed_kml.get_property_boundaries()[0]`
- **Wire-in point**: Replace Step 2 boundary extraction
- **Benefit**: Handles multi-parcel files, validates/repairs geometry, better error messages

### 4C. Constraint Management System

- **Module**: `core/constraints/collection.py`, `core/constraints/validator.py`, `core/constraints/aggregator.py`
- **Classes**: `ConstraintCollection`, `ConstraintValidator`, `ConstraintAggregator`
- **Tests**: 41 passing (`test_collection.py`)
- **Current state**: Step 4 manually constructs `OptimizationConstraints` dataclass
- **Wire-in point**: Replace Step 4 constraint setup with unified constraint management
- **Benefit**: Geometry validation, constraint aggregation modes (union/intersection/most-restrictive), statistics

---

## Priority 5 — Terrain Enhancements

### 5A. Aspect/Solar Exposure Analysis

- **Module**: `core/terrain/aspect.py`
- **Class**: `AspectCalculator` — terrain aspect, cardinal direction, solar exposure
- **Tests**: 51 passing (`test_aspect.py`)
- **Wire-in point**: `terrain_service.py` — compute alongside slope, include in `TerrainData`
- **Benefit**: Solar panel orientation, building placement preferences, environmental scoring

### 5B. Buildability Zone Classification

- **Module**: `core/terrain/buildability.py`
- **Class**: `BuildabilityAnalyzer` — classifies terrain into easy/moderate/difficult/unbuildable
- **Tests**: 46 passing (`test_buildability.py`)
- **Current state**: `constraints.buildable_zones` is always `[]`
- **Wire-in point**: Step 4b — populate `constraints.buildable_zones` from `BuildabilityAnalyzer`
- **Benefit**: Optimizer prefers easy-build zones, avoids difficult terrain even below slope limit

---

## Priority 6 — Minor Items

### 6A. CRS Normalizer

- **Module**: `core/crs/normalizer.py`
- **Tests**: 28 passing
- **Could simplify**: Step 2b CRS detection/transformation code

### 6B. Retry Decorator

- **Module**: `core/retry.py`
- **Tests**: None
- **Could wrap**: OSM, FEMA, USGS client calls (replace inline retry loops)

### 6C. Unused Config Fields (6 fields parsed but ignored)

| Field | Model | What it should do |
|-------|-------|-------------------|
| `exclusion_zones_enabled` | `ConstraintConfig` | Gate exclusion zone generation on/off |
| `respect_property_lines` | `ConstraintConfig` | Toggle boundary containment check |
| `respect_easements` | `ConstraintConfig` | Toggle easement zone violations |
| `wetland_buffer` | `ConstraintConfig` | Buffer distance for wetland/water features |
| `turning_radius` | `RoadConfig` | Pass to `PathfinderConfig` for road generation |
| `include_sidewalks` | `RoadConfig` | Add sidewalk width to road segments |

---

## Test Count Summary

| Priority | Modules | Orphaned Tests |
|----------|---------|---------------|
| P1 — Export | 3 modules | 137 |
| P2 — Earthwork | 3 modules | 50 |
| P3 — Integrations | 2 integrations | 113 |
| P4 — Optimizer infra | 3 modules | 110 |
| P5 — Terrain | 2 modules | 97 |
| P6 — Minor | 2 modules + config | 28 |
| **Total** | **15 items** | **~535 tests** |

All tests already pass. The work is purely wiring — no new algorithms needed.
