"""
3D Terrain Visualization for site analysis.

This module provides 3D terrain visualization capabilities including:
- 3D terrain surface from DEM data
- Extruded assets with height
- Roads draped on terrain
- Interactive and static rendering
- Camera controls
- Lighting and shading
- Performance optimization for large DEMs
- Export to HTML (interactive) and PNG (static)
"""

import io
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.interpolate import griddata
from shapely.geometry import (
    Point,
    LineString,
    Polygon,
    MultiPolygon,
    MultiLineString,
)
from shapely.geometry.base import BaseGeometry

logger = logging.getLogger(__name__)


class RenderMode(Enum):
    """Rendering mode for 3D visualization."""

    SURFACE = "surface"  # Solid surface
    WIREFRAME = "wireframe"  # Wireframe only
    CONTOUR = "contour"  # Contour lines
    HYBRID = "hybrid"  # Surface with contours


class CameraPreset(Enum):
    """Camera position presets."""

    TOP = "top"  # Top-down view
    ISOMETRIC = "isometric"  # 45-degree isometric
    OBLIQUE = "oblique"  # 30-degree oblique
    CUSTOM = "custom"  # Custom position


class OutputFormat3D(Enum):
    """Supported 3D output formats."""

    HTML = "html"  # Interactive HTML
    PNG = "png"  # Static PNG image


@dataclass
class CameraConfig:
    """
    Camera configuration for 3D view.

    Attributes:
        preset: Camera preset
        eye: Camera position (x, y, z)
        center: Look-at point (x, y, z)
        up: Up vector (x, y, z)
    """

    preset: CameraPreset = CameraPreset.ISOMETRIC
    eye: Optional[Tuple[float, float, float]] = None
    center: Optional[Tuple[float, float, float]] = None
    up: Tuple[float, float, float] = (0, 0, 1)


@dataclass
class LightingConfig:
    """
    Lighting configuration for 3D rendering.

    Attributes:
        ambient: Ambient light intensity (0.0-1.0)
        diffuse: Diffuse light intensity (0.0-1.0)
        specular: Specular light intensity (0.0-1.0)
        roughness: Surface roughness (0.0-1.0)
        fresnel: Fresnel coefficient (0.0-1.0)
    """

    ambient: float = 0.7
    diffuse: float = 0.8
    specular: float = 0.2
    roughness: float = 0.5
    fresnel: float = 0.2


@dataclass
class TerrainStyle3D:
    """
    Styling for 3D terrain.

    Attributes:
        colorscale: Plotly colorscale name or custom colors
        show_contours: Show contour lines
        contour_width: Contour line width
        opacity: Surface opacity (0.0-1.0)
        show_wireframe: Show wireframe
        wireframe_color: Wireframe color
        wireframe_width: Wireframe line width
        vertical_exaggeration: Z-axis exaggeration factor
    """

    colorscale: str = "earth"
    show_contours: bool = False
    contour_width: float = 1.0
    opacity: float = 1.0
    show_wireframe: bool = False
    wireframe_color: str = "#000000"
    wireframe_width: float = 0.5
    vertical_exaggeration: float = 1.0


@dataclass
class AssetStyle3D:
    """
    Styling for 3D assets (buildings, etc.).

    Attributes:
        color: Asset color
        opacity: Asset opacity (0.0-1.0)
        show_edges: Show edges
        edge_color: Edge color
        edge_width: Edge line width
    """

    color: str = "#8b4513"
    opacity: float = 0.8
    show_edges: bool = True
    edge_color: str = "#654321"
    edge_width: float = 1.0


@dataclass
class Map3DConfig:
    """
    Configuration for 3D map rendering.

    Attributes:
        title: Map title
        width: Figure width in pixels
        height: Figure height in pixels
        camera: Camera configuration
        lighting: Lighting configuration
        terrain_style: Terrain styling
        asset_style: Asset styling
        show_axes: Show axis labels
        show_grid: Show grid
        background_color: Background color
        dem_resolution: DEM resolution for downsampling (None = no downsampling)
    """

    title: Optional[str] = None
    width: int = 1200
    height: int = 800
    camera: CameraConfig = field(default_factory=CameraConfig)
    lighting: LightingConfig = field(default_factory=LightingConfig)
    terrain_style: TerrainStyle3D = field(default_factory=TerrainStyle3D)
    asset_style: AssetStyle3D = field(default_factory=AssetStyle3D)
    show_axes: bool = True
    show_grid: bool = True
    background_color: str = "#ffffff"
    dem_resolution: Optional[int] = None


