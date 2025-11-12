/**
 * MapViewer Component - Interactive map display with MapLibre GL
 * Supports layers, controls, and interaction handlers
 */

import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type {
  Coordinate,
  PlacedAsset,
  ConstraintZone,
  RoadNetwork,
  BuildableArea,
  LayerVisibility,
  Bounds,
} from '../types/results';

interface MapViewerProps {
  bounds: Bounds;
  propertyBoundary: Coordinate[];
  assets: PlacedAsset[];
  roadNetwork?: RoadNetwork;
  constraintZones?: ConstraintZone[];
  buildableAreas?: BuildableArea[];
  layerVisibility: LayerVisibility;
  onAssetClick?: (asset: PlacedAsset) => void;
  onMapClick?: (coordinate: Coordinate) => void;
  onAssetMove?: (assetId: string, newPosition: Coordinate) => void;
  editable?: boolean;
  selectedAssetId?: string;
  violatingAssetIds?: string[];
}

export const MapViewer: React.FC<MapViewerProps> = ({
  bounds,
  propertyBoundary,
  assets,
  roadNetwork,
  constraintZones = [],
  buildableAreas = [],
  layerVisibility,
  onAssetClick,
  onMapClick,
  onAssetMove,
  editable = false,
  selectedAssetId,
  violatingAssetIds = [],
}) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [measuring, setMeasuring] = useState(false);
  const [measurementPoints, setMeasurementPoints] = useState<Coordinate[]>([]);
  const measuringRef = useRef(measuring);
  const measurementPointsRef = useRef(measurementPoints);
  const markersRef = useRef<Map<string, { marker: maplibregl.Marker; element: HTMLElement; popup: maplibregl.Popup }>>(new Map());
  const dragStateRef = useRef<{ assetId: string; marker: maplibregl.Marker; element: HTMLElement } | null>(null);

  // Keep refs in sync with state
  useEffect(() => {
    measuringRef.current = measuring;
  }, [measuring]);

  useEffect(() => {
    measurementPointsRef.current = measurementPoints;
  }, [measurementPoints]);

  // Initialize map
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    const centerLat = (bounds.north + bounds.south) / 2;
    const centerLng = (bounds.east + bounds.west) / 2;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'carto-light': {
            type: 'raster',
            tiles: [
              'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
              'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
              'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'
            ],
            tileSize: 256,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          }
        },
        layers: [
          {
            id: 'carto-light',
            type: 'raster',
            source: 'carto-light',
            minzoom: 0,
            maxzoom: 19
          }
        ]
      },
      center: [centerLng, centerLat],
      zoom: 15,
      pitch: 0,
      bearing: 0,
    });

    map.current.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.current.addControl(new maplibregl.ScaleControl(), 'bottom-left');
    map.current.addControl(new maplibregl.FullscreenControl(), 'top-right');

    map.current.on('load', () => {
      setMapLoaded(true);
    });

    map.current.on('click', (e) => {
      // Handle measurement mode clicks
      if (measuringRef.current) {
        const newPoint = {
          latitude: e.lngLat.lat,
          longitude: e.lngLat.lng,
        };
        setMeasurementPoints([...measurementPointsRef.current, newPoint]);
        return;
      }

      if (onMapClick) {
        onMapClick({
          latitude: e.lngLat.lat,
          longitude: e.lngLat.lng,
        });
      }
    });

    // Fit to bounds
    if (bounds) {
      map.current.fitBounds(
        [
          [bounds.west, bounds.south],
          [bounds.east, bounds.north],
        ],
        { padding: 50 }
      );
    }

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Update property boundary layer
  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    const sourceId = 'property-boundary';
    const layerId = 'property-boundary-layer';

    if (map.current.getLayer(layerId)) {
      map.current.removeLayer(layerId);
    }
    if (map.current.getSource(sourceId)) {
      map.current.removeSource(sourceId);
    }

    if (!layerVisibility.property_boundary) return;

    const coordinates = propertyBoundary.map((c) => [c.longitude, c.latitude]);
    // Close the polygon
    coordinates.push(coordinates[0]);

    map.current.addSource(sourceId, {
      type: 'geojson',
      data: {
        type: 'Feature',
        properties: {},
        geometry: {
          type: 'Polygon',
          coordinates: [coordinates],
        },
      },
    });

    map.current.addLayer({
      id: layerId,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': '#FF0000',
        'line-width': 3,
        'line-opacity': 0.8,
      },
    });

    map.current.addLayer({
      id: `${layerId}-fill`,
      type: 'fill',
      source: sourceId,
      paint: {
        'fill-color': '#FF0000',
        'fill-opacity': 0.1,
      },
    });
  }, [mapLoaded, propertyBoundary, layerVisibility.property_boundary]);

  // Update buildable areas layer
  useEffect(() => {
    if (!map.current || !mapLoaded || !layerVisibility.buildable_areas) return;

    const sourceId = 'buildable-areas';
    const layerId = 'buildable-areas-layer';

    if (map.current.getLayer(layerId)) {
      map.current.removeLayer(layerId);
    }
    if (map.current.getSource(sourceId)) {
      map.current.removeSource(sourceId);
    }

    const features = buildableAreas.map((area, index) => {
      const coordinates = area.polygon.map((c) => [c.longitude, c.latitude]);
      coordinates.push(coordinates[0]);

      return {
        type: 'Feature' as const,
        properties: {
          id: index,
          usable: area.usable,
          area: area.area,
        },
        geometry: {
          type: 'Polygon' as const,
          coordinates: [coordinates],
        },
      };
    });

    map.current.addSource(sourceId, {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features,
      },
    });

    map.current.addLayer({
      id: layerId,
      type: 'fill',
      source: sourceId,
      paint: {
        'fill-color': ['case', ['get', 'usable'], '#00FF00', '#FFAA00'],
        'fill-opacity': 0.3,
      },
    });
  }, [mapLoaded, buildableAreas, layerVisibility.buildable_areas]);

  // Update constraint zones layer
  useEffect(() => {
    if (!map.current || !mapLoaded || !layerVisibility.constraints) return;

    const sourceId = 'constraint-zones';
    const layerId = 'constraint-zones-layer';

    if (map.current.getLayer(layerId)) {
      map.current.removeLayer(layerId);
    }
    if (map.current.getSource(sourceId)) {
      map.current.removeSource(sourceId);
    }

    const severityColors: Record<string, string> = {
      low: '#FFFF00',
      medium: '#FFA500',
      high: '#FF0000',
    };

    const features = constraintZones.map((zone) => {
      const coordinates = zone.polygon.map((c) => [c.longitude, c.latitude]);
      coordinates.push(coordinates[0]);

      return {
        type: 'Feature' as const,
        properties: {
          id: zone.id,
          type: zone.type,
          severity: zone.severity,
          description: zone.description || '',
        },
        geometry: {
          type: 'Polygon' as const,
          coordinates: [coordinates],
        },
      };
    });

    map.current.addSource(sourceId, {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features,
      },
    });

    map.current.addLayer({
      id: layerId,
      type: 'fill',
      source: sourceId,
      paint: {
        'fill-color': [
          'match',
          ['get', 'severity'],
          'low',
          severityColors.low,
          'medium',
          severityColors.medium,
          'high',
          severityColors.high,
          '#CCCCCC',
        ],
        'fill-opacity': 0.4,
      },
    });

    map.current.addLayer({
      id: `${layerId}-outline`,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': '#000000',
        'line-width': 1,
        'line-opacity': 0.5,
      },
    });
  }, [mapLoaded, constraintZones, layerVisibility.constraints]);

  // Update roads layer
  useEffect(() => {
    if (!map.current || !mapLoaded || !layerVisibility.roads || !roadNetwork) return;

    const sourceId = 'roads';
    const baseLayerId = 'roads-base-layer';
    const borderLayerId = 'roads-border-layer';
    const centerlineLayerId = 'roads-centerline-layer';

    // Remove existing layers
    [centerlineLayerId, baseLayerId, borderLayerId].forEach(layerId => {
      if (map.current!.getLayer(layerId)) {
        map.current!.removeLayer(layerId);
      }
    });
    if (map.current.getSource(sourceId)) {
      map.current.removeSource(sourceId);
    }

    // Helper function to find the asset closest to a road endpoint
    const findAssetAtPoint = (point: Coordinate, threshold = 0.0001): PlacedAsset | null => {
      for (const asset of assets) {
        const distance = Math.sqrt(
          Math.pow(asset.position.latitude - point.latitude, 2) +
          Math.pow(asset.position.longitude - point.longitude, 2)
        );
        if (distance < threshold) {
          return asset;
        }
      }
      return null;
    };

    // Update road segments to connect to moved assets
    const features = roadNetwork.segments.map((segment) => {
      const points = [...segment.points];

      // Check and update first point (road start)
      const startAsset = findAssetAtPoint(points[0]);
      if (startAsset) {
        points[0] = startAsset.position;
      }

      // Check and update last point (road end)
      const endAsset = findAssetAtPoint(points[points.length - 1]);
      if (endAsset) {
        points[points.length - 1] = endAsset.position;
      }

      return {
        type: 'Feature' as const,
        properties: {
          id: segment.id,
          width: segment.width,
          grade: segment.grade,
          surface_type: segment.surface_type,
          length: segment.length,
        },
        geometry: {
          type: 'LineString' as const,
          coordinates: points.map((p) => [p.longitude, p.latitude]),
        },
      };
    });

    map.current.addSource(sourceId, {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features,
      },
    });

    // Road border (darker outline)
    map.current.addLayer({
      id: borderLayerId,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': '#2c2c2c',
        'line-width': ['+', ['get', 'width'], 2], // Slightly wider than base
        'line-opacity': 0.9,
      },
    });

    // Road base (asphalt color)
    map.current.addLayer({
      id: baseLayerId,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': [
          'match',
          ['get', 'surface_type'],
          'paved', '#4a4a4a',
          'gravel', '#8b7d6b',
          'dirt', '#a0826d',
          '#4a4a4a' // default
        ],
        'line-width': ['get', 'width'],
        'line-opacity': 0.85,
      },
    });

    // Road centerline (dashed yellow)
    map.current.addLayer({
      id: centerlineLayerId,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': '#ffd700',
        'line-width': 2,
        'line-opacity': 0.8,
        'line-dasharray': [3, 3],
      },
    });
  }, [mapLoaded, roadNetwork, layerVisibility.roads, assets]);

  // Helper function to calculate rotated rectangle corners
  const getAssetPolygon = (
    centerLat: number,
    centerLng: number,
    widthFeet: number,
    lengthFeet: number,
    rotationDegrees: number
  ): [number, number][] => {
    // Convert feet to approximate degrees (very rough approximation)
    // At equator: 1 degree latitude ≈ 364,000 feet, 1 degree longitude ≈ 288,200 feet
    // This is a simplification - in production you'd use proper projection math
    const latPerFoot = 1 / 364000;
    const lngPerFoot = 1 / 288200;

    const halfWidth = (widthFeet / 2) * lngPerFoot;
    const halfLength = (lengthFeet / 2) * latPerFoot;

    // Rotation in radians
    const rotRad = (rotationDegrees * Math.PI) / 180;
    const cos = Math.cos(rotRad);
    const sin = Math.sin(rotRad);

    // Four corners of the rectangle (before rotation)
    const corners = [
      [-halfWidth, -halfLength],
      [halfWidth, -halfLength],
      [halfWidth, halfLength],
      [-halfWidth, halfLength],
    ];

    // Rotate and translate corners
    return corners.map(([x, y]) => {
      const rotX = x * cos - y * sin;
      const rotY = x * sin + y * cos;
      return [centerLng + rotX, centerLat + rotY];
    });
  };

  // Update asset polygons (runs on every asset change for smooth rotation)
  useEffect(() => {
    if (!map.current || !mapLoaded || !layerVisibility.assets) return;

    // Create GeoJSON features for asset footprints
    const features = assets.map((asset) => {
      const corners = getAssetPolygon(
        asset.position.latitude,
        asset.position.longitude,
        asset.width,
        asset.length,
        asset.rotation
      );

      // Close the polygon
      corners.push(corners[0]);

      return {
        type: 'Feature' as const,
        properties: {
          id: asset.id,
          type: asset.type,
          selected: asset.id === selectedAssetId,
          violating: violatingAssetIds.includes(asset.id),
        },
        geometry: {
          type: 'Polygon' as const,
          coordinates: [corners],
        },
      };
    });

    const geojsonData = {
      type: 'FeatureCollection' as const,
      features,
    };

    // Check if source exists - if so, just update the data (much faster!)
    const source = map.current.getSource('asset-polygons') as maplibregl.GeoJSONSource;
    if (source) {
      // Efficiently update just the data without recreating layers
      source.setData(geojsonData);
    } else {
      // First time - create source and layers
      map.current.addSource('asset-polygons', {
        type: 'geojson',
        data: geojsonData,
      });

      // Add fill layer
      map.current.addLayer({
        id: 'asset-polygons-fill',
        type: 'fill',
        source: 'asset-polygons',
        paint: {
          'fill-color': [
            'case',
            ['get', 'violating'],
            '#DC2626', // Red for violating
            ['get', 'selected'],
            '#0000FF', // Blue for selected
            '#FF6600'  // Orange for normal
          ],
          'fill-opacity': 0.3,
        },
      });

      // Add outline layer
      map.current.addLayer({
        id: 'asset-polygons-outline',
        type: 'line',
        source: 'asset-polygons',
        paint: {
          'line-color': [
            'case',
            ['get', 'violating'],
            '#DC2626', // Red for violating
            ['get', 'selected'],
            '#0000FF', // Blue for selected
            '#FF6600'  // Orange for normal
          ],
          'line-width': [
            'case',
            ['get', 'violating'],
            4, // Thicker for violating
            ['get', 'selected'],
            3, // Medium for selected
            2  // Thin for normal
          ],
        },
      });

      // Add click handler for polygons (only once)
      map.current.on('click', 'asset-polygons-fill', (e) => {
        if (e.features && e.features.length > 0 && onAssetClick) {
          const assetId = e.features[0].properties?.id;
          const asset = assets.find(a => a.id === assetId);
          if (asset) {
            onAssetClick(asset);
          }
        }
      });

      // Change cursor on hover (only once)
      map.current.on('mouseenter', 'asset-polygons-fill', () => {
        if (map.current) {
          map.current.getCanvas().style.cursor = 'pointer';
        }
      });

      map.current.on('mouseleave', 'asset-polygons-fill', () => {
        if (map.current) {
          map.current.getCanvas().style.cursor = '';
        }
      });
    }
  }, [mapLoaded, assets, layerVisibility.assets, selectedAssetId, violatingAssetIds]);

  // Update asset markers (only when assets are added/removed or selection changes)
  useEffect(() => {
    if (!map.current || !mapLoaded || !layerVisibility.assets) return;

    // Global drag handlers
    const onGlobalMouseMove = (e: maplibregl.MapMouseEvent) => {
      if (!dragStateRef.current) return;
      dragStateRef.current.marker.setLngLat(e.lngLat);

      // Update the polygon in real-time
      const source = map.current?.getSource('asset-polygons') as maplibregl.GeoJSONSource;
      if (source) {
        const data = source._data as any;
        if (data?.features) {
          // Find the feature for this asset and update its geometry
          const featureIndex = data.features.findIndex(
            (f: any) => f.properties.id === dragStateRef.current!.assetId
          );
          if (featureIndex !== -1) {
            const asset = assets.find(a => a.id === dragStateRef.current!.assetId);
            if (asset) {
              const corners = getAssetPolygon(
                e.lngLat.lat,
                e.lngLat.lng,
                asset.width,
                asset.length,
                asset.rotation
              );
              corners.push(corners[0]); // Close polygon
              data.features[featureIndex].geometry.coordinates = [corners];
              source.setData(data);
            }
          }
        }
      }
    };

    const onGlobalMouseUp = () => {
      if (dragStateRef.current && onAssetMove) {
        const lngLat = dragStateRef.current.marker.getLngLat();
        onAssetMove(dragStateRef.current.assetId, {
          latitude: lngLat.lat,
          longitude: lngLat.lng,
        });
        dragStateRef.current.element.style.cursor = 'pointer';
        map.current!.dragPan.enable();
        dragStateRef.current = null;
      }
    };

    const onGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Shift' && editable && onAssetMove) {
        // Update cursor for all hovered markers
        const hovered = document.querySelector('.asset-marker:hover');
        if (hovered && !dragStateRef.current) {
          (hovered as HTMLElement).style.cursor = 'grab';
        }
      }
    };

    const onGlobalKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'Shift' && !dragStateRef.current) {
        // Reset cursor for all markers
        const hovered = document.querySelector('.asset-marker:hover');
        if (hovered) {
          (hovered as HTMLElement).style.cursor = 'pointer';
        }
      }
    };

    // Register global handlers (only once per render, cleaned up at end)
    map.current.on('mousemove', onGlobalMouseMove);
    document.addEventListener('mouseup', onGlobalMouseUp);
    document.addEventListener('keydown', onGlobalKeyDown);
    document.addEventListener('keyup', onGlobalKeyUp);

    // For now, recreate all markers to avoid stale closure issues
    // TODO: Optimize this later by properly updating event listeners
    markersRef.current.forEach((markerData) => {
      markerData.marker.remove();
      markerData.popup.remove(); // Clean up popup
    });
    markersRef.current.clear();

    // Create markers for each asset
    assets.forEach((asset) => {
      // Create new marker
      const el = document.createElement('div');
      el.className = 'asset-marker';
      el.style.width = '30px';
      el.style.height = '30px';
      el.style.borderRadius = '50%';
      el.style.backgroundColor = asset.id === selectedAssetId ? '#0000FF' : '#FF6600';
      el.style.border = '3px solid white';
      el.style.cursor = 'pointer';
      el.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';
      el.style.transition = 'box-shadow 0.2s, width 0.2s, height 0.2s';
      el.style.zIndex = asset.id === selectedAssetId ? '1000' : '999';

      const marker = new maplibregl.Marker({
        element: el,
        draggable: false,
      })
        .setLngLat([asset.position.longitude, asset.position.latitude])
        .addTo(map.current!);

      const onMouseDown = (e: MouseEvent) => {
        // Handle Shift+Drag for moving assets
        if (e.shiftKey && editable && onAssetMove) {
          dragStateRef.current = {
            assetId: asset.id,
            marker: marker,
            element: el,
          };
          el.style.cursor = 'grabbing';
          map.current!.dragPan.disable();
          e.stopPropagation();
          e.preventDefault();
          return;
        }

        // Otherwise just stop propagation for click handling
        e.stopPropagation();
      };

      const onClick = (e: MouseEvent) => {
        e.stopPropagation();
        if (onAssetClick) {
          onAssetClick(asset);
        }
      };

      // Add popup on hover
      const popup = new maplibregl.Popup({
        offset: 25,
        closeButton: false,
        closeOnClick: false
      }).setHTML(
        `
        <div style="padding: 8px;">
          <strong>${asset.type}</strong><br/>
          <small>Size: ${asset.width}' x ${asset.length}'</small><br/>
          <small>Rotation: ${asset.rotation}°</small>
          ${asset.id === selectedAssetId ? '<br/><small style="color: blue; font-weight: bold;">SELECTED</small>' : ''}
        </div>
        `
      );

      const handleMouseEnter = (e: MouseEvent) => {
        // Use size change instead of transform to avoid conflict with marker positioning
        el.style.width = '36px';
        el.style.height = '36px';
        el.style.marginLeft = '-3px';
        el.style.marginTop = '-3px';
        el.style.boxShadow = '0 4px 8px rgba(0,0,0,0.4)';
        if (e.shiftKey && editable && onAssetMove) {
          el.style.cursor = 'grab';
        }
        popup.setLngLat([asset.position.longitude, asset.position.latitude]).addTo(map.current!);
      };

      const handleMouseLeave = () => {
        // Reset size
        el.style.width = '30px';
        el.style.height = '30px';
        el.style.marginLeft = '0';
        el.style.marginTop = '0';
        el.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';
        if (!dragStateRef.current || dragStateRef.current.assetId !== asset.id) {
          el.style.cursor = 'pointer';
        }
        popup.remove();
      };

      // Register per-asset event listeners
      el.addEventListener('mousedown', onMouseDown);
      el.addEventListener('click', onClick);
      el.addEventListener('mouseenter', handleMouseEnter);
      el.addEventListener('mouseleave', handleMouseLeave);

      // Store marker and popup references for future updates
      markersRef.current.set(asset.id, { marker, element: el, popup });
    });

    // Cleanup function
    return () => {
      map.current?.off('mousemove', onGlobalMouseMove);
      document.removeEventListener('mouseup', onGlobalMouseUp);
      document.removeEventListener('keydown', onGlobalKeyDown);
      document.removeEventListener('keyup', onGlobalKeyUp);

      // Clean up all popups when unmounting or dependencies change
      markersRef.current.forEach((markerData) => {
        markerData.popup.remove();
      });
    };
  }, [mapLoaded, assets.length, JSON.stringify(assets.map(a => ({id: a.id, lat: a.position.latitude, lng: a.position.longitude}))), layerVisibility.assets, selectedAssetId, editable, onAssetClick, onAssetMove]);

  const toggleMeasurement = () => {
    const newMeasuring = !measuring;
    setMeasuring(newMeasuring);
    setMeasurementPoints([]);

    // Update cursor style
    if (map.current) {
      map.current.getCanvas().style.cursor = newMeasuring ? 'crosshair' : '';
    }
  };

  // Calculate distance between two points in feet
  const calculateDistance = (point1: Coordinate, point2: Coordinate): number => {
    const R = 20902231; // Earth's radius in feet
    const lat1 = (point1.latitude * Math.PI) / 180;
    const lat2 = (point2.latitude * Math.PI) / 180;
    const deltaLat = ((point2.latitude - point1.latitude) * Math.PI) / 180;
    const deltaLng = ((point2.longitude - point1.longitude) * Math.PI) / 180;

    const a =
      Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
      Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLng / 2) * Math.sin(deltaLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c;
  };

  // Update measurement layer
  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    // Remove existing measurement layers
    if (map.current.getLayer('measurement-line')) {
      map.current.removeLayer('measurement-line');
    }
    if (map.current.getLayer('measurement-points')) {
      map.current.removeLayer('measurement-points');
    }
    if (map.current.getSource('measurement')) {
      map.current.removeSource('measurement');
    }

    if (!measuring || measurementPoints.length === 0) return;

    // Create line features
    const features: any[] = [];

    // Add points
    measurementPoints.forEach((point, index) => {
      features.push({
        type: 'Feature',
        properties: {
          type: 'point',
          index,
        },
        geometry: {
          type: 'Point',
          coordinates: [point.longitude, point.latitude],
        },
      });
    });

    // Add lines between consecutive points
    if (measurementPoints.length > 1) {
      for (let i = 0; i < measurementPoints.length - 1; i++) {
        features.push({
          type: 'Feature',
          properties: {
            type: 'line',
            distance: calculateDistance(measurementPoints[i], measurementPoints[i + 1]),
          },
          geometry: {
            type: 'LineString',
            coordinates: [
              [measurementPoints[i].longitude, measurementPoints[i].latitude],
              [measurementPoints[i + 1].longitude, measurementPoints[i + 1].latitude],
            ],
          },
        });
      }
    }

    map.current.addSource('measurement', {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features,
      },
    });

    // Add line layer
    map.current.addLayer({
      id: 'measurement-line',
      type: 'line',
      source: 'measurement',
      filter: ['==', ['get', 'type'], 'line'],
      paint: {
        'line-color': '#FF0000',
        'line-width': 3,
        'line-dasharray': [2, 2],
      },
    });

    // Add point layer
    map.current.addLayer({
      id: 'measurement-points',
      type: 'circle',
      source: 'measurement',
      filter: ['==', ['get', 'type'], 'point'],
      paint: {
        'circle-radius': 6,
        'circle-color': '#FF0000',
        'circle-stroke-width': 2,
        'circle-stroke-color': '#FFFFFF',
      },
    });
  }, [mapLoaded, measuring, measurementPoints]);

  const handleScreenshot = () => {
    if (!map.current) return;

    map.current.once('render', () => {
      const canvas = map.current!.getCanvas();
      const link = document.createElement('a');
      link.download = 'map-screenshot.png';
      link.href = canvas.toDataURL();
      link.click();
    });
    map.current.triggerRepaint();
  };

  return (
    <div className="relative w-full h-full">
      <div ref={mapContainer} className="w-full h-full rounded-lg" />

      {/* Map Controls */}
      <div className="absolute top-4 left-4 bg-white rounded-lg shadow-lg p-2 space-y-2">
        <button
          onClick={toggleMeasurement}
          className={`w-full px-3 py-2 text-sm rounded ${
            measuring ? 'bg-blue-600 text-white' : 'bg-gray-100 hover:bg-gray-200'
          }`}
          title="Measure distance"
        >
          Measure
        </button>
        <button
          onClick={handleScreenshot}
          className="w-full px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded"
          title="Take screenshot"
        >
          Screenshot
        </button>
      </div>

      {/* Measurement Info */}
      {measuring && (
        <div className="absolute bottom-4 left-4 bg-white rounded-lg shadow-lg p-4 min-w-[200px]">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-gray-900">Measurement</h4>
            <button
              onClick={toggleMeasurement}
              className="text-xs text-red-600 hover:text-red-800"
            >
              Clear
            </button>
          </div>

          {measurementPoints.length === 0 ? (
            <p className="text-xs text-gray-600">Click on the map to start measuring</p>
          ) : (
            <div className="space-y-1">
              <p className="text-xs text-gray-600">
                Points: {measurementPoints.length}
              </p>

              {measurementPoints.length > 1 && (
                <>
                  <div className="border-t border-gray-200 pt-2 mt-2">
                    {measurementPoints.slice(0, -1).map((point, i) => {
                      const distance = calculateDistance(point, measurementPoints[i + 1]);
                      return (
                        <p key={i} className="text-xs text-gray-700">
                          Segment {i + 1}: {distance.toFixed(1)} ft
                        </p>
                      );
                    })}
                  </div>

                  <div className="border-t border-gray-200 pt-2 mt-2">
                    <p className="text-sm font-semibold text-blue-600">
                      Total: {measurementPoints.slice(0, -1).reduce((total, point, i) => {
                        return total + calculateDistance(point, measurementPoints[i + 1]);
                      }, 0).toFixed(1)} ft
                    </p>
                  </div>
                </>
              )}

              <p className="text-xs text-gray-500 mt-2">Click to add more points</p>
            </div>
          )}
        </div>
      )}

      {/* Loading Indicator */}
      {!mapLoaded && (
        <div className="absolute inset-0 bg-gray-900 bg-opacity-50 flex items-center justify-center rounded-lg">
          <div className="bg-white rounded-lg p-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-2 text-sm text-gray-600">Loading map...</p>
          </div>
        </div>
      )}
    </div>
  );
};
