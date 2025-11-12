"""
Tests for geospatial exports.

Tests cover:
- KMZ export (Google Earth)
- GeoJSON export (QGIS/web)
- DXF export (AutoCAD)
- Data validation
- File format validation
- Georeferencing
"""

import json
import zipfile
import pytest
from pathlib import Path
from xml.etree import ElementTree as ET

from shapely.geometry import Polygon, Point, LineString

from entmoot.core.export.geospatial import (
    ExportData,
    GeospatialExporter,
    KMZExporter,
    GeoJSONExporter,
    DXFExporter,
)


@pytest.fixture
def sample_boundary() -> Polygon:
    """Create sample site boundary."""
    return Polygon([
        (-122.4, 37.8),
        (-122.3, 37.8),
        (-122.3, 37.9),
        (-122.4, 37.9),
        (-122.4, 37.8),
    ])


@pytest.fixture
def sample_export_data(sample_boundary: Polygon) -> ExportData:
    """Create sample export data."""
    data = ExportData(
        project_name="Test Export Project",
        crs_epsg=4326,  # WGS84
        site_boundary=sample_boundary,
    )

    # Add buildable zone
    buildable_zone = Polygon([
        (-122.38, 37.82),
        (-122.32, 37.82),
        (-122.32, 37.88),
        (-122.38, 37.88),
        (-122.38, 37.82),
    ])
    data.add_buildable_zone(
        buildable_zone,
        "Buildable Area 1",
        {"area_acres": 5.2, "zoning": "R1"}
    )

    # Add constraints
    wetland = Polygon([
        (-122.39, 37.81),
        (-122.37, 37.81),
        (-122.37, 37.83),
        (-122.39, 37.83),
        (-122.39, 37.81),
    ])
    data.add_constraint(
        wetland,
        "Wetland Buffer",
        "wetland",
        {"buffer_ft": 50, "protected": True}
    )

    setback = Polygon([
        (-122.395, 37.805),
        (-122.385, 37.805),
        (-122.385, 37.815),
        (-122.395, 37.815),
        (-122.395, 37.805),
    ])
    data.add_constraint(
        setback,
        "Property Line Setback",
        "property_line",
        {"setback_ft": 25}
    )

    # Add assets as points
    building = Point(-122.35, 37.85)
    data.add_asset(
        building,
        "Main Building",
        "building",
        {"area_sqft": 5000, "height_ft": 25}
    )

    parking = Point(-122.36, 37.86)
    data.add_asset(
        parking,
        "Parking Lot",
        "parking_lot",
        {"spaces": 50}
    )

    # Add assets as polygons
    equipment_yard = Polygon([
        (-122.34, 37.84),
        (-122.33, 37.84),
        (-122.33, 37.85),
        (-122.34, 37.85),
        (-122.34, 37.84),
    ])
    data.add_asset(
        equipment_yard,
        "Equipment Yard",
        "equipment_yard",
        {"area_sqft": 2000}
    )

    # Add roads
    road1 = LineString([
        (-122.395, 37.85),
        (-122.35, 37.85),
        (-122.35, 37.87),
    ])
    data.add_road(
        road1,
        "Main Access Road",
        {"length_ft": 500, "width_ft": 24, "surface": "asphalt"}
    )

    road2 = LineString([
        (-122.35, 37.85),
        (-122.32, 37.85),
    ])
    data.add_road(
        road2,
        "Secondary Road",
        {"length_ft": 300, "width_ft": 20, "surface": "gravel"}
    )

    return data


