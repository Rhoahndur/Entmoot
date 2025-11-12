/**
 * Export utilities for downloading layouts in various formats
 */

import { jsPDF } from 'jspdf';
import { saveAs } from 'file-saver';
import type {
  OptimizationResults,
  LayoutAlternative,
  ExportFormat,
  ExportOptions,
} from '../types/results';

/**
 * Export layout as PDF report
 */
export const exportToPDF = async (
  alternative: LayoutAlternative,
  projectName: string,
  options?: ExportOptions
): Promise<void> => {
  const pdf = new jsPDF({
    orientation: options?.orientation || 'portrait',
    unit: 'mm',
    format: options?.pageSize || 'letter',
  });

  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 20;

  // Title
  pdf.setFontSize(24);
  pdf.text(projectName, margin, margin + 10);

  // Alternative name
  pdf.setFontSize(16);
  pdf.text(alternative.name, margin, margin + 20);

  if (alternative.description) {
    pdf.setFontSize(10);
    pdf.text(alternative.description, margin, margin + 28);
  }

  // Metrics section
  let y = margin + 40;
  pdf.setFontSize(14);
  pdf.text('Project Metrics', margin, y);

  y += 10;
  pdf.setFontSize(10);

  const metrics = [
    ['Property Area', `${alternative.metrics.property_area.toLocaleString('en-US', { maximumFractionDigits: 1 })} sq ft`],
    ['Buildable Area', `${alternative.metrics.buildable_area.toLocaleString('en-US', { maximumFractionDigits: 1 })} sq ft (${alternative.metrics.buildable_percentage.toFixed(1)}%)`],
    ['Assets Placed', alternative.metrics.assets_placed.toString()],
    ['Total Road Length', `${alternative.metrics.total_road_length.toLocaleString('en-US', { maximumFractionDigits: 1 })} ft`],
    ['Optimization Score', `${alternative.metrics.optimization_score.toFixed(1)}%`],
    ['Constraint Violations', alternative.metrics.constraint_violations.toString()],
  ];

  metrics.forEach(([label, value]) => {
    pdf.text(`${label}:`, margin, y);
    pdf.text(value, margin + 70, y);
    y += 7;
  });

  // Cost breakdown
  y += 10;
  pdf.setFontSize(14);
  pdf.text('Cost Breakdown', margin, y);

  y += 10;
  pdf.setFontSize(10);

  const costs = [
    ['Earthwork', alternative.metrics.estimated_cost.earthwork],
    ['Roads', alternative.metrics.estimated_cost.roads],
    ['Utilities', alternative.metrics.estimated_cost.utilities],
    ['Drainage', alternative.metrics.estimated_cost.drainage],
    ['Landscaping', alternative.metrics.estimated_cost.landscaping],
    ['Contingency', alternative.metrics.estimated_cost.contingency],
    ['Total', alternative.metrics.estimated_cost.total],
  ];

  costs.forEach(([label, value]) => {
    const formattedValue = `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
    pdf.text(`${label}:`, margin, y);
    pdf.text(formattedValue, margin + 70, y);
    y += 7;
  });

  // Earthwork section
  y += 10;
  pdf.setFontSize(14);
  pdf.text('Earthwork Summary', margin, y);

  y += 10;
  pdf.setFontSize(10);

  const earthwork = [
    ['Cut Volume', `${Math.abs(alternative.metrics.earthwork_volumes.cut).toLocaleString('en-US', { maximumFractionDigits: 1 })} yd³`],
    ['Fill Volume', `${alternative.metrics.earthwork_volumes.fill.toLocaleString('en-US', { maximumFractionDigits: 1 })} yd³`],
    ['Net Volume', `${alternative.metrics.earthwork_volumes.net.toLocaleString('en-US', { maximumFractionDigits: 1 })} yd³`],
    ['Balance Ratio', alternative.metrics.earthwork_volumes.balance_ratio.toFixed(1)],
  ];

  earthwork.forEach(([label, value]) => {
    pdf.text(`${label}:`, margin, y);
    pdf.text(value, margin + 70, y);
    y += 7;
  });

  // Asset list (new page if needed)
  if (y > pageHeight - 60) {
    pdf.addPage();
    y = margin;
  } else {
    y += 10;
  }

  pdf.setFontSize(14);
  pdf.text('Asset List', margin, y);

  y += 10;
  pdf.setFontSize(9);

  // Table headers
  pdf.text('Type', margin, y);
  pdf.text('Size (ft)', margin + 40, y);
  pdf.text('Rotation', margin + 80, y);
  pdf.text('Position', margin + 110, y);

  y += 7;

  alternative.assets.forEach((asset) => {
    if (y > pageHeight - margin) {
      pdf.addPage();
      y = margin;
    }

    const type = asset.type.replace('_', ' ');
    const size = `${asset.width.toFixed(1)} × ${asset.length.toFixed(1)}${asset.height ? ` × ${asset.height.toFixed(1)}` : ''}`;
    const rotation = `${asset.rotation.toFixed(1)}°`;
    const position = `${asset.position.latitude.toFixed(6)}, ${asset.position.longitude.toFixed(6)}`;

    pdf.text(type, margin, y);
    pdf.text(size, margin + 40, y);
    pdf.text(rotation, margin + 80, y);
    pdf.text(position, margin + 110, y);

    y += 6;
  });

  // Footer
  const timestamp = new Date().toLocaleString();
  pdf.setFontSize(8);
  pdf.text(`Generated on ${timestamp} by Entmoot`, margin, pageHeight - 10);

  // Save
  pdf.save(`${projectName.replace(/\s+/g, '_')}_${alternative.name.replace(/\s+/g, '_')}.pdf`);
};

/**
 * Validate coordinate has required properties
 */
const validateCoordinate = (coord: any): coord is { latitude: number; longitude: number } => {
  return coord && typeof coord.latitude === 'number' && typeof coord.longitude === 'number';
};

/**
 * Export layout as GeoJSON
 */
export const exportToGeoJSON = async (
  alternative: LayoutAlternative,
  propertyBoundary: Array<{ latitude: number; longitude: number }>,
  projectName: string
): Promise<void> => {
  const features: any[] = [];

  // Validate property boundary
  if (!propertyBoundary || propertyBoundary.length === 0) {
    throw new Error('Property boundary is missing or empty');
  }

  const validBoundary = propertyBoundary.filter(validateCoordinate);
  if (validBoundary.length === 0) {
    throw new Error('Property boundary has no valid coordinates');
  }

  // Property boundary
  features.push({
    type: 'Feature',
    properties: {
      name: 'Property Boundary',
      type: 'boundary',
    },
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          ...validBoundary.map((p) => [p.longitude, p.latitude]),
          [validBoundary[0].longitude, validBoundary[0].latitude], // Close polygon
        ],
      ],
    },
  });

  // Assets
  alternative.assets.forEach((asset) => {
    if (!asset.polygon || asset.polygon.length === 0) {
      console.warn(`Asset ${asset.id} has no polygon data, skipping`);
      return;
    }

    const validPolygon = asset.polygon.filter(validateCoordinate);
    if (validPolygon.length < 3) {
      console.warn(`Asset ${asset.id} has insufficient valid coordinates, skipping`);
      return;
    }

    features.push({
      type: 'Feature',
      properties: {
        id: asset.id,
        type: asset.type,
        width: asset.width,
        length: asset.length,
        height: asset.height,
        rotation: asset.rotation,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            ...validPolygon.map((p) => [p.longitude, p.latitude]),
            [validPolygon[0].longitude, validPolygon[0].latitude], // Close polygon
          ],
        ],
      },
    });
  });

  // Roads
  if (alternative.road_network && alternative.road_network.segments) {
    alternative.road_network.segments.forEach((segment) => {
      if (!segment.points || segment.points.length < 2) {
        console.warn(`Road segment ${segment.id} has insufficient points, skipping`);
        return;
      }

      const validPoints = segment.points.filter(validateCoordinate);
      if (validPoints.length < 2) {
        console.warn(`Road segment ${segment.id} has insufficient valid coordinates, skipping`);
        return;
      }

      features.push({
        type: 'Feature',
        properties: {
          id: segment.id,
          type: 'road',
          width: segment.width,
          grade: segment.grade,
          surface_type: segment.surface_type,
          length: segment.length,
        },
        geometry: {
          type: 'LineString',
          coordinates: validPoints.map((p) => [p.longitude, p.latitude]),
        },
      });
    });
  }

  // Constraint zones
  if (alternative.constraint_zones) {
    alternative.constraint_zones.forEach((zone) => {
      if (!zone.polygon || zone.polygon.length === 0) {
        return;
      }

      const validPolygon = zone.polygon.filter(validateCoordinate);
      if (validPolygon.length < 3) {
        return;
      }

      features.push({
        type: 'Feature',
        properties: {
          id: zone.id,
          type: zone.type,
          severity: zone.severity,
          description: zone.description,
        },
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              ...validPolygon.map((p) => [p.longitude, p.latitude]),
              [validPolygon[0].longitude, validPolygon[0].latitude], // Close polygon
            ],
          ],
        },
      });
    });
  }

  // Buildable areas
  if (alternative.buildable_areas) {
    alternative.buildable_areas.forEach((area) => {
      if (!area.polygon || area.polygon.length === 0) {
        return;
      }

      const validPolygon = area.polygon.filter(validateCoordinate);
      if (validPolygon.length < 3) {
        return;
      }

      features.push({
        type: 'Feature',
        properties: {
          type: 'buildable_area',
          area: area.area,
          usable: area.usable,
        },
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              ...validPolygon.map((p) => [p.longitude, p.latitude]),
              [validPolygon[0].longitude, validPolygon[0].latitude], // Close polygon
            ],
          ],
        },
      });
    });
  }

  const geojson = {
    type: 'FeatureCollection',
    properties: {
      name: projectName,
      alternative: alternative.name,
      created: new Date().toISOString(),
    },
    features,
  };

  const blob = new Blob([JSON.stringify(geojson, null, 2)], {
    type: 'application/geo+json',
  });

  saveAs(blob, `${projectName.replace(/\s+/g, '_')}_${alternative.name.replace(/\s+/g, '_')}.geojson`);
};

/**
 * Export layout as KMZ (simplified - creates KML and zips it)
 * Note: Full KMZ requires zip library, this creates KML for now
 */
export const exportToKMZ = async (
  alternative: LayoutAlternative,
  propertyBoundary: Array<{ latitude: number; longitude: number }>,
  projectName: string
): Promise<void> => {
  // Validate property boundary
  if (!propertyBoundary || propertyBoundary.length === 0) {
    throw new Error('Property boundary is missing or empty');
  }

  const validBoundary = propertyBoundary.filter(validateCoordinate);
  if (validBoundary.length === 0) {
    throw new Error('Property boundary has no valid coordinates');
  }

  let kml = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>${projectName} - ${alternative.name}</name>
    <description>Generated by Entmoot on ${new Date().toISOString()}</description>

    <!-- Styles -->
    <Style id="propertyBoundary">
      <LineStyle>
        <color>ff0000ff</color>
        <width>3</width>
      </LineStyle>
      <PolyStyle>
        <color>330000ff</color>
      </PolyStyle>
    </Style>

    <Style id="building">
      <PolyStyle>
        <color>ff0066ff</color>
      </PolyStyle>
    </Style>

    <Style id="road">
      <LineStyle>
        <color>ff555555</color>
        <width>4</width>
      </LineStyle>
    </Style>

    <!-- Property Boundary -->
    <Placemark>
      <name>Property Boundary</name>
      <styleUrl>#propertyBoundary</styleUrl>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
`;

  // Add boundary coordinates
  validBoundary.forEach((p) => {
    kml += `              ${p.longitude},${p.latitude},0\n`;
  });
  // Close the polygon
  kml += `              ${validBoundary[0].longitude},${validBoundary[0].latitude},0\n`;

  kml += `            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

    <!-- Assets -->
`;

  alternative.assets.forEach((asset) => {
    if (!asset.polygon || asset.polygon.length === 0) {
      return;
    }

    const validPolygon = asset.polygon.filter(validateCoordinate);
    if (validPolygon.length < 3) {
      return;
    }

    kml += `    <Placemark>
      <name>${asset.type} - ${asset.id.substring(0, 8)}</name>
      <description>Size: ${asset.width}' x ${asset.length}'${asset.height ? ` x ${asset.height}'` : ''}, Rotation: ${asset.rotation}°</description>
      <styleUrl>#building</styleUrl>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
`;

    validPolygon.forEach((p) => {
      kml += `              ${p.longitude},${p.latitude},0\n`;
    });
    // Close the polygon
    kml += `              ${validPolygon[0].longitude},${validPolygon[0].latitude},0\n`;

    kml += `            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

`;
  });

  // Add roads
  if (alternative.road_network && alternative.road_network.segments) {
    alternative.road_network.segments.forEach((segment) => {
      if (!segment.points || segment.points.length < 2) {
        return;
      }

      const validPoints = segment.points.filter(validateCoordinate);
      if (validPoints.length < 2) {
        return;
      }

      kml += `    <Placemark>
      <name>Road - ${segment.id}</name>
      <description>Width: ${segment.width}', Grade: ${segment.grade}%, Surface: ${segment.surface_type}</description>
      <styleUrl>#road</styleUrl>
      <LineString>
        <coordinates>
`;

      validPoints.forEach((p) => {
        kml += `          ${p.longitude},${p.latitude},0\n`;
      });

      kml += `        </coordinates>
      </LineString>
    </Placemark>

`;
    });
  }

  kml += `  </Document>
</kml>`;

  const blob = new Blob([kml], { type: 'application/vnd.google-earth.kml+xml' });
  saveAs(blob, `${projectName.replace(/\s+/g, '_')}_${alternative.name.replace(/\s+/g, '_')}.kml`);
};

/**
 * Export layout as DXF (simplified - creates basic DXF)
 */
export const exportToDXF = async (
  alternative: LayoutAlternative,
  propertyBoundary: Array<{ latitude: number; longitude: number }>,
  projectName: string
): Promise<void> => {
  // Validate property boundary
  if (!propertyBoundary || propertyBoundary.length === 0) {
    throw new Error('Property boundary is missing or empty');
  }

  const validBoundary = propertyBoundary.filter(validateCoordinate);
  if (validBoundary.length === 0) {
    throw new Error('Property boundary has no valid coordinates');
  }

  // Basic DXF header
  let dxf = `0
SECTION
2
HEADER
9
$ACADVER
1
AC1015
0
ENDSEC
0
SECTION
2
TABLES
0
ENDSEC
0
SECTION
2
ENTITIES
`;

  // Add property boundary as polyline
  dxf += `0
LWPOLYLINE
8
BOUNDARY
62
1
70
1
`;

  dxf += `90
${validBoundary.length + 1}
`;

  validBoundary.forEach((p) => {
    dxf += `10
${p.longitude}
20
${p.latitude}
`;
  });

  // Close polyline
  dxf += `10
${validBoundary[0].longitude}
20
${validBoundary[0].latitude}
`;

  // Add assets
  alternative.assets.forEach((asset, index) => {
    if (!asset.polygon || asset.polygon.length === 0) {
      return;
    }

    const validPolygon = asset.polygon.filter(validateCoordinate);
    if (validPolygon.length < 3) {
      return;
    }

    dxf += `0
LWPOLYLINE
8
ASSET_${asset.type.toUpperCase()}
62
${index + 2}
70
1
`;

    dxf += `90
${validPolygon.length + 1}
`;

    validPolygon.forEach((p) => {
      dxf += `10
${p.longitude}
20
${p.latitude}
`;
    });

    // Close polyline
    dxf += `10
${validPolygon[0].longitude}
20
${validPolygon[0].latitude}
`;
  });

  // Add roads
  if (alternative.road_network && alternative.road_network.segments) {
    alternative.road_network.segments.forEach((segment) => {
      if (!segment.points || segment.points.length < 2) {
        return;
      }

      const validPoints = segment.points.filter(validateCoordinate);
      if (validPoints.length < 2) {
        return;
      }

      dxf += `0
LWPOLYLINE
8
ROAD
62
7
70
0
`;

      dxf += `90
${validPoints.length}
`;

      validPoints.forEach((p) => {
        dxf += `10
${p.longitude}
20
${p.latitude}
`;
      });
    });
  }

  // DXF footer
  dxf += `0
ENDSEC
0
EOF
`;

  const blob = new Blob([dxf], { type: 'application/dxf' });
  saveAs(blob, `${projectName.replace(/\s+/g, '_')}_${alternative.name.replace(/\s+/g, '_')}.dxf`);
};

/**
 * Main export function that routes to appropriate exporter
 */
export const exportLayout = async (
  format: ExportFormat,
  results: OptimizationResults,
  alternativeId: string,
  options?: ExportOptions
): Promise<void> => {
  const alternative = results.alternatives.find((alt) => alt.id === alternativeId);
  if (!alternative) {
    throw new Error('Alternative not found');
  }

  switch (format) {
    case 'pdf':
      return exportToPDF(alternative, results.project_name, options);
    case 'geojson':
      return exportToGeoJSON(alternative, results.property_boundary, results.project_name);
    case 'kmz':
      return exportToKMZ(alternative, results.property_boundary, results.project_name);
    case 'dxf':
      return exportToDXF(alternative, results.property_boundary, results.project_name);
    default:
      throw new Error(`Unsupported export format: ${format}`);
  }
};
