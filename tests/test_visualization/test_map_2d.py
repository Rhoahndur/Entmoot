"""
Tests for 2D map rendering.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Point, LineString, Polygon, MultiPolygon

from entmoot.core.visualization.map_2d import (
    Map2DRenderer,
    MapConfig,
    StyleConfig,
    LayerConfig,
    LayerType,
    OutputFormat,
    DEFAULT_STYLES,
)


@pytest.fixture
def sample_geometries():
    """Create sample geometries for testing."""
    # Boundary
    boundary = Polygon([
        (0, 0), (100, 0), (100, 100), (0, 100), (0, 0)
    ])

    # Buildings
    building1 = Polygon([
        (10, 10), (30, 10), (30, 30), (10, 30), (10, 10)
    ])
    building2 = Polygon([
        (50, 50), (70, 50), (70, 70), (50, 70), (50, 50)
    ])

    # Roads
    road1 = LineString([
        (0, 50), (50, 50), (50, 0)
    ])
    road2 = LineString([
        (50, 50), (100, 50)
    ])

    # Constraints
    constraint = Polygon([
        (20, 60), (40, 60), (40, 80), (20, 80), (20, 60)
    ])

    # Points
    point1 = Point(15, 15)
    point2 = Point(60, 60)

    return {
        "boundary": boundary,
        "buildings": [building1, building2],
        "roads": [road1, road2],
        "constraints": [constraint],
        "points": [point1, point2],
    }


@pytest.fixture
def map_renderer():
    """Create a map renderer with default config."""
    config = MapConfig(
        title="Test Map",
        width=10,
        height=8,
        dpi=100,  # Lower DPI for faster tests
    )
    return Map2DRenderer(config)


class TestStyleConfig:
    """Tests for StyleConfig."""

    def test_default_style(self):
        """Test default style configuration."""
        style = StyleConfig()
        assert style.color == "#1f77b4"
        assert style.line_width == 1.0
        assert style.alpha == 1.0
        assert style.line_style == "-"
        assert style.marker == "o"
        assert style.marker_size == 6.0

    def test_custom_style(self):
        """Test custom style configuration."""
        style = StyleConfig(
            color="#ff0000",
            edge_color="#000000",
            line_width=2.0,
            alpha=0.5,
            hatch="///"
        )
        assert style.color == "#ff0000"
        assert style.edge_color == "#000000"
        assert style.line_width == 2.0
        assert style.alpha == 0.5
        assert style.hatch == "///"


class TestMapConfig:
    """Tests for MapConfig."""

    def test_default_config(self):
        """Test default map configuration."""
        config = MapConfig()
        assert config.width == 12.0
        assert config.height == 10.0
        assert config.dpi == 300
        assert config.show_legend is True
        assert config.show_scale is True
        assert config.show_north_arrow is True
        assert config.show_grid is False

    def test_custom_config(self):
        """Test custom map configuration."""
        config = MapConfig(
            title="Custom Map",
            width=15.0,
            height=12.0,
            dpi=150,
            show_grid=True,
            grid_spacing=10.0,
        )
        assert config.title == "Custom Map"
        assert config.width == 15.0
        assert config.height == 12.0
        assert config.dpi == 150
        assert config.show_grid is True
        assert config.grid_spacing == 10.0


class TestMap2DRenderer:
    """Tests for Map2DRenderer."""

    def test_initialization(self, map_renderer):
        """Test renderer initialization."""
        assert map_renderer.config is not None
        assert map_renderer.layers == []
        assert map_renderer._figure is None
        assert map_renderer._axes is None

    def test_add_layer(self, map_renderer, sample_geometries):
        """Test adding layers."""
        # Add boundary layer
        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        assert len(map_renderer.layers) == 1
        assert map_renderer.layers[0].name == "boundary"
        assert map_renderer.layers[0].layer_type == LayerType.BOUNDARIES

    def test_add_multiple_layers(self, map_renderer, sample_geometries):
        """Test adding multiple layers."""
        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        map_renderer.add_layer(
            name="buildings",
            geometries=sample_geometries["buildings"],
            layer_type=LayerType.ASSETS,
        )

        map_renderer.add_layer(
            name="roads",
            geometries=sample_geometries["roads"],
            layer_type=LayerType.ROADS,
        )

        assert len(map_renderer.layers) == 3
        assert map_renderer.layers[0].name == "boundary"
        assert map_renderer.layers[1].name == "buildings"
        assert map_renderer.layers[2].name == "roads"

    def test_add_layer_with_custom_style(self, map_renderer, sample_geometries):
        """Test adding layer with custom style."""
        custom_style = StyleConfig(
            color="#ff0000",
            line_width=2.0,
            alpha=0.5,
        )

        map_renderer.add_layer(
            name="buildings",
            geometries=sample_geometries["buildings"],
            style=custom_style,
            layer_type=LayerType.ASSETS,
        )

        assert len(map_renderer.layers) == 1
        layer = map_renderer.layers[0]
        assert layer.style.color == "#ff0000"
        assert layer.style.line_width == 2.0
        assert layer.style.alpha == 0.5

    def test_add_empty_layer(self, map_renderer):
        """Test adding empty layer (should be skipped)."""
        map_renderer.add_layer(
            name="empty",
            geometries=[],
            layer_type=LayerType.ASSETS,
        )

        assert len(map_renderer.layers) == 0

    def test_remove_layer(self, map_renderer, sample_geometries):
        """Test removing layers."""
        map_renderer.add_layer(
            name="layer1",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )
        map_renderer.add_layer(
            name="layer2",
            geometries=sample_geometries["buildings"],
            layer_type=LayerType.ASSETS,
        )

        assert len(map_renderer.layers) == 2

        removed = map_renderer.remove_layer("layer1")
        assert removed is True
        assert len(map_renderer.layers) == 1
        assert map_renderer.layers[0].name == "layer2"

    def test_remove_nonexistent_layer(self, map_renderer, sample_geometries):
        """Test removing non-existent layer."""
        map_renderer.add_layer(
            name="layer1",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        removed = map_renderer.remove_layer("nonexistent")
        assert removed is False
        assert len(map_renderer.layers) == 1

    def test_toggle_layer(self, map_renderer, sample_geometries):
        """Test toggling layer visibility."""
        map_renderer.add_layer(
            name="layer1",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        layer = map_renderer.layers[0]
        assert layer.visible is True

        # Toggle off
        result = map_renderer.toggle_layer("layer1")
        assert result is True
        assert layer.visible is False

        # Toggle on
        result = map_renderer.toggle_layer("layer1")
        assert result is True
        assert layer.visible is True

    def test_toggle_layer_with_explicit_state(self, map_renderer, sample_geometries):
        """Test toggling layer with explicit state."""
        map_renderer.add_layer(
            name="layer1",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        layer = map_renderer.layers[0]

        # Set to False explicitly
        result = map_renderer.toggle_layer("layer1", visible=False)
        assert result is True
        assert layer.visible is False

        # Set to True explicitly
        result = map_renderer.toggle_layer("layer1", visible=True)
        assert result is True
        assert layer.visible is True

    def test_calculate_bounds(self, map_renderer, sample_geometries):
        """Test bounds calculation."""
        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        bounds = map_renderer._calculate_bounds()

        # Should be approximately (0, 0, 100, 100) with margin
        assert bounds[0] < 0  # minx with margin
        assert bounds[1] < 0  # miny with margin
        assert bounds[2] > 100  # maxx with margin
        assert bounds[3] > 100  # maxy with margin

    def test_calculate_bounds_empty(self):
        """Test bounds calculation with no geometries."""
        renderer = Map2DRenderer()
        bounds = renderer._calculate_bounds()

        # Should return default bounds
        assert bounds == (0.0, 0.0, 1.0, 1.0)

    def test_render_basic(self, map_renderer, sample_geometries):
        """Test basic rendering."""
        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        fig = map_renderer.render()

        assert fig is not None
        assert map_renderer._figure is not None
        assert map_renderer._axes is not None

        # Clean up
        map_renderer.close()

    def test_render_multiple_layers(self, map_renderer, sample_geometries):
        """Test rendering multiple layers."""
        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )
        map_renderer.add_layer(
            name="buildings",
            geometries=sample_geometries["buildings"],
            layer_type=LayerType.ASSETS,
        )
        map_renderer.add_layer(
            name="roads",
            geometries=sample_geometries["roads"],
            layer_type=LayerType.ROADS,
        )

        fig = map_renderer.render()

        assert fig is not None

        # Clean up
        map_renderer.close()

    def test_render_with_points(self, map_renderer, sample_geometries):
        """Test rendering with point geometries."""
        map_renderer.add_layer(
            name="points",
            geometries=sample_geometries["points"],
            layer_type=LayerType.ASSETS,
        )

        fig = map_renderer.render()

        assert fig is not None

        # Clean up
        map_renderer.close()

    def test_render_with_multipolygon(self, map_renderer, sample_geometries):
        """Test rendering with MultiPolygon."""
        multi_poly = MultiPolygon([
            sample_geometries["buildings"][0],
            sample_geometries["buildings"][1],
        ])

        map_renderer.add_layer(
            name="multi",
            geometries=[multi_poly],
            layer_type=LayerType.ASSETS,
        )

        fig = map_renderer.render()

        assert fig is not None

        # Clean up
        map_renderer.close()

    def test_render_without_layers(self):
        """Test rendering without layers (should raise)."""
        renderer = Map2DRenderer()

        with pytest.raises(ValueError, match="No layers to render"):
            renderer.render()

    def test_render_with_invisible_layers(self, map_renderer, sample_geometries):
        """Test rendering with invisible layers."""
        map_renderer.add_layer(
            name="layer1",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        map_renderer.toggle_layer("layer1", visible=False)

        # Should render with default bounds (with warning)
        fig = map_renderer.render()
        assert fig is not None

        # Clean up
        map_renderer.close()

    def test_export_png(self, map_renderer, sample_geometries):
        """Test exporting to PNG."""
        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_map.png"
            result_path = map_renderer.export(output_path, format=OutputFormat.PNG)

            assert result_path.exists()
            assert result_path.suffix == ".png"
            assert result_path.stat().st_size > 0

        # Clean up
        map_renderer.close()

    def test_export_svg(self, map_renderer, sample_geometries):
        """Test exporting to SVG."""
        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_map.svg"
            result_path = map_renderer.export(output_path, format=OutputFormat.SVG)

            assert result_path.exists()
            assert result_path.suffix == ".svg"
            assert result_path.stat().st_size > 0

        # Clean up
        map_renderer.close()

    def test_export_auto_extension(self, map_renderer, sample_geometries):
        """Test export with auto extension."""
        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_map"  # No extension
            result_path = map_renderer.export(output_path, format=OutputFormat.PNG)

            assert result_path.exists()
            assert result_path.suffix == ".png"

        # Clean up
        map_renderer.close()

    def test_export_bytes(self, map_renderer, sample_geometries):
        """Test exporting to bytes."""
        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        image_bytes = map_renderer.export_bytes(format=OutputFormat.PNG)

        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 0

        # Clean up
        map_renderer.close()

    def test_render_with_legend(self, map_renderer, sample_geometries):
        """Test rendering with legend."""
        map_renderer.config.show_legend = True

        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
            label="Property Boundary",
        )
        map_renderer.add_layer(
            name="buildings",
            geometries=sample_geometries["buildings"],
            layer_type=LayerType.ASSETS,
            label="Buildings",
        )

        fig = map_renderer.render()

        assert fig is not None
        # Legend should be added to axes
        assert map_renderer._axes.get_legend() is not None

        # Clean up
        map_renderer.close()

    def test_render_with_scale_bar(self, map_renderer, sample_geometries):
        """Test rendering with scale bar."""
        map_renderer.config.show_scale = True

        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        fig = map_renderer.render()

        assert fig is not None

        # Clean up
        map_renderer.close()

    def test_render_with_north_arrow(self, map_renderer, sample_geometries):
        """Test rendering with north arrow."""
        map_renderer.config.show_north_arrow = True

        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        fig = map_renderer.render()

        assert fig is not None

        # Clean up
        map_renderer.close()

    def test_render_with_grid(self, map_renderer, sample_geometries):
        """Test rendering with grid."""
        map_renderer.config.show_grid = True
        map_renderer.config.grid_spacing = 20.0

        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        fig = map_renderer.render()

        assert fig is not None

        # Clean up
        map_renderer.close()

    def test_close(self, map_renderer, sample_geometries):
        """Test closing figure."""
        map_renderer.add_layer(
            name="boundary",
            geometries=[sample_geometries["boundary"]],
            layer_type=LayerType.BOUNDARIES,
        )

        map_renderer.render()

        assert map_renderer._figure is not None

        map_renderer.close()

        assert map_renderer._figure is None
        assert map_renderer._axes is None


class TestDefaultStyles:
    """Tests for default styles."""

    def test_default_styles_exist(self):
        """Test that default styles are defined."""
        assert "boundary" in DEFAULT_STYLES
        assert "constraint_wetland" in DEFAULT_STYLES
        assert "asset_building" in DEFAULT_STYLES
        assert "road_primary" in DEFAULT_STYLES

    def test_boundary_style(self):
        """Test boundary default style."""
        style = DEFAULT_STYLES["boundary"]
        assert style.color == "none"
        assert style.edge_color == "#000000"
        assert style.line_width == 2.0

    def test_constraint_style(self):
        """Test constraint default style."""
        style = DEFAULT_STYLES["constraint_wetland"]
        assert style.alpha < 1.0
        assert style.hatch is not None
