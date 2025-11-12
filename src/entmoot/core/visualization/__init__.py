"""
Visualization module for Entmoot.

This module provides 2D and 3D map rendering capabilities:
- 2D map rendering with multi-layer support
- 3D terrain visualization with asset extrusion
- Multiple output formats (PNG, SVG, HTML)
- Configurable styling and camera controls
"""

from entmoot.core.visualization.map_2d import (
    Map2DRenderer,
    MapConfig,
    StyleConfig,
    LayerConfig,
    LayerType,
    OutputFormat,
    DEFAULT_STYLES,
)

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

__all__ = [
    # 2D rendering
    "Map2DRenderer",
    "MapConfig",
    "StyleConfig",
    "LayerConfig",
    "LayerType",
    "OutputFormat",
    "DEFAULT_STYLES",
    # 3D rendering
    "Map3DRenderer",
    "Map3DConfig",
    "TerrainStyle3D",
    "AssetStyle3D",
    "CameraConfig",
    "LightingConfig",
    "CameraPreset",
    "RenderMode",
    "OutputFormat3D",
]
