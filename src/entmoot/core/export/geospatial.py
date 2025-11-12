"""
Geospatial export module for site layouts.

Provides export functionality to:
- KMZ (Google Earth) with custom icons and styling
- GeoJSON (QGIS/web mapping) with proper feature collections
- DXF (AutoCAD) with layers and proper CAD structure

All exports are properly georeferenced.
"""

import io
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from xml.etree import ElementTree as ET

import ezdxf
from ezdxf import units
from ezdxf.enums import TextEntityAlignment
import simplekml
from shapely.geometry import (
    Point as ShapelyPoint,
    Polygon as ShapelyPolygon,
    LineString as ShapelyLineString,
    MultiPolygon,
    MultiLineString,
    MultiPoint,
)
from shapely.geometry.base import BaseGeometry

logger = logging.getLogger(__name__)


class ExportData:
    """
    Container for data to be exported to geospatial formats.

    Attributes:
        project_name: Name of the project
        crs_epsg: EPSG code for coordinate reference system
        site_boundary: Site boundary polygon
        constraints: List of constraint geometries with metadata
        assets: List of asset geometries with metadata
        roads: List of road line geometries with metadata
        buildable_zones: List of buildable area polygons
        metadata: Additional metadata for the export
    """

    def __init__(
        self,
        project_name: str,
        crs_epsg: int = 4326,  # WGS84 default
        site_boundary: Optional[ShapelyPolygon] = None,
    ) -> None:
        """
        Initialize export data.

        Args:
            project_name: Name of the project
            crs_epsg: EPSG code (default: 4326 for WGS84)
            site_boundary: Site boundary polygon
        """
        self.project_name = project_name
        self.crs_epsg = crs_epsg
        self.site_boundary = site_boundary

        # Data collections
        self.constraints: List[Dict[str, Any]] = []
        self.assets: List[Dict[str, Any]] = []
        self.roads: List[Dict[str, Any]] = []
        self.buildable_zones: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {
            'created_at': datetime.now().isoformat(),
            'crs': f'EPSG:{crs_epsg}',
        }

    def add_constraint(
        self,
        geometry: BaseGeometry,
        name: str,
        constraint_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a constraint to the export."""
        self.constraints.append({
            'geometry': geometry,
            'name': name,
            'type': constraint_type,
            'properties': properties or {},
        })

    def add_asset(
        self,
        geometry: BaseGeometry,
        name: str,
        asset_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an asset to the export."""
        self.assets.append({
            'geometry': geometry,
            'name': name,
            'type': asset_type,
            'properties': properties or {},
        })

    def add_road(
        self,
        geometry: ShapelyLineString,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a road to the export."""
        self.roads.append({
            'geometry': geometry,
            'name': name,
            'properties': properties or {},
        })

    def add_buildable_zone(
        self,
        geometry: ShapelyPolygon,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a buildable zone to the export."""
        self.buildable_zones.append({
            'geometry': geometry,
            'name': name,
            'properties': properties or {},
        })


class GeospatialExporter:
    """Base class for geospatial exporters."""

    def __init__(self) -> None:
        """Initialize exporter."""
        pass

    def export(self, data: ExportData, output_path: Path) -> None:
        """
        Export data to file.

        Args:
            data: Export data
            output_path: Path to output file

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError("Subclass must implement export()")


class KMZExporter(GeospatialExporter):
    """
    Export site layout to KMZ format for Google Earth.

    Creates a KMZ file with:
    - Organized folder structure
    - Custom icons for different asset types
    - Styled polygons and lines
    - Proper metadata
    """

    # Icon URLs for different asset types
    ASSET_ICONS = {
        'building': 'http://maps.google.com/mapfiles/kml/shapes/homegardenbusiness.png',
        'equipment_yard': 'http://maps.google.com/mapfiles/kml/shapes/ranger_station.png',
        'parking_lot': 'http://maps.google.com/mapfiles/kml/shapes/parking_lot.png',
        'storage_tank': 'http://maps.google.com/mapfiles/kml/shapes/water.png',
    }

    # Colors for different constraint types (AABBGGRR format)
    CONSTRAINT_COLORS = {
        'property_line': simplekml.Color.blue,
        'wetland': simplekml.Color.green,
        'floodplain': simplekml.Color.cyan,
        'steep_slope': simplekml.Color.orange,
        'setback': simplekml.Color.yellow,
    }

    def export(self, data: ExportData, output_path: Path) -> None:
        """
        Export to KMZ format.

        Args:
            data: Export data
            output_path: Path to output KMZ file
        """
        logger.info(f"Exporting to KMZ: {output_path}")

        # Create KML document
        kml = simplekml.Kml(name=data.project_name)

        # Add site boundary
        if data.site_boundary:
            self._add_site_boundary(kml, data.site_boundary)

        # Add buildable zones
        if data.buildable_zones:
            folder = kml.newfolder(name="Buildable Zones")
            for zone in data.buildable_zones:
                self._add_buildable_zone(folder, zone)

        # Add constraints
        if data.constraints:
            folder = kml.newfolder(name="Constraints")
            for constraint in data.constraints:
                self._add_constraint(folder, constraint)

        # Add assets
        if data.assets:
            folder = kml.newfolder(name="Assets")
            for asset in data.assets:
                self._add_asset(folder, asset)

        # Add roads
        if data.roads:
            folder = kml.newfolder(name="Road Network")
            for road in data.roads:
                self._add_road(folder, road)

        # Add metadata
        description = self._create_description(data)
        kml.document.description = description

        # Save as KMZ
        kml.savekmz(str(output_path))
        logger.info(f"KMZ export completed: {output_path}")

    def _add_site_boundary(self, kml: simplekml.Kml, boundary: ShapelyPolygon) -> None:
        """Add site boundary to KML."""
        coords = list(boundary.exterior.coords)
        pol = kml.newpolygon(name="Site Boundary")
        pol.outerboundaryis = coords

        # Style
        pol.style.linestyle.color = simplekml.Color.blue
        pol.style.linestyle.width = 3
        pol.style.polystyle.color = simplekml.Color.changealphaint(50, simplekml.Color.blue)

    def _add_buildable_zone(self, folder: simplekml.Folder, zone: Dict[str, Any]) -> None:
        """Add buildable zone to KML folder."""
        geom = zone['geometry']
        name = zone['name']

        if isinstance(geom, ShapelyPolygon):
            coords = list(geom.exterior.coords)
            pol = folder.newpolygon(name=name)
            pol.outerboundaryis = coords

            # Style
            pol.style.linestyle.color = simplekml.Color.green
            pol.style.linestyle.width = 2
            pol.style.polystyle.color = simplekml.Color.changealphaint(
                80, simplekml.Color.lightgreen
            )

            # Add properties as description
            props = zone.get('properties', {})
            if props:
                pol.description = self._format_properties(props)

    def _add_constraint(self, folder: simplekml.Folder, constraint: Dict[str, Any]) -> None:
        """Add constraint to KML folder."""
        geom = constraint['geometry']
        name = constraint['name']
        ctype = constraint.get('type', 'unknown')

        # Get color for constraint type
        color = self.CONSTRAINT_COLORS.get(ctype, simplekml.Color.red)

        if isinstance(geom, ShapelyPolygon):
            coords = list(geom.exterior.coords)
            pol = folder.newpolygon(name=name)
            pol.outerboundaryis = coords

            # Style
            pol.style.linestyle.color = color
            pol.style.linestyle.width = 2
            pol.style.polystyle.color = simplekml.Color.changealphaint(100, color)

            # Add properties
            props = constraint.get('properties', {})
            props['constraint_type'] = ctype
            pol.description = self._format_properties(props)

    def _add_asset(self, folder: simplekml.Folder, asset: Dict[str, Any]) -> None:
        """Add asset to KML folder."""
        geom = asset['geometry']
        name = asset['name']
        atype = asset.get('type', 'building')

        if isinstance(geom, ShapelyPoint):
            # Use point with custom icon
            pnt = folder.newpoint(name=name)
            pnt.coords = [(geom.x, geom.y)]

            # Set icon
            icon_url = self.ASSET_ICONS.get(atype, self.ASSET_ICONS['building'])
            pnt.style.iconstyle.icon.href = icon_url
            pnt.style.iconstyle.scale = 1.2

        elif isinstance(geom, ShapelyPolygon):
            # Use polygon for asset footprint
            coords = list(geom.exterior.coords)
            pol = folder.newpolygon(name=name)
            pol.outerboundaryis = coords

            # Style based on type
            if atype == 'building':
                color = simplekml.Color.red
            elif atype == 'equipment_yard':
                color = simplekml.Color.orange
            elif atype == 'parking_lot':
                color = simplekml.Color.grey
            else:
                color = simplekml.Color.purple

            pol.style.linestyle.color = color
            pol.style.linestyle.width = 2
            pol.style.polystyle.color = simplekml.Color.changealphaint(150, color)

        # Add properties
        props = asset.get('properties', {})
        props['asset_type'] = atype
        if isinstance(geom, ShapelyPoint):
            pnt.description = self._format_properties(props)
        else:
            pol.description = self._format_properties(props)

    def _add_road(self, folder: simplekml.Folder, road: Dict[str, Any]) -> None:
        """Add road to KML folder."""
        geom = road['geometry']
        name = road['name']

        if isinstance(geom, ShapelyLineString):
            coords = list(geom.coords)
            line = folder.newlinestring(name=name)
            line.coords = coords

            # Style
            line.style.linestyle.color = simplekml.Color.brown
            line.style.linestyle.width = 4

            # Add properties
            props = road.get('properties', {})
            line.description = self._format_properties(props)

    def _format_properties(self, props: Dict[str, Any]) -> str:
        """Format properties as HTML description."""
        html = "<![CDATA[<table>"
        for key, value in props.items():
            html += f"<tr><td><b>{key}:</b></td><td>{value}</td></tr>"
        html += "</table>]]>"
        return html

    def _create_description(self, data: ExportData) -> str:
        """Create document description."""
        return f"""
        <![CDATA[
        <h2>{data.project_name}</h2>
        <p>Site layout export from Entmoot</p>
        <p><b>Created:</b> {data.metadata['created_at']}</p>
        <p><b>CRS:</b> {data.metadata['crs']}</p>
        <p><b>Assets:</b> {len(data.assets)}</p>
        <p><b>Constraints:</b> {len(data.constraints)}</p>
        <p><b>Roads:</b> {len(data.roads)}</p>
        ]]>
        """


class GeoJSONExporter(GeospatialExporter):
    """
    Export site layout to GeoJSON format for QGIS and web mapping.

    Creates valid GeoJSON FeatureCollection with:
    - Proper geometry types
    - Feature properties
    - CRS information
    """

    def export(self, data: ExportData, output_path: Path) -> None:
        """
        Export to GeoJSON format.

        Args:
            data: Export data
            output_path: Path to output GeoJSON file
        """
        logger.info(f"Exporting to GeoJSON: {output_path}")

        # Create feature collection
        feature_collection = {
            "type": "FeatureCollection",
            "name": data.project_name,
            "crs": {
                "type": "name",
                "properties": {
                    "name": f"urn:ogc:def:crs:EPSG::{data.crs_epsg}"
                }
            },
            "features": [],
            "metadata": data.metadata,
        }

        # Add site boundary
        if data.site_boundary:
            feature_collection["features"].append(
                self._create_feature(
                    data.site_boundary,
                    {
                        "name": "Site Boundary",
                        "layer": "boundary",
                        "type": "site_boundary",
                    }
                )
            )

        # Add buildable zones
        for zone in data.buildable_zones:
            feature_collection["features"].append(
                self._create_feature(
                    zone['geometry'],
                    {
                        "name": zone['name'],
                        "layer": "buildable_zones",
                        **zone.get('properties', {}),
                    }
                )
            )

        # Add constraints
        for constraint in data.constraints:
            feature_collection["features"].append(
                self._create_feature(
                    constraint['geometry'],
                    {
                        "name": constraint['name'],
                        "layer": "constraints",
                        "constraint_type": constraint['type'],
                        **constraint.get('properties', {}),
                    }
                )
            )

        # Add assets
        for asset in data.assets:
            feature_collection["features"].append(
                self._create_feature(
                    asset['geometry'],
                    {
                        "name": asset['name'],
                        "layer": "assets",
                        "asset_type": asset['type'],
                        **asset.get('properties', {}),
                    }
                )
            )

        # Add roads
        for road in data.roads:
            feature_collection["features"].append(
                self._create_feature(
                    road['geometry'],
                    {
                        "name": road['name'],
                        "layer": "roads",
                        **road.get('properties', {}),
                    }
                )
            )

        # Write to file
        with open(output_path, 'w') as f:
            json.dump(feature_collection, f, indent=2)

        logger.info(f"GeoJSON export completed: {output_path}")

    def _create_feature(
        self,
        geometry: BaseGeometry,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a GeoJSON feature from geometry and properties."""
        # Convert Shapely geometry to GeoJSON
        geom_dict = self._geometry_to_geojson(geometry)

        return {
            "type": "Feature",
            "geometry": geom_dict,
            "properties": properties,
        }

    def _geometry_to_geojson(self, geometry: BaseGeometry) -> Dict[str, Any]:
        """Convert Shapely geometry to GeoJSON geometry dict."""
        if isinstance(geometry, ShapelyPoint):
            return {
                "type": "Point",
                "coordinates": [geometry.x, geometry.y]
            }
        elif isinstance(geometry, ShapelyLineString):
            return {
                "type": "LineString",
                "coordinates": list(geometry.coords)
            }
        elif isinstance(geometry, ShapelyPolygon):
            coords = [list(geometry.exterior.coords)]
            for interior in geometry.interiors:
                coords.append(list(interior.coords))
            return {
                "type": "Polygon",
                "coordinates": coords
            }
        elif isinstance(geometry, MultiPoint):
            return {
                "type": "MultiPoint",
                "coordinates": [[p.x, p.y] for p in geometry.geoms]
            }
        elif isinstance(geometry, MultiLineString):
            return {
                "type": "MultiLineString",
                "coordinates": [list(line.coords) for line in geometry.geoms]
            }
        elif isinstance(geometry, MultiPolygon):
            coords = []
            for poly in geometry.geoms:
                poly_coords = [list(poly.exterior.coords)]
                for interior in poly.interiors:
                    poly_coords.append(list(interior.coords))
                coords.append(poly_coords)
            return {
                "type": "MultiPolygon",
                "coordinates": coords
            }
        else:
            raise ValueError(f"Unsupported geometry type: {type(geometry)}")


class DXFExporter(GeospatialExporter):
    """
    Export site layout to DXF format for AutoCAD.

    Creates DXF file with:
    - Organized layers by feature type
    - Polylines for boundaries and roads
    - Points for assets
    - Proper CAD structure
    - Text labels
    """

    # Layer definitions with colors (AutoCAD color index)
    LAYERS = {
        'BOUNDARY': {'color': 5},  # Blue
        'BUILDABLE': {'color': 3},  # Green
        'CONSTRAINTS': {'color': 1},  # Red
        'ASSETS': {'color': 4},  # Cyan
        'ROADS': {'color': 6},  # Magenta
        'LABELS': {'color': 7},  # White/Black
    }

    def export(self, data: ExportData, output_path: Path) -> None:
        """
        Export to DXF format.

        Args:
            data: Export data
            output_path: Path to output DXF file
        """
        logger.info(f"Exporting to DXF: {output_path}")

        # Create new DXF document
        doc = ezdxf.new('R2010')  # AutoCAD 2010 format
        doc.units = units.M  # Meters

        # Create layers
        for layer_name, layer_props in self.LAYERS.items():
            doc.layers.add(name=layer_name, color=layer_props['color'])

        # Get modelspace
        msp = doc.modelspace()

        # Add site boundary
        if data.site_boundary:
            self._add_polygon(msp, data.site_boundary, 'BOUNDARY', 'Site Boundary')

        # Add buildable zones
        for zone in data.buildable_zones:
            self._add_polygon(
                msp,
                zone['geometry'],
                'BUILDABLE',
                zone['name']
            )

        # Add constraints
        for constraint in data.constraints:
            self._add_polygon(
                msp,
                constraint['geometry'],
                'CONSTRAINTS',
                constraint['name']
            )

        # Add assets
        for asset in data.assets:
            geom = asset['geometry']
            if isinstance(geom, ShapelyPoint):
                self._add_point(msp, geom, 'ASSETS', asset['name'])
            elif isinstance(geom, ShapelyPolygon):
                self._add_polygon(msp, geom, 'ASSETS', asset['name'])

        # Add roads
        for road in data.roads:
            self._add_linestring(msp, road['geometry'], 'ROADS', road['name'])

        # Save DXF
        doc.saveas(str(output_path))
        logger.info(f"DXF export completed: {output_path}")

    def _add_polygon(
        self,
        msp: Any,
        polygon: ShapelyPolygon,
        layer: str,
        label: str,
    ) -> None:
        """Add polygon to modelspace."""
        # Convert to list of (x, y) tuples
        coords = list(polygon.exterior.coords)

        # Add as polyline
        msp.add_lwpolyline(
            coords,
            close=True,
            dxfattribs={'layer': layer}
        )

        # Add label at centroid
        centroid = polygon.centroid
        self._add_text(msp, centroid.x, centroid.y, label, layer='LABELS')

    def _add_linestring(
        self,
        msp: Any,
        linestring: ShapelyLineString,
        layer: str,
        label: str,
    ) -> None:
        """Add linestring to modelspace."""
        coords = list(linestring.coords)

        # Add as polyline (not closed)
        msp.add_lwpolyline(
            coords,
            close=False,
            dxfattribs={'layer': layer}
        )

        # Add label at midpoint
        midpoint = linestring.interpolate(0.5, normalized=True)
        self._add_text(msp, midpoint.x, midpoint.y, label, layer='LABELS')

    def _add_point(
        self,
        msp: Any,
        point: ShapelyPoint,
        layer: str,
        label: str,
    ) -> None:
        """Add point to modelspace."""
        # Add point entity
        msp.add_point(
            (point.x, point.y),
            dxfattribs={'layer': layer}
        )

        # Add label
        self._add_text(msp, point.x, point.y + 2, label, layer='LABELS')

    def _add_text(
        self,
        msp: Any,
        x: float,
        y: float,
        text: str,
        layer: str = 'LABELS',
        height: float = 2.0,
    ) -> None:
        """Add text label to modelspace."""
        msp.add_text(
            text,
            dxfattribs={
                'layer': layer,
                'height': height,
            }
        ).set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)
