"""
2D Map Rendering for site visualization.

This module provides comprehensive 2D map rendering capabilities including:
- Multi-layer rendering (terrain, constraints, assets, roads)
- Multiple output formats (PNG, SVG)
- Configurable styling and colors
- Legend generation
- Scale bar and north arrow
- Coordinate grid (optional)
- High-resolution output (300 DPI)
"""

import io
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
import numpy as np
from shapely.geometry import (
    Point,
    LineString,
    Polygon,
    MultiPolygon,
    MultiLineString,
    GeometryCollection,
)
from shapely.geometry.base import BaseGeometry

logger = logging.getLogger(__name__)


class LayerType(Enum):
    """Layer types for rendering order."""

    TERRAIN = 1
    CONSTRAINTS = 2
    ASSETS = 3
    ROADS = 4
    BOUNDARIES = 5
    ANNOTATIONS = 6


class OutputFormat(Enum):
    """Supported output formats."""

    PNG = "png"
    SVG = "svg"


@dataclass
class StyleConfig:
    """
    Styling configuration for map elements.

    Attributes:
        color: Fill or line color (hex or named color)
        edge_color: Edge color for polygons
        line_width: Line width in points
        alpha: Transparency (0.0-1.0)
        line_style: Line style ('-', '--', '-.', ':')
        marker: Marker style for points
        marker_size: Marker size in points
        hatch: Hatch pattern for fills
    """

    color: str = "#1f77b4"
    edge_color: Optional[str] = None
    line_width: float = 1.0
    alpha: float = 1.0
    line_style: str = "-"
    marker: str = "o"
    marker_size: float = 6.0
    hatch: Optional[str] = None


@dataclass
class LayerConfig:
    """
    Configuration for a map layer.

    Attributes:
        name: Layer name
        geometries: List of geometries to render
        style: Style configuration
        layer_type: Type of layer (for ordering)
        visible: Whether layer is visible
        label: Label for legend
        z_order: Z-order for rendering (higher = on top)
    """

    name: str
    geometries: List[BaseGeometry]
    style: StyleConfig
    layer_type: LayerType
    visible: bool = True
    label: Optional[str] = None
    z_order: Optional[int] = None


@dataclass
class MapConfig:
    """
    Configuration for map rendering.

    Attributes:
        title: Map title
        width: Figure width in inches
        height: Figure height in inches
        dpi: Dots per inch for output
        show_legend: Show legend
        show_scale: Show scale bar
        show_north_arrow: Show north arrow
        show_grid: Show coordinate grid
        grid_spacing: Grid spacing (auto if None)
        background_color: Background color
        font_size: Base font size
        margin: Margin as fraction of plot area
    """

    title: Optional[str] = None
    width: float = 12.0
    height: float = 10.0
    dpi: int = 300
    show_legend: bool = True
    show_scale: bool = True
    show_north_arrow: bool = True
    show_grid: bool = False
    grid_spacing: Optional[float] = None
    background_color: str = "#ffffff"
    font_size: int = 10
    margin: float = 0.05


# Default style configurations
DEFAULT_STYLES: Dict[str, StyleConfig] = {
    "boundary": StyleConfig(
        color="none",
        edge_color="#000000",
        line_width=2.0,
        alpha=1.0,
        line_style="-",
    ),
    "constraint_wetland": StyleConfig(
        color="#4a90e2",
        edge_color="#2c5aa0",
        line_width=0.5,
        alpha=0.4,
        hatch="///",
    ),
    "constraint_setback": StyleConfig(
        color="#ff6b6b",
        edge_color="#cc0000",
        line_width=0.5,
        alpha=0.3,
        hatch="\\\\\\",
    ),
    "constraint_easement": StyleConfig(
        color="#f39c12",
        edge_color="#d68910",
        line_width=0.5,
        alpha=0.3,
        hatch="xxx",
    ),
    "asset_building": StyleConfig(
        color="#8b4513",
        edge_color="#654321",
        line_width=1.0,
        alpha=0.8,
    ),
    "asset_parking": StyleConfig(
        color="#808080",
        edge_color="#404040",
        line_width=0.5,
        alpha=0.6,
    ),
    "road_primary": StyleConfig(
        color="#ffcc00",
        edge_color="#ff9900",
        line_width=3.0,
        alpha=1.0,
    ),
    "road_secondary": StyleConfig(
        color="#ffd966",
        edge_color="#ffb84d",
        line_width=2.0,
        alpha=1.0,
    ),
    "terrain_contour": StyleConfig(
        color="#8b7355",
        line_width=0.5,
        alpha=0.5,
        line_style="-",
    ),
}