class Map3DRenderer:
    """
    3D map renderer with terrain visualization and asset extrusion.

    Supports interactive HTML output and static image export with
    optimized rendering for large terrain datasets.
    """

    def __init__(self, config: Optional[Map3DConfig] = None):
        """
        Initialize 3D map renderer.

        Args:
            config: 3D map configuration (uses defaults if None)
        """
        self.config = config or Map3DConfig()
        self.terrain_data: Optional[np.ndarray] = None
        self.terrain_x: Optional[np.ndarray] = None
        self.terrain_y: Optional[np.ndarray] = None
        self.assets: List[Dict[str, Any]] = []
        self.roads: List[Dict[str, Any]] = []
        self._figure: Optional[go.Figure] = None

    def set_terrain(
        self,
        x: np.ndarray,
        y: np.ndarray,
        z: np.ndarray,
        downsample: bool = True,
    ) -> None:
        """
        Set terrain data from coordinate arrays.

        Args:
            x: X coordinates (1D or 2D array)
            y: Y coordinates (1D or 2D array)
            z: Z elevations (2D array)
            downsample: Whether to downsample based on config
        """
        # Ensure 2D arrays
        if x.ndim == 1 and y.ndim == 1:
            x, y = np.meshgrid(x, y)

        # Apply vertical exaggeration
        z = z * self.config.terrain_style.vertical_exaggeration

        # Downsample if requested and resolution specified
        if downsample and self.config.dem_resolution:
            x, y, z = self._downsample_terrain(x, y, z)

        self.terrain_x = x
        self.terrain_y = y
        self.terrain_data = z

        logger.info(f"Terrain set: shape={z.shape}, range=[{z.min():.2f}, {z.max():.2f}]")

    def set_terrain_from_dem(
        self,
        dem_array: np.ndarray,
        transform: Any,
        downsample: bool = True,
    ) -> None:
        """
        Set terrain from DEM array with geotransform.

        Args:
            dem_array: DEM elevation array
            transform: Rasterio Affine transform
            downsample: Whether to downsample based on config
        """
        # Create coordinate arrays from transform
        rows, cols = dem_array.shape
        x = np.arange(cols) * transform.a + transform.c
        y = np.arange(rows) * transform.e + transform.f

        self.set_terrain(x, y, dem_array, downsample=downsample)

    def _downsample_terrain(
        self,
        x: np.ndarray,
        y: np.ndarray,
        z: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Downsample terrain data for performance.

        Args:
            x: X coordinates
            y: Y coordinates
            z: Z elevations

        Returns:
            Downsampled (x, y, z) arrays
        """
        target_res = self.config.dem_resolution
        if target_res is None:
            return x, y, z

        rows, cols = z.shape
        if rows <= target_res and cols <= target_res:
            return x, y, z

        # Calculate stride
        stride_y = max(1, rows // target_res)
        stride_x = max(1, cols // target_res)

        # Downsample
        x_down = x[::stride_y, ::stride_x]
        y_down = y[::stride_y, ::stride_x]
        z_down = z[::stride_y, ::stride_x]

        logger.info(f"Downsampled terrain from {z.shape} to {z_down.shape}")
        return x_down, y_down, z_down

    def add_asset(
        self,
        geometry: Union[Polygon, MultiPolygon],
        height: float = 5.0,
        name: Optional[str] = None,
        style: Optional[AssetStyle3D] = None,
    ) -> None:
        """
        Add an extruded asset (building, structure).

        Args:
            geometry: Asset footprint polygon
            height: Extrusion height in meters
            name: Asset name
            style: Asset style (uses config default if None)
        """
        style = style or self.config.asset_style

        # Get base elevation from terrain
        base_elevation = self._get_terrain_elevation(geometry.centroid)

        asset = {
            "geometry": geometry,
            "height": height,
            "base_elevation": base_elevation,
            "name": name or f"Asset_{len(self.assets)}",
            "style": style,
        }

        self.assets.append(asset)
        logger.debug(f"Added asset '{asset['name']}' with height {height}m")

    def add_road(
        self,
        geometry: Union[LineString, MultiLineString],
        width: float = 3.0,
        name: Optional[str] = None,
        color: str = "#ffcc00",
    ) -> None:
        """
        Add a road draped on terrain.

        Args:
            geometry: Road centerline
            width: Road width in meters
            name: Road name
            color: Road color
        """
        road = {
            "geometry": geometry,
            "width": width,
            "name": name or f"Road_{len(self.roads)}",
            "color": color,
        }

        self.roads.append(road)
        logger.debug(f"Added road '{road['name']}' with width {width}m")

    def _get_terrain_elevation(self, point: Point) -> float:
        """
        Get terrain elevation at a point.

        Args:
            point: Point to query

        Returns:
            Elevation at point (or 0 if no terrain)
        """
        if self.terrain_data is None:
            return 0.0

        # Find nearest grid point
        try:
            x_idx = np.argmin(np.abs(self.terrain_x[0, :] - point.x))
            y_idx = np.argmin(np.abs(self.terrain_y[:, 0] - point.y))
            return float(self.terrain_data[y_idx, x_idx])
        except (IndexError, ValueError):
            logger.warning(f"Could not get elevation at {point}")
            return 0.0

    def _create_terrain_surface(self) -> go.Surface:
        """
        Create terrain surface trace.

        Returns:
            Plotly Surface trace
        """
        if self.terrain_data is None:
            raise ValueError("No terrain data set")

        style = self.config.terrain_style

        # Create surface trace
        surface = go.Surface(
            x=self.terrain_x,
            y=self.terrain_y,
            z=self.terrain_data,
            colorscale=style.colorscale,
            opacity=style.opacity,
            showscale=True,
            colorbar=dict(title="Elevation (m)", len=0.7),
            lighting=dict(
                ambient=self.config.lighting.ambient,
                diffuse=self.config.lighting.diffuse,
                specular=self.config.lighting.specular,
                roughness=self.config.lighting.roughness,
                fresnel=self.config.lighting.fresnel,
            ),
            contours=dict(
                z=dict(
                    show=style.show_contours,
                    usecolormap=True,
                    highlightcolor="limegreen",
                    width=style.contour_width,
                    project=dict(z=False),
                )
            ),
            name="Terrain",
        )

        return surface

    def _create_asset_mesh(self, asset: Dict[str, Any]) -> List[go.Mesh3d]:
        """
        Create 3D mesh for an extruded asset.

        Args:
            asset: Asset dictionary

        Returns:
            List of Mesh3d traces
        """
        geometry = asset["geometry"]
        height = asset["height"]
        base_elev = asset["base_elevation"]
        style = asset["style"]

        meshes = []

        # Handle MultiPolygon
        polygons = [geometry] if isinstance(geometry, Polygon) else geometry.geoms

        for poly in polygons:
            # Extract exterior coordinates
            coords = list(poly.exterior.coords)
            n = len(coords) - 1  # Last point is duplicate

            # Create vertices (bottom and top)
            vertices_bottom = [(x, y, base_elev) for x, y in coords[:-1]]
            vertices_top = [(x, y, base_elev + height) for x, y in coords[:-1]]
            vertices = vertices_bottom + vertices_top

            x, y, z = zip(*vertices)

            # Create faces (triangles)
            faces_i = []
            faces_j = []
            faces_k = []

            # Bottom face (fan triangulation)
            for i in range(1, n - 1):
                faces_i.extend([0, 0, 0])
                faces_j.extend([i, i, i])
                faces_k.extend([i + 1, i + 1, i + 1])

            # Top face (fan triangulation)
            for i in range(1, n - 1):
                faces_i.extend([n, n, n])
                faces_j.extend([n + i + 1, n + i + 1, n + i + 1])
                faces_k.extend([n + i, n + i, n + i])

            # Side faces (quads as two triangles)
            for i in range(n):
                j = (i + 1) % n
                # Triangle 1
                faces_i.append(i)
                faces_j.append(j)
                faces_k.append(n + i)
                # Triangle 2
                faces_i.append(j)
                faces_j.append(n + j)
                faces_k.append(n + i)

            # Create mesh
            mesh = go.Mesh3d(
                x=list(x),
                y=list(y),
                z=list(z),
                i=faces_i,
                j=faces_j,
                k=faces_k,
                color=style.color,
                opacity=style.opacity,
                name=asset["name"],
                showlegend=True,
            )

            meshes.append(mesh)

        return meshes

    def _create_road_trace(self, road: Dict[str, Any]) -> go.Scatter3d:
        """
        Create 3D trace for a road draped on terrain.

        Args:
            road: Road dictionary

        Returns:
            Plotly Scatter3d trace
        """
        geometry = road["geometry"]

        # Handle MultiLineString
        lines = [geometry] if isinstance(geometry, LineString) else geometry.geoms

        all_x, all_y, all_z = [], [], []

        for line in lines:
            coords = list(line.coords)
            for x, y in coords:
                point = Point(x, y)
                z = self._get_terrain_elevation(point)
                all_x.append(x)
                all_y.append(y)
                all_z.append(z + 0.5)  # Slightly above terrain

            # Add None to separate line segments
            all_x.append(None)
            all_y.append(None)
            all_z.append(None)

        trace = go.Scatter3d(
            x=all_x,
            y=all_y,
            z=all_z,
            mode="lines",
            line=dict(color=road["color"], width=road["width"]),
            name=road["name"],
            showlegend=True,
        )

        return trace

    def _get_camera_position(self) -> Dict[str, Any]:
        """
        Get camera position based on configuration.

        Returns:
            Camera dictionary for plotly
        """
        camera_config = self.config.camera

        # Calculate bounds if needed
        if self.terrain_data is not None:
            x_center = np.mean(self.terrain_x)
            y_center = np.mean(self.terrain_y)
            z_center = np.mean(self.terrain_data)
            x_range = np.ptp(self.terrain_x)
            y_range = np.ptp(self.terrain_y)
            z_range = np.ptp(self.terrain_data)
            max_range = max(x_range, y_range, z_range)
        else:
            x_center = y_center = z_center = 0
            max_range = 100

        # Determine eye position based on preset
        if camera_config.eye is not None:
            eye = camera_config.eye
        elif camera_config.preset == CameraPreset.TOP:
            eye = (0, 0, 2)
        elif camera_config.preset == CameraPreset.ISOMETRIC:
            eye = (1.5, 1.5, 1.5)
        elif camera_config.preset == CameraPreset.OBLIQUE:
            eye = (1.5, 1.5, 1.0)
        else:
            eye = (1.5, 1.5, 1.5)

        # Determine center
        center = camera_config.center or (0, 0, 0)

        camera = dict(
            eye=dict(x=eye[0], y=eye[1], z=eye[2]),
            center=dict(x=center[0], y=center[1], z=center[2]),
            up=dict(x=camera_config.up[0], y=camera_config.up[1], z=camera_config.up[2]),
        )

        return camera

    def render(self) -> go.Figure:
        """
        Render the 3D map.

        Returns:
            Plotly Figure object
        """
        traces = []

        # Add terrain surface
        if self.terrain_data is not None:
            terrain_surface = self._create_terrain_surface()
            traces.append(terrain_surface)
        else:
            logger.warning("No terrain data set")

        # Add assets
        for asset in self.assets:
            asset_meshes = self._create_asset_mesh(asset)
            traces.extend(asset_meshes)

        # Add roads
        for road in self.roads:
            road_trace = self._create_road_trace(road)
            traces.append(road_trace)

        # Create figure
        fig = go.Figure(data=traces)

        # Configure layout
        camera = self._get_camera_position()

        fig.update_layout(
            title=self.config.title or "3D Site Visualization",
            width=self.config.width,
            height=self.config.height,
            scene=dict(
                xaxis=dict(
                    title="Easting (m)",
                    visible=self.config.show_axes,
                    showgrid=self.config.show_grid,
                    gridcolor="lightgray",
                ),
                yaxis=dict(
                    title="Northing (m)",
                    visible=self.config.show_axes,
                    showgrid=self.config.show_grid,
                    gridcolor="lightgray",
                ),
                zaxis=dict(
                    title="Elevation (m)",
                    visible=self.config.show_axes,
                    showgrid=self.config.show_grid,
                    gridcolor="lightgray",
                ),
                camera=camera,
                aspectmode="data",
            ),
            paper_bgcolor=self.config.background_color,
            plot_bgcolor=self.config.background_color,
            showlegend=True,
            legend=dict(x=0.02, y=0.98, bgcolor="rgba(255, 255, 255, 0.8)"),
        )

        self._figure = fig
        logger.info(f"Rendered 3D map with {len(traces)} traces")
        return fig

    def export(
        self,
        output_path: Union[str, Path],
        format: OutputFormat3D = OutputFormat3D.HTML,
    ) -> Path:
        """
        Export the 3D map to a file.

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
        if format == OutputFormat3D.HTML:
            self._figure.write_html(
                str(output_path),
                include_plotlyjs="cdn",
                auto_open=False,
            )
        elif format == OutputFormat3D.PNG:
            # Requires kaleido
            try:
                self._figure.write_image(
                    str(output_path),
                    width=self.config.width,
                    height=self.config.height,
                )
            except Exception as e:
                logger.error(f"Failed to export PNG (kaleido may not be installed): {e}")
                raise

        logger.info(f"Exported 3D map to {output_path}")
        return output_path

    def export_html_string(self) -> str:
        """
        Export the 3D map as HTML string.

        Returns:
            HTML string
        """
        if self._figure is None:
            self.render()

        return self._figure.to_html(
            include_plotlyjs="cdn",
            full_html=True,
        )

    def show(self) -> None:
        """Display the 3D map in a browser (interactive)."""
        if self._figure is None:
            self.render()

        self._figure.show()