class TestExportData:
    """Test ExportData class."""

    def test_init(self, sample_boundary: Polygon) -> None:
        """Test ExportData initialization."""
        data = ExportData(
            project_name="Test Project",
            crs_epsg=4326,
            site_boundary=sample_boundary,
        )

        assert data.project_name == "Test Project"
        assert data.crs_epsg == 4326
        assert data.site_boundary == sample_boundary
        assert len(data.constraints) == 0
        assert len(data.assets) == 0
        assert len(data.roads) == 0
        assert "created_at" in data.metadata
        assert data.metadata["crs"] == "EPSG:4326"

    def test_add_constraint(self, sample_boundary: Polygon) -> None:
        """Test adding constraint."""
        data = ExportData("Test", 4326, sample_boundary)

        constraint_geom = Polygon([
            (-122.4, 37.8),
            (-122.35, 37.8),
            (-122.35, 37.85),
            (-122.4, 37.85),
            (-122.4, 37.8),
        ])

        data.add_constraint(
            constraint_geom,
            "Test Constraint",
            "wetland",
            {"protected": True}
        )

        assert len(data.constraints) == 1
        assert data.constraints[0]["name"] == "Test Constraint"
        assert data.constraints[0]["type"] == "wetland"
        assert data.constraints[0]["properties"]["protected"] is True

    def test_add_asset(self, sample_boundary: Polygon) -> None:
        """Test adding asset."""
        data = ExportData("Test", 4326, sample_boundary)

        asset_geom = Point(-122.35, 37.85)
        data.add_asset(
            asset_geom,
            "Building 1",
            "building",
            {"area": 1000}
        )

        assert len(data.assets) == 1
        assert data.assets[0]["name"] == "Building 1"
        assert data.assets[0]["type"] == "building"

    def test_add_road(self, sample_boundary: Polygon) -> None:
        """Test adding road."""
        data = ExportData("Test", 4326, sample_boundary)

        road_geom = LineString([(-122.4, 37.8), (-122.3, 37.9)])
        data.add_road(
            road_geom,
            "Main Road",
            {"length": 500}
        )

        assert len(data.roads) == 1
        assert data.roads[0]["name"] == "Main Road"

    def test_add_buildable_zone(self, sample_boundary: Polygon) -> None:
        """Test adding buildable zone."""
        data = ExportData("Test", 4326, sample_boundary)

        zone_geom = Polygon([
            (-122.39, 37.81),
            (-122.31, 37.81),
            (-122.31, 37.89),
            (-122.39, 37.89),
            (-122.39, 37.81),
        ])
        data.add_buildable_zone(
            zone_geom,
            "Zone 1",
            {"zoning": "R1"}
        )

        assert len(data.buildable_zones) == 1
        assert data.buildable_zones[0]["name"] == "Zone 1"