class Map2DRenderer:
    """
    2D map renderer with multi-layer support and export capabilities.

    Supports rendering property boundaries, assets, roads, constraints,
    and terrain features with customizable styling.
    """

    def __init__(self, config: Optional[MapConfig] = None):
        """
        Initialize 2D map renderer.

        Args:
            config: Map configuration (uses defaults if None)
        """
        self.config = config or MapConfig()
        self.layers: List[LayerConfig] = []
        self._figure: Optional[Figure] = None
        self._axes: Optional[Axes] = None
        self._bounds: Optional[Tuple[float, float, float, float]] = None

    def add_layer(
        self,
        name: str,
        geometries: List[BaseGeometry],
        style: Optional[StyleConfig] = None,
        layer_type: LayerType = LayerType.ASSETS,
        label: Optional[str] = None,
    ) -> None:
        """
        Add a layer to the map.

        Args:
            name: Layer name
            geometries: List of geometries to render
            style: Style configuration (uses defaults if None)
            layer_type: Type of layer
            label: Label for legend (uses name if None)
        """
        if not geometries:
            logger.warning(f"Layer '{name}' has no geometries, skipping")
            return

        style = style or DEFAULT_STYLES.get(name, StyleConfig())
        label = label or name

        # Determine z-order based on layer type
        z_order_map = {
            LayerType.TERRAIN: 1,
            LayerType.CONSTRAINTS: 2,
            LayerType.ASSETS: 3,
            LayerType.ROADS: 4,
            LayerType.BOUNDARIES: 5,
            LayerType.ANNOTATIONS: 6,
        }
        z_order = z_order_map.get(layer_type, 3)

        layer = LayerConfig(
            name=name,
            geometries=geometries,
            style=style,
            layer_type=layer_type,
            label=label,
            z_order=z_order,
        )
        self.layers.append(layer)
        logger.info(f"Added layer '{name}' with {len(geometries)} geometries")

    def remove_layer(self, name: str) -> bool:
        """
        Remove a layer by name.

        Args:
            name: Layer name

        Returns:
            True if layer was removed
        """
        initial_count = len(self.layers)
        self.layers = [layer for layer in self.layers if layer.name != name]
        removed = len(self.layers) < initial_count

        if removed:
            logger.info(f"Removed layer '{name}'")
        else:
            logger.warning(f"Layer '{name}' not found")

        return removed

    def toggle_layer(self, name: str, visible: Optional[bool] = None) -> bool:
        """
        Toggle layer visibility.

        Args:
            name: Layer name
            visible: Visibility state (toggles if None)

        Returns:
            True if layer was found
        """
        for layer in self.layers:
            if layer.name == name:
                layer.visible = not layer.visible if visible is None else visible
                logger.info(f"Layer '{name}' visibility: {layer.visible}")
                return True

        logger.warning(f"Layer '{name}' not found")
        return False

    def _calculate_bounds(self) -> Tuple[float, float, float, float]:
        """
        Calculate bounding box for all visible geometries.

        Returns:
            Tuple of (minx, miny, maxx, maxy)
        """
        all_bounds = []

        for layer in self.layers:
            if not layer.visible:
                continue

            for geom in layer.geometries:
                if geom and not geom.is_empty:
                    all_bounds.append(geom.bounds)

        if not all_bounds:
            logger.warning("No geometries to calculate bounds")
            return (0.0, 0.0, 1.0, 1.0)

        minx = min(b[0] for b in all_bounds)
        miny = min(b[1] for b in all_bounds)
        maxx = max(b[2] for b in all_bounds)
        maxy = max(b[3] for b in all_bounds)

        # Add margin
        margin_x = (maxx - minx) * self.config.margin
        margin_y = (maxy - miny) * self.config.margin

        return (
            minx - margin_x,
            miny - margin_y,
            maxx + margin_x,
            maxy + margin_y,
        )

    def _render_geometry(
        self,
        ax: Axes,
        geom: BaseGeometry,
        style: StyleConfig,
        z_order: int,
    ) -> None:
        """
        Render a single geometry.

        Args:
            ax: Matplotlib axes
            geom: Geometry to render
            style: Style configuration
            z_order: Z-order for rendering
        """
        if geom.is_empty:
            return

        if isinstance(geom, Point):
            ax.plot(
                geom.x,
                geom.y,
                marker=style.marker,
                markersize=style.marker_size,
                color=style.color,
                alpha=style.alpha,
                zorder=z_order,
            )

        elif isinstance(geom, LineString):
            x, y = geom.xy
            ax.plot(
                x,
                y,
                color=style.color,
                linewidth=style.line_width,
                linestyle=style.line_style,
                alpha=style.alpha,
                zorder=z_order,
            )

        elif isinstance(geom, Polygon):
            x, y = geom.exterior.xy
            patch = mpatches.Polygon(
                list(zip(x, y)),
                facecolor=style.color,
                edgecolor=style.edge_color or style.color,
                linewidth=style.line_width,
                alpha=style.alpha,
                hatch=style.hatch,
                zorder=z_order,
            )
            ax.add_patch(patch)

            # Render holes
            for interior in geom.interiors:
                x, y = interior.xy
                hole_patch = mpatches.Polygon(
                    list(zip(x, y)),
                    facecolor=self.config.background_color,
                    edgecolor=style.edge_color or style.color,
                    linewidth=style.line_width,
                    alpha=1.0,
                    zorder=z_order,
                )
                ax.add_patch(hole_patch)

        elif isinstance(geom, (MultiPolygon, MultiLineString, GeometryCollection)):
            for sub_geom in geom.geoms:
                self._render_geometry(ax, sub_geom, style, z_order)

    def _render_layers(self, ax: Axes) -> None:
        """
        Render all visible layers.

        Args:
            ax: Matplotlib axes
        """
        # Sort layers by z-order
        sorted_layers = sorted(self.layers, key=lambda l: l.z_order or 0)

        for layer in sorted_layers:
            if not layer.visible:
                continue

            logger.debug(f"Rendering layer '{layer.name}' with {len(layer.geometries)} geometries")

            for geom in layer.geometries:
                self._render_geometry(ax, geom, layer.style, layer.z_order or 0)

    def _add_legend(self, ax: Axes) -> None:
        """
        Add legend to the map.

        Args:
            ax: Matplotlib axes
        """
        legend_elements = []

        for layer in self.layers:
            if not layer.visible:
                continue

            style = layer.style

            # Determine legend element type
            if style.color != "none":
                element = mpatches.Patch(
                    facecolor=style.color,
                    edgecolor=style.edge_color or style.color,
                    linewidth=style.line_width,
                    alpha=style.alpha,
                    hatch=style.hatch,
                    label=layer.label,
                )
            else:
                element = Line2D(
                    [0],
                    [0],
                    color=style.edge_color or style.color,
                    linewidth=style.line_width,
                    linestyle=style.line_style,
                    label=layer.label,
                )

            legend_elements.append(element)

        if legend_elements:
            ax.legend(
                handles=legend_elements,
                loc="upper right",
                fontsize=self.config.font_size - 1,
                framealpha=0.9,
            )

    def _add_scale_bar(self, ax: Axes, bounds: Tuple[float, float, float, float]) -> None:
        """
        Add scale bar to the map.

        Args:
            ax: Matplotlib axes
            bounds: Map bounds (minx, miny, maxx, maxy)
        """
        minx, miny, maxx, maxy = bounds
        map_width = maxx - minx

        # Calculate appropriate scale bar length (round to nice number)
        scale_length = map_width * 0.2
        magnitude = 10 ** np.floor(np.log10(scale_length))
        scale_length = np.round(scale_length / magnitude) * magnitude

        # Position at bottom left
        x_start = minx + map_width * 0.05
        y_pos = miny + (maxy - miny) * 0.05

        # Draw scale bar
        ax.plot(
            [x_start, x_start + scale_length],
            [y_pos, y_pos],
            color="black",
            linewidth=2,
            solid_capstyle="butt",
            zorder=100,
        )

        # Add ticks
        tick_height = (maxy - miny) * 0.01
        for x in [x_start, x_start + scale_length]:
            ax.plot([x, x], [y_pos, y_pos + tick_height], color="black", linewidth=2, zorder=100)

        # Add label
        label = f"{scale_length:.0f} m" if scale_length >= 1 else f"{scale_length*1000:.0f} cm"
        ax.text(
            x_start + scale_length / 2,
            y_pos + tick_height * 2,
            label,
            ha="center",
            va="bottom",
            fontsize=self.config.font_size - 2,
            zorder=100,
        )

    def _add_north_arrow(self, ax: Axes, bounds: Tuple[float, float, float, float]) -> None:
        """
        Add north arrow to the map.

        Args:
            ax: Matplotlib axes
            bounds: Map bounds (minx, miny, maxx, maxy)
        """
        minx, miny, maxx, maxy = bounds
        map_width = maxx - minx
        map_height = maxy - miny

        # Position at top left
        x_pos = minx + map_width * 0.05
        y_pos = maxy - map_height * 0.05
        arrow_length = map_height * 0.05

        # Draw arrow
        ax.annotate(
            "",
            xy=(x_pos, y_pos),
            xytext=(x_pos, y_pos - arrow_length),
            arrowprops=dict(arrowstyle="->", lw=2, color="black"),
            zorder=100,
        )

        # Add "N" label
        ax.text(
            x_pos,
            y_pos + arrow_length * 0.2,
            "N",
            ha="center",
            va="bottom",
            fontsize=self.config.font_size + 2,
            fontweight="bold",
            zorder=100,
        )

    def _add_grid(self, ax: Axes, bounds: Tuple[float, float, float, float]) -> None:
        """
        Add coordinate grid to the map.

        Args:
            ax: Matplotlib axes
            bounds: Map bounds (minx, miny, maxx, maxy)
        """
        minx, miny, maxx, maxy = bounds

        if self.config.grid_spacing:
            spacing = self.config.grid_spacing
        else:
            # Auto-calculate grid spacing
            map_width = maxx - minx
            magnitude = 10 ** np.floor(np.log10(map_width))
            spacing = magnitude

        # Configure grid
        ax.grid(
            True,
            which="both",
            linestyle=":",
            linewidth=0.5,
            color="gray",
            alpha=0.3,
            zorder=0,
        )

        # Set grid spacing
        ax.xaxis.set_major_locator(plt.MultipleLocator(spacing))
        ax.yaxis.set_major_locator(plt.MultipleLocator(spacing))

    def render(self) -> Figure:
        """
        Render the map to a matplotlib Figure.

        Returns:
            Matplotlib Figure object
        """
        if not self.layers:
            raise ValueError("No layers to render")

        # Calculate bounds
        bounds = self._calculate_bounds()
        self._bounds = bounds

        # Create figure and axes
        fig, ax = plt.subplots(
            figsize=(self.config.width, self.config.height),
            dpi=self.config.dpi,
        )

        self._figure = fig
        self._axes = ax

        # Set background
        ax.set_facecolor(self.config.background_color)
        fig.patch.set_facecolor(self.config.background_color)

        # Set bounds
        ax.set_xlim(bounds[0], bounds[2])
        ax.set_ylim(bounds[1], bounds[3])

        # Set aspect ratio to equal
        ax.set_aspect("equal", adjustable="box")

        # Render layers
        self._render_layers(ax)

        # Add optional elements
        if self.config.show_grid:
            self._add_grid(ax, bounds)

        if self.config.show_scale:
            self._add_scale_bar(ax, bounds)

        if self.config.show_north_arrow:
            self._add_north_arrow(ax, bounds)

        if self.config.show_legend:
            self._add_legend(ax)

        # Add title
        if self.config.title:
            ax.set_title(
                self.config.title,
                fontsize=self.config.font_size + 2,
                fontweight="bold",
                pad=20,
            )

        # Format axes
        ax.tick_params(labelsize=self.config.font_size - 2)
        ax.set_xlabel("Easting (m)", fontsize=self.config.font_size)
        ax.set_ylabel("Northing (m)", fontsize=self.config.font_size)

        # Tight layout
        plt.tight_layout()

        logger.info(f"Rendered map with {len(self.layers)} layers")
        return fig

    def export(
        self,
        output_path: Union[str, Path],
        format: OutputFormat = OutputFormat.PNG,
    ) -> Path:
        """
        Export the map to a file.

        Args:
            output_path: Output file path
            format: Output format

        Returns:
            Path to the exported file
        """
        if self._figure is None:
            self.render()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Ensure correct extension
        if not output_path.suffix:
            output_path = output_path.with_suffix(f".{format.value}")

        # Export
        self._figure.savefig(
            output_path,
            format=format.value,
            dpi=self.config.dpi,
            bbox_inches="tight",
            facecolor=self.config.background_color,
        )

        logger.info(f"Exported map to {output_path}")
        return output_path

    def export_bytes(self, format: OutputFormat = OutputFormat.PNG) -> bytes:
        """
        Export the map to bytes.

        Args:
            format: Output format

        Returns:
            Bytes of the exported image
        """
        if self._figure is None:
            self.render()

        buffer = io.BytesIO()
        self._figure.savefig(
            buffer,
            format=format.value,
            dpi=self.config.dpi,
            bbox_inches="tight",
            facecolor=self.config.background_color,
        )

        buffer.seek(0)
        return buffer.read()

    def close(self) -> None:
        """Close the figure to free memory."""
        if self._figure is not None:
            plt.close(self._figure)
            self._figure = None
            self._axes = None
