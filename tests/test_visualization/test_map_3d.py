"""
Tests for 3D map rendering.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, MultiLineString

from entmoot.core.visualization.map_3d import (
    Map3DRenderer,
    Map3DConfig,
    TerrainStyle3D,
    AssetStyle3D,
    CameraConfig,
    LightingConfig,
    CameraPreset,
    RenderMode,
    OutputFormat3D,
)


@pytest.fixture
def sample_terrain():
    """Create sample terrain data."""
    # Create a simple elevation grid (50x50)
    x = np.linspace(0, 100, 50)
    y = np.linspace(0, 100, 50)
    X, Y = np.meshgrid(x, y)

    # Create a simple terrain with a hill
    Z = 10 + 5 * np.sin(X / 20) * np.cos(Y / 20)

    return X, Y, Z


@pytest.fixture
def sample_geometries():
    """Create sample geometries for 3D rendering."""
    # Buildings
    building1 = Polygon([
        (20, 20), (30, 20), (30, 30), (20, 30), (20, 20)
    ])
    building2 = Polygon([
        (60, 60), (75, 60), (75, 75), (60, 75), (60, 60)
    ])

    # Roads
    road1 = LineString([
        (0, 50), (50, 50), (50, 100)
    ])
    road2 = LineString([
        (50, 50), (100, 50)
    ])

    # Multi geometries
    multi_building = MultiPolygon([building1, building2])
    multi_road = MultiLineString([road1, road2])

    return {
        "buildings": [building1, building2],
        "roads": [road1, road2],
        "multi_building": multi_building,
        "multi_road": multi_road,
    }


@pytest.fixture
def map_renderer():
    """Create a 3D map renderer with default config."""
    config = Map3DConfig(
        title="Test 3D Map",
        width=800,
        height=600,
    )
    return Map3DRenderer(config)


class TestCameraConfig:
    """Tests for CameraConfig."""

    def test_default_config(self):
        """Test default camera configuration."""
        config = CameraConfig()
        assert config.preset == CameraPreset.ISOMETRIC
        assert config.eye is None
        assert config.center is None
        assert config.up == (0, 0, 1)

    def test_custom_config(self):
        """Test custom camera configuration."""
        config = CameraConfig(
            preset=CameraPreset.TOP,
            eye=(1, 1, 2),
            center=(0, 0, 0),
            up=(0, 1, 0),
        )
        assert config.preset == CameraPreset.TOP
        assert config.eye == (1, 1, 2)
        assert config.center == (0, 0, 0)
        assert config.up == (0, 1, 0)


class TestLightingConfig:
    """Tests for LightingConfig."""

    def test_default_config(self):
        """Test default lighting configuration."""
        config = LightingConfig()
        assert config.ambient == 0.7
        assert config.diffuse == 0.8
        assert config.specular == 0.2
        assert config.roughness == 0.5
        assert config.fresnel == 0.2

    def test_custom_config(self):
        """Test custom lighting configuration."""
        config = LightingConfig(
            ambient=0.5,
            diffuse=1.0,
            specular=0.3,
            roughness=0.2,
            fresnel=0.1,
        )
        assert config.ambient == 0.5
        assert config.diffuse == 1.0
        assert config.specular == 0.3
        assert config.roughness == 0.2
        assert config.fresnel == 0.1


class TestTerrainStyle3D:
    """Tests for TerrainStyle3D."""

    def test_default_style(self):
        """Test default terrain style."""
        style = TerrainStyle3D()
        assert style.colorscale == "earth"
        assert style.show_contours is False
        assert style.opacity == 1.0
        assert style.show_wireframe is False
        assert style.vertical_exaggeration == 1.0

    def test_custom_style(self):
        """Test custom terrain style."""
        style = TerrainStyle3D(
            colorscale="viridis",
            show_contours=True,
            contour_width=2.0,
            opacity=0.8,
            vertical_exaggeration=2.0,
        )
        assert style.colorscale == "viridis"
        assert style.show_contours is True
        assert style.contour_width == 2.0
        assert style.opacity == 0.8
        assert style.vertical_exaggeration == 2.0


class TestAssetStyle3D:
    """Tests for AssetStyle3D."""

    def test_default_style(self):
        """Test default asset style."""
        style = AssetStyle3D()
        assert style.color == "#8b4513"
        assert style.opacity == 0.8
        assert style.show_edges is True
        assert style.edge_color == "#654321"
        assert style.edge_width == 1.0

    def test_custom_style(self):
        """Test custom asset style."""
        style = AssetStyle3D(
            color="#ff0000",
            opacity=0.9,
            show_edges=False,
            edge_color="#000000",
            edge_width=2.0,
        )
        assert style.color == "#ff0000"
        assert style.opacity == 0.9
        assert style.show_edges is False
        assert style.edge_color == "#000000"
        assert style.edge_width == 2.0


class TestMap3DConfig:
    """Tests for Map3DConfig."""

    def test_default_config(self):
        """Test default 3D map configuration."""
        config = Map3DConfig()
        assert config.width == 1200
        assert config.height == 800
        assert config.show_axes is True
        assert config.show_grid is True
        assert config.background_color == "#ffffff"
        assert config.dem_resolution is None
        assert isinstance(config.camera, CameraConfig)
        assert isinstance(config.lighting, LightingConfig)
        assert isinstance(config.terrain_style, TerrainStyle3D)
        assert isinstance(config.asset_style, AssetStyle3D)

    def test_custom_config(self):
        """Test custom 3D map configuration."""
        camera = CameraConfig(preset=CameraPreset.TOP)
        lighting = LightingConfig(ambient=0.5)
        terrain_style = TerrainStyle3D(colorscale="viridis")
        asset_style = AssetStyle3D(color="#ff0000")

        config = Map3DConfig(
            title="Custom 3D Map",
            width=1600,
            height=1200,
            camera=camera,
            lighting=lighting,
            terrain_style=terrain_style,
            asset_style=asset_style,
            show_axes=False,
            show_grid=False,
            dem_resolution=100,
        )

        assert config.title == "Custom 3D Map"
        assert config.width == 1600
        assert config.height == 1200
        assert config.camera.preset == CameraPreset.TOP
        assert config.lighting.ambient == 0.5
        assert config.terrain_style.colorscale == "viridis"
        assert config.asset_style.color == "#ff0000"
        assert config.show_axes is False
        assert config.show_grid is False
        assert config.dem_resolution == 100


class TestMap3DRenderer:
    """Tests for Map3DRenderer."""

    def test_initialization(self, map_renderer):
        """Test renderer initialization."""
        assert map_renderer.config is not None
        assert map_renderer.terrain_data is None
        assert map_renderer.terrain_x is None
        assert map_renderer.terrain_y is None
        assert map_renderer.assets == []
        assert map_renderer.roads == []
        assert map_renderer._figure is None

    def test_set_terrain(self, map_renderer, sample_terrain):
        """Test setting terrain data."""
        X, Y, Z = sample_terrain

        map_renderer.set_terrain(X, Y, Z, downsample=False)

        assert map_renderer.terrain_data is not None
        assert map_renderer.terrain_x is not None
        assert map_renderer.terrain_y is not None
        assert map_renderer.terrain_data.shape == Z.shape

    def test_set_terrain_1d_coordinates(self, map_renderer, sample_terrain):
        """Test setting terrain with 1D coordinate arrays."""
        X, Y, Z = sample_terrain

        # Extract 1D arrays
        x = X[0, :]
        y = Y[:, 0]

        map_renderer.set_terrain(x, y, Z, downsample=False)

        assert map_renderer.terrain_data is not None
        assert map_renderer.terrain_x.ndim == 2
        assert map_renderer.terrain_y.ndim == 2

    def test_set_terrain_with_vertical_exaggeration(self, map_renderer, sample_terrain):
        """Test terrain with vertical exaggeration."""
        X, Y, Z = sample_terrain

        map_renderer.config.terrain_style.vertical_exaggeration = 2.0
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        # Z values should be doubled
        assert np.allclose(map_renderer.terrain_data, Z * 2.0)

    def test_downsample_terrain(self, map_renderer):
        """Test terrain downsampling."""
        # Create large terrain
        x = np.linspace(0, 100, 200)
        y = np.linspace(0, 100, 200)
        X, Y = np.meshgrid(x, y)
        Z = 10 + np.sin(X / 20) * np.cos(Y / 20)

        # Set resolution limit
        map_renderer.config.dem_resolution = 50

        map_renderer.set_terrain(X, Y, Z, downsample=True)

        # Should be downsampled
        assert map_renderer.terrain_data.shape[0] <= 50
        assert map_renderer.terrain_data.shape[1] <= 50

    def test_add_asset(self, map_renderer, sample_terrain, sample_geometries):
        """Test adding assets."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        building = sample_geometries["buildings"][0]
        map_renderer.add_asset(building, height=10.0, name="Building 1")

        assert len(map_renderer.assets) == 1
        assert map_renderer.assets[0]["name"] == "Building 1"
        assert map_renderer.assets[0]["height"] == 10.0
        assert map_renderer.assets[0]["geometry"] == building

    def test_add_multiple_assets(self, map_renderer, sample_terrain, sample_geometries):
        """Test adding multiple assets."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        for i, building in enumerate(sample_geometries["buildings"]):
            map_renderer.add_asset(building, height=10.0, name=f"Building {i+1}")

        assert len(map_renderer.assets) == 2

    def test_add_asset_with_custom_style(self, map_renderer, sample_terrain, sample_geometries):
        """Test adding asset with custom style."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        custom_style = AssetStyle3D(
            color="#ff0000",
            opacity=0.9,
        )

        building = sample_geometries["buildings"][0]
        map_renderer.add_asset(building, height=10.0, style=custom_style)

        assert len(map_renderer.assets) == 1
        assert map_renderer.assets[0]["style"].color == "#ff0000"
        assert map_renderer.assets[0]["style"].opacity == 0.9

    def test_add_multipolygon_asset(self, map_renderer, sample_terrain, sample_geometries):
        """Test adding MultiPolygon asset."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        multi_building = sample_geometries["multi_building"]
        map_renderer.add_asset(multi_building, height=10.0)

        assert len(map_renderer.assets) == 1

    def test_add_road(self, map_renderer, sample_terrain, sample_geometries):
        """Test adding roads."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        road = sample_geometries["roads"][0]
        map_renderer.add_road(road, width=5.0, name="Main Road")

        assert len(map_renderer.roads) == 1
        assert map_renderer.roads[0]["name"] == "Main Road"
        assert map_renderer.roads[0]["width"] == 5.0

    def test_add_multiple_roads(self, map_renderer, sample_terrain, sample_geometries):
        """Test adding multiple roads."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        for i, road in enumerate(sample_geometries["roads"]):
            map_renderer.add_road(road, width=5.0, name=f"Road {i+1}")

        assert len(map_renderer.roads) == 2

    def test_add_multilinestring_road(self, map_renderer, sample_terrain, sample_geometries):
        """Test adding MultiLineString road."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        multi_road = sample_geometries["multi_road"]
        map_renderer.add_road(multi_road, width=5.0)

        assert len(map_renderer.roads) == 1

    def test_get_terrain_elevation(self, map_renderer, sample_terrain):
        """Test getting terrain elevation at a point."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        point = Point(50, 50)
        elevation = map_renderer._get_terrain_elevation(point)

        assert isinstance(elevation, float)
        assert elevation > 0  # Should be within terrain range

    def test_get_terrain_elevation_no_terrain(self, map_renderer):
        """Test getting elevation without terrain."""
        point = Point(50, 50)
        elevation = map_renderer._get_terrain_elevation(point)

        assert elevation == 0.0

    def test_create_terrain_surface(self, map_renderer, sample_terrain):
        """Test creating terrain surface."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        surface = map_renderer._create_terrain_surface()

        assert surface is not None
        assert hasattr(surface, "type")

    def test_create_terrain_surface_no_terrain(self, map_renderer):
        """Test creating surface without terrain (should raise)."""
        with pytest.raises(ValueError, match="No terrain data set"):
            map_renderer._create_terrain_surface()

    def test_create_asset_mesh(self, map_renderer, sample_terrain, sample_geometries):
        """Test creating asset mesh."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        building = sample_geometries["buildings"][0]
        map_renderer.add_asset(building, height=10.0)

        asset = map_renderer.assets[0]
        meshes = map_renderer._create_asset_mesh(asset)

        assert len(meshes) > 0
        assert hasattr(meshes[0], "type")

    def test_create_road_trace(self, map_renderer, sample_terrain, sample_geometries):
        """Test creating road trace."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        road = sample_geometries["roads"][0]
        map_renderer.add_road(road, width=5.0)

        road_data = map_renderer.roads[0]
        trace = map_renderer._create_road_trace(road_data)

        assert trace is not None
        assert hasattr(trace, "type")

    def test_get_camera_position_default(self, map_renderer, sample_terrain):
        """Test getting default camera position."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        camera = map_renderer._get_camera_position()

        assert "eye" in camera
        assert "center" in camera
        assert "up" in camera

    def test_get_camera_position_top_view(self, map_renderer, sample_terrain):
        """Test getting top-down camera position."""
        map_renderer.config.camera.preset = CameraPreset.TOP
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        camera = map_renderer._get_camera_position()

        assert camera["eye"]["x"] == 0
        assert camera["eye"]["y"] == 0
        assert camera["eye"]["z"] == 2

    def test_get_camera_position_custom(self, map_renderer, sample_terrain):
        """Test getting custom camera position."""
        map_renderer.config.camera.eye = (2, 2, 3)
        map_renderer.config.camera.center = (0, 0, 0.5)

        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        camera = map_renderer._get_camera_position()

        assert camera["eye"]["x"] == 2
        assert camera["eye"]["y"] == 2
        assert camera["eye"]["z"] == 3
        assert camera["center"]["x"] == 0
        assert camera["center"]["y"] == 0
        assert camera["center"]["z"] == 0.5

    def test_render_terrain_only(self, map_renderer, sample_terrain):
        """Test rendering terrain only."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        fig = map_renderer.render()

        assert fig is not None
        assert map_renderer._figure is not None

    def test_render_with_assets(self, map_renderer, sample_terrain, sample_geometries):
        """Test rendering with assets."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        for building in sample_geometries["buildings"]:
            map_renderer.add_asset(building, height=10.0)

        fig = map_renderer.render()

        assert fig is not None

    def test_render_with_roads(self, map_renderer, sample_terrain, sample_geometries):
        """Test rendering with roads."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        for road in sample_geometries["roads"]:
            map_renderer.add_road(road, width=5.0)

        fig = map_renderer.render()

        assert fig is not None

    def test_render_complete_scene(self, map_renderer, sample_terrain, sample_geometries):
        """Test rendering complete scene with terrain, assets, and roads."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        for building in sample_geometries["buildings"]:
            map_renderer.add_asset(building, height=10.0)

        for road in sample_geometries["roads"]:
            map_renderer.add_road(road, width=5.0)

        fig = map_renderer.render()

        assert fig is not None

    def test_render_without_terrain(self, map_renderer):
        """Test rendering without terrain."""
        fig = map_renderer.render()

        # Should render but with warning
        assert fig is not None

    def test_export_html(self, map_renderer, sample_terrain):
        """Test exporting to HTML."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_map.html"
            result_path = map_renderer.export(output_path, format=OutputFormat3D.HTML)

            assert result_path.exists()
            assert result_path.suffix == ".html"
            assert result_path.stat().st_size > 0

            # Check HTML content
            content = result_path.read_text()
            assert "plotly" in content.lower()

    def test_export_html_auto_extension(self, map_renderer, sample_terrain):
        """Test export HTML with auto extension."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_map"  # No extension
            result_path = map_renderer.export(output_path, format=OutputFormat3D.HTML)

            assert result_path.exists()
            assert result_path.suffix == ".html"

    def test_export_html_string(self, map_renderer, sample_terrain):
        """Test exporting HTML as string."""
        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        html_string = map_renderer.export_html_string()

        assert isinstance(html_string, str)
        assert len(html_string) > 0
        assert "plotly" in html_string.lower()

    def test_render_with_contours(self, map_renderer, sample_terrain):
        """Test rendering with contours."""
        map_renderer.config.terrain_style.show_contours = True
        map_renderer.config.terrain_style.contour_width = 2.0

        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        fig = map_renderer.render()

        assert fig is not None

    def test_render_with_custom_colorscale(self, map_renderer, sample_terrain):
        """Test rendering with custom colorscale."""
        map_renderer.config.terrain_style.colorscale = "viridis"

        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        fig = map_renderer.render()

        assert fig is not None

    def test_render_without_axes(self, map_renderer, sample_terrain):
        """Test rendering without axes."""
        map_renderer.config.show_axes = False

        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        fig = map_renderer.render()

        assert fig is not None

    def test_render_without_grid(self, map_renderer, sample_terrain):
        """Test rendering without grid."""
        map_renderer.config.show_grid = False

        X, Y, Z = sample_terrain
        map_renderer.set_terrain(X, Y, Z, downsample=False)

        fig = map_renderer.render()

        assert fig is not None


class TestEnums:
    """Tests for enumeration types."""

    def test_render_mode_enum(self):
        """Test RenderMode enum."""
        assert RenderMode.SURFACE.value == "surface"
        assert RenderMode.WIREFRAME.value == "wireframe"
        assert RenderMode.CONTOUR.value == "contour"
        assert RenderMode.HYBRID.value == "hybrid"

    def test_camera_preset_enum(self):
        """Test CameraPreset enum."""
        assert CameraPreset.TOP.value == "top"
        assert CameraPreset.ISOMETRIC.value == "isometric"
        assert CameraPreset.OBLIQUE.value == "oblique"
        assert CameraPreset.CUSTOM.value == "custom"

    def test_output_format_3d_enum(self):
        """Test OutputFormat3D enum."""
        assert OutputFormat3D.HTML.value == "html"
        assert OutputFormat3D.PNG.value == "png"