class TestKMZExporter:
    """Test KMZ export functionality."""

    def test_init(self) -> None:
        """Test KMZExporter initialization."""
        exporter = KMZExporter()
        assert isinstance(exporter, GeospatialExporter)

    def test_export_basic(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test basic KMZ export."""
        output_path = tmp_path / "test.kmz"
        exporter = KMZExporter()

        exporter.export(sample_export_data, output_path)

        # Verify file exists
        assert output_path.exists()
        assert output_path.stat().st_size > 0

        # Verify it's a valid zip file
        assert zipfile.is_zipfile(output_path)

    def test_export_contains_kml(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test that KMZ contains valid KML."""
        output_path = tmp_path / "test.kmz"
        exporter = KMZExporter()
        exporter.export(sample_export_data, output_path)

        # Extract and verify KML
        with zipfile.ZipFile(output_path, 'r') as kmz:
            files = kmz.namelist()
            # Should contain doc.kml
            assert any(f.endswith('.kml') for f in files)

            # Read KML content
            kml_file = [f for f in files if f.endswith('.kml')][0]
            kml_content = kmz.read(kml_file).decode('utf-8')

            # Should be valid XML
            root = ET.fromstring(kml_content)
            assert root is not None

    def test_export_with_site_boundary(
        self,
        sample_boundary: Polygon,
        tmp_path: Path,
    ) -> None:
        """Test KMZ export with just site boundary."""
        data = ExportData(
            "Boundary Test",
            4326,
            sample_boundary,
        )

        output_path = tmp_path / "boundary.kmz"
        exporter = KMZExporter()
        exporter.export(data, output_path)

        assert output_path.exists()

    def test_export_with_all_features(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test KMZ export with all feature types."""
        output_path = tmp_path / "complete.kmz"
        exporter = KMZExporter()
        exporter.export(sample_export_data, output_path)

        # Should have all features
        assert output_path.exists()
        assert output_path.stat().st_size > 1000  # Should be substantial

    def test_export_empty_data(
        self,
        sample_boundary: Polygon,
        tmp_path: Path,
    ) -> None:
        """Test KMZ export with minimal data."""
        data = ExportData("Empty Test", 4326, sample_boundary)

        output_path = tmp_path / "empty.kmz"
        exporter = KMZExporter()

        # Should not error with empty data
        exporter.export(data, output_path)
        assert output_path.exists()


class TestGeoJSONExporter:
    """Test GeoJSON export functionality."""

    def test_init(self) -> None:
        """Test GeoJSONExporter initialization."""
        exporter = GeoJSONExporter()
        assert isinstance(exporter, GeospatialExporter)

    def test_export_basic(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test basic GeoJSON export."""
        output_path = tmp_path / "test.geojson"
        exporter = GeoJSONExporter()

        exporter.export(sample_export_data, output_path)

        # Verify file exists
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_export_valid_json(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test that export creates valid JSON."""
        output_path = tmp_path / "test.geojson"
        exporter = GeoJSONExporter()
        exporter.export(sample_export_data, output_path)

        # Parse JSON
        with open(output_path, 'r') as f:
            data = json.load(f)

        # Verify structure
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert isinstance(data["features"], list)

    def test_export_has_crs(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test that export includes CRS information."""
        output_path = tmp_path / "test.geojson"
        exporter = GeoJSONExporter()
        exporter.export(sample_export_data, output_path)

        with open(output_path, 'r') as f:
            data = json.load(f)

        assert "crs" in data
        assert "EPSG::4326" in data["crs"]["properties"]["name"]

    def test_export_features_count(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test that all features are exported."""
        output_path = tmp_path / "test.geojson"
        exporter = GeoJSONExporter()
        exporter.export(sample_export_data, output_path)

        with open(output_path, 'r') as f:
            data = json.load(f)

        # Should have:
        # 1 site boundary + 1 buildable zone + 2 constraints + 3 assets + 2 roads = 9
        assert len(data["features"]) == 9

    def test_export_feature_properties(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test that feature properties are included."""
        output_path = tmp_path / "test.geojson"
        exporter = GeoJSONExporter()
        exporter.export(sample_export_data, output_path)

        with open(output_path, 'r') as f:
            data = json.load(f)

        # Check that features have properties
        for feature in data["features"]:
            assert "properties" in feature
            assert "name" in feature["properties"]
            assert "layer" in feature["properties"]

    def test_export_geometry_types(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test that different geometry types are exported correctly."""
        output_path = tmp_path / "test.geojson"
        exporter = GeoJSONExporter()
        exporter.export(sample_export_data, output_path)

        with open(output_path, 'r') as f:
            data = json.load(f)

        # Should have different geometry types
        geom_types = set()
        for feature in data["features"]:
            geom_types.add(feature["geometry"]["type"])

        assert "Polygon" in geom_types
        assert "Point" in geom_types
        assert "LineString" in geom_types

    def test_geometry_to_geojson_point(self) -> None:
        """Test Point conversion to GeoJSON."""
        exporter = GeoJSONExporter()
        point = Point(-122.5, 37.8)

        geojson = exporter._geometry_to_geojson(point)

        assert geojson["type"] == "Point"
        assert geojson["coordinates"] == [-122.5, 37.8]

    def test_geometry_to_geojson_linestring(self) -> None:
        """Test LineString conversion to GeoJSON."""
        exporter = GeoJSONExporter()
        line = LineString([(-122.5, 37.8), (-122.4, 37.9)])

        geojson = exporter._geometry_to_geojson(line)

        assert geojson["type"] == "LineString"
        assert len(geojson["coordinates"]) == 2

    def test_geometry_to_geojson_polygon(self) -> None:
        """Test Polygon conversion to GeoJSON."""
        exporter = GeoJSONExporter()
        polygon = Polygon([
            (-122.5, 37.8),
            (-122.4, 37.8),
            (-122.4, 37.9),
            (-122.5, 37.9),
            (-122.5, 37.8),
        ])

        geojson = exporter._geometry_to_geojson(polygon)

        assert geojson["type"] == "Polygon"
        assert len(geojson["coordinates"]) >= 1
        assert len(geojson["coordinates"][0]) == 5  # Closed ring


class TestDXFExporter:
    """Test DXF export functionality."""

    def test_init(self) -> None:
        """Test DXFExporter initialization."""
        exporter = DXFExporter()
        assert isinstance(exporter, GeospatialExporter)

    def test_export_basic(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test basic DXF export."""
        output_path = tmp_path / "test.dxf"
        exporter = DXFExporter()

        exporter.export(sample_export_data, output_path)

        # Verify file exists
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_export_valid_dxf(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test that export creates valid DXF."""
        import ezdxf

        output_path = tmp_path / "test.dxf"
        exporter = DXFExporter()
        exporter.export(sample_export_data, output_path)

        # Try to read with ezdxf
        doc = ezdxf.readfile(str(output_path))
        assert doc is not None

    def test_export_has_layers(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test that DXF has proper layers."""
        import ezdxf

        output_path = tmp_path / "test.dxf"
        exporter = DXFExporter()
        exporter.export(sample_export_data, output_path)

        doc = ezdxf.readfile(str(output_path))

        # Check for expected layers
        layer_names = [layer.dxf.name for layer in doc.layers]
        assert "BOUNDARY" in layer_names
        assert "CONSTRAINTS" in layer_names
        assert "ASSETS" in layer_names
        assert "ROADS" in layer_names

    def test_export_entities(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test that DXF contains entities."""
        import ezdxf

        output_path = tmp_path / "test.dxf"
        exporter = DXFExporter()
        exporter.export(sample_export_data, output_path)

        doc = ezdxf.readfile(str(output_path))
        msp = doc.modelspace()

        # Should have entities
        entities = list(msp)
        assert len(entities) > 0

    def test_export_with_site_boundary(
        self,
        sample_boundary: Polygon,
        tmp_path: Path,
    ) -> None:
        """Test DXF export with just site boundary."""
        import ezdxf

        data = ExportData("Boundary Test", 4326, sample_boundary)

        output_path = tmp_path / "boundary.dxf"
        exporter = DXFExporter()
        exporter.export(data, output_path)

        # Verify
        doc = ezdxf.readfile(str(output_path))
        assert doc is not None

    def test_layer_colors(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test that layers have correct colors."""
        import ezdxf

        output_path = tmp_path / "test.dxf"
        exporter = DXFExporter()
        exporter.export(sample_export_data, output_path)

        doc = ezdxf.readfile(str(output_path))

        # Check layer colors
        for layer_name, layer_props in exporter.LAYERS.items():
            if layer_name in [layer.dxf.name for layer in doc.layers]:
                layer = doc.layers.get(layer_name)
                assert layer.dxf.color == layer_props['color']


class TestGeospatialExportIntegration:
    """Integration tests for geospatial exports."""

    def test_export_all_formats(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test exporting to all formats."""
        # KMZ
        kmz_path = tmp_path / "export.kmz"
        kmz_exporter = KMZExporter()
        kmz_exporter.export(sample_export_data, kmz_path)
        assert kmz_path.exists()

        # GeoJSON
        geojson_path = tmp_path / "export.geojson"
        geojson_exporter = GeoJSONExporter()
        geojson_exporter.export(sample_export_data, geojson_path)
        assert geojson_path.exists()

        # DXF
        dxf_path = tmp_path / "export.dxf"
        dxf_exporter = DXFExporter()
        dxf_exporter.export(sample_export_data, dxf_path)
        assert dxf_path.exists()

    def test_roundtrip_geojson(
        self,
        sample_export_data: ExportData,
        tmp_path: Path,
    ) -> None:
        """Test that GeoJSON can be read back."""
        output_path = tmp_path / "test.geojson"
        exporter = GeoJSONExporter()
        exporter.export(sample_export_data, output_path)

        # Read back
        with open(output_path, 'r') as f:
            data = json.load(f)

        # Verify critical data is preserved
        assert data["name"] == sample_export_data.project_name
        assert len(data["features"]) > 0

        # Check that geometries are valid
        for feature in data["features"]:
            assert "geometry" in feature
            assert "type" in feature["geometry"]
            assert "coordinates" in feature["geometry"]

    def test_large_dataset_export(
        self,
        sample_boundary: Polygon,
        tmp_path: Path,
    ) -> None:
        """Test exporting large dataset."""
        data = ExportData("Large Dataset", 4326, sample_boundary)

        # Add many constraints
        for i in range(50):
            constraint = Polygon([
                (-122.4 + i*0.01, 37.8 + i*0.01),
                (-122.39 + i*0.01, 37.8 + i*0.01),
                (-122.39 + i*0.01, 37.81 + i*0.01),
                (-122.4 + i*0.01, 37.81 + i*0.01),
                (-122.4 + i*0.01, 37.8 + i*0.01),
            ])
            data.add_constraint(constraint, f"Constraint {i}", "setback")

        # Add many assets
        for i in range(30):
            asset = Point(-122.35 + i*0.01, 37.85 + i*0.01)
            data.add_asset(asset, f"Asset {i}", "building")

        # Export to all formats
        for fmt, exporter_class in [
            ("kmz", KMZExporter),
            ("geojson", GeoJSONExporter),
            ("dxf", DXFExporter),
        ]:
            output_path = tmp_path / f"large.{fmt}"
            exporter = exporter_class()
            exporter.export(data, output_path)
            assert output_path.exists()

    def test_different_crs(
        self,
        tmp_path: Path,
    ) -> None:
        """Test export with different CRS."""
        # UTM Zone 10N (common for San Francisco area)
        boundary = Polygon([
            (551000, 4180000),
            (552000, 4180000),
            (552000, 4181000),
            (551000, 4181000),
            (551000, 4180000),
        ])

        data = ExportData("UTM Test", 32610, boundary)

        # GeoJSON should include correct CRS
        output_path = tmp_path / "utm.geojson"
        exporter = GeoJSONExporter()
        exporter.export(data, output_path)

        with open(output_path, 'r') as f:
            geojson = json.load(f)

        assert "EPSG::32610" in geojson["crs"]["properties"]["name"]
