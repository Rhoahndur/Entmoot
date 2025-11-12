/**
 * Real-time constraint violation checker for frontend
 * Checks assets against constraint zones and other assets
 */

import type {
  PlacedAsset,
  ConstraintZone,
  ConstraintViolation,
  Coordinate,
} from '../types/results';

/**
 * Check if a point is inside a polygon using ray casting algorithm
 */
function isPointInPolygon(point: Coordinate, polygon: Coordinate[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].longitude;
    const yi = polygon[i].latitude;
    const xj = polygon[j].longitude;
    const yj = polygon[j].latitude;

    const intersect =
      yi > point.latitude !== yj > point.latitude &&
      point.longitude < ((xj - xi) * (point.latitude - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

/**
 * Check if two polygons intersect (simple check: if any vertex of one is inside the other)
 */
function doPolygonsIntersect(poly1: Coordinate[], poly2: Coordinate[]): boolean {
  // Check if any vertex of poly1 is inside poly2
  for (const point of poly1) {
    if (isPointInPolygon(point, poly2)) {
      return true;
    }
  }
  // Check if any vertex of poly2 is inside poly1
  for (const point of poly2) {
    if (isPointInPolygon(point, poly1)) {
      return true;
    }
  }
  return false;
}

/**
 * Check if two assets overlap
 */
function doAssetsOverlap(asset1: PlacedAsset, asset2: PlacedAsset): boolean {
  return doPolygonsIntersect(asset1.polygon, asset2.polygon);
}

/**
 * Check if asset intersects with a constraint zone
 */
function isAssetInConstraintZone(
  asset: PlacedAsset,
  zone: ConstraintZone
): boolean {
  return doPolygonsIntersect(asset.polygon, zone.polygon);
}

/**
 * Get constraint violation message based on type
 */
function getViolationMessage(
  assetType: string,
  constraintType: string
): string {
  const messages: Record<string, string> = {
    setback: `Asset violates setback requirement`,
    wetland: `Asset is placed in protected wetland area`,
    slope: `Asset is on terrain with excessive slope`,
    easement: `Asset intersects with utility easement`,
    exclusion: `Asset is in excluded area`,
    property_line: `Asset crosses property boundary`,
  };
  return messages[constraintType] || `Asset violates ${constraintType} constraint`;
}

/**
 * Check if asset is fully contained within property boundary
 */
function isAssetInsideProperty(
  asset: PlacedAsset,
  propertyBoundary: Coordinate[]
): boolean {
  // Check if all corners of the asset are inside the property boundary
  for (const corner of asset.polygon) {
    if (!isPointInPolygon(corner, propertyBoundary)) {
      return false;
    }
  }
  return true;
}

/**
 * Check all constraint violations for assets
 */
export function checkConstraintViolations(
  assets: PlacedAsset[],
  constraintZones: ConstraintZone[],
  propertyBoundary?: Coordinate[]
): ConstraintViolation[] {
  const violations: ConstraintViolation[] = [];

  // Check if assets are outside property boundary
  if (propertyBoundary) {
    for (const asset of assets) {
      if (!isAssetInsideProperty(asset, propertyBoundary)) {
        violations.push({
          asset_id: asset.id,
          constraint_type: 'property_line',
          severity: 'error',
          message: 'Asset extends beyond property boundary',
          location: asset.position,
        });
      }
    }
  }

  // Check each asset against constraint zones
  for (const asset of assets) {
    for (const zone of constraintZones) {
      if (isAssetInConstraintZone(asset, zone)) {
        violations.push({
          asset_id: asset.id,
          constraint_type: zone.type,
          severity: zone.severity === 'high' ? 'error' : 'warning',
          message: getViolationMessage(asset.type, zone.type),
          location: asset.position,
        });
      }
    }
  }

  // Check for asset overlaps
  for (let i = 0; i < assets.length; i++) {
    for (let j = i + 1; j < assets.length; j++) {
      if (doAssetsOverlap(assets[i], assets[j])) {
        violations.push({
          asset_id: assets[i].id,
          constraint_type: 'exclusion',
          severity: 'error',
          message: `Asset overlaps with another asset (${assets[j].type})`,
          location: assets[i].position,
        });
        violations.push({
          asset_id: assets[j].id,
          constraint_type: 'exclusion',
          severity: 'error',
          message: `Asset overlaps with another asset (${assets[i].type})`,
          location: assets[j].position,
        });
      }
    }
  }

  return violations;
}

/**
 * Recalculate asset polygon based on position and rotation
 * This is a simplified version - assumes rectangular assets
 */
export function recalculateAssetPolygon(asset: PlacedAsset): Coordinate[] {
  const { position, width, length, rotation } = asset;
  const halfWidth = width / 2;
  const halfLength = length / 2;

  // Convert feet to approximate degrees (very rough approximation)
  // 1 degree latitude ≈ 364,000 feet at equator
  const latScale = 1 / 364000;
  const lngScale = 1 / 288200; // longitude varies by latitude, this is approximate

  // Create corners in local coordinate system (feet)
  const corners = [
    { x: -halfLength, y: -halfWidth },
    { x: halfLength, y: -halfWidth },
    { x: halfLength, y: halfWidth },
    { x: -halfLength, y: halfWidth },
  ];

  // Rotate and translate corners
  const radians = (rotation * Math.PI) / 180;
  const cos = Math.cos(radians);
  const sin = Math.sin(radians);

  return corners.map((corner) => {
    // Rotate
    const rotatedX = corner.x * cos - corner.y * sin;
    const rotatedY = corner.x * sin + corner.y * cos;

    // Translate to world coordinates
    return {
      latitude: position.latitude + rotatedY * latScale,
      longitude: position.longitude + rotatedX * lngScale,
    };
  });
}
