/**
 * TypeScript types for results and layout data
 */

import { AssetType } from './config';

// Coordinate types
export interface Coordinate {
  latitude: number;
  longitude: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface Bounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

// Asset placement types
export interface PlacedAsset {
  id: string;
  type: AssetType;
  position: Coordinate;
  rotation: number; // degrees
  width: number;
  length: number;
  height?: number;
  polygon: Coordinate[]; // footprint corners
  properties?: Record<string, any>;
}

// Road network types
export interface RoadSegment {
  id: string;
  points: Coordinate[];
  width: number;
  grade: number; // percentage
  surface_type: 'paved' | 'gravel' | 'dirt';
  length: number; // feet
}

export interface RoadNetwork {
  segments: RoadSegment[];
  total_length: number;
  intersections: Coordinate[];
}

// Constraint types
export const ConstraintType = {
  SETBACK: 'setback',
  WETLAND: 'wetland',
  SLOPE: 'slope',
  EASEMENT: 'easement',
  EXCLUSION: 'exclusion',
  PROPERTY_LINE: 'property_line',
} as const;

export type ConstraintType = typeof ConstraintType[keyof typeof ConstraintType];

export interface ConstraintZone {
  id: string;
  type: ConstraintType;
  polygon: Coordinate[];
  severity: 'low' | 'medium' | 'high'; // for visualization
  description?: string;
}

// Earthwork types
export interface EarthworkVolumes {
  cut: number; // cubic yards
  fill: number; // cubic yards
  net: number; // cubic yards (fill - cut)
  balance_ratio: number; // cut/fill ratio
}

export interface EarthworkZone {
  polygon: Coordinate[];
  cut_volume?: number;
  fill_volume?: number;
  average_depth: number;
}

// Buildable area types
export interface BuildableArea {
  polygon: Coordinate[];
  area: number; // square feet
  usable: boolean;
}

// Cost breakdown types
export interface CostBreakdown {
  earthwork: number;
  roads: number;
  utilities: number;
  drainage: number;
  landscaping: number;
  contingency: number;
  total: number;
}

// Metrics types
export interface LayoutMetrics {
  property_area: number; // square feet
  buildable_area: number; // square feet
  buildable_percentage: number;
  assets_placed: number;
  total_road_length: number; // feet
  earthwork_volumes: EarthworkVolumes;
  estimated_cost: CostBreakdown;
  constraint_violations: number;
  optimization_score: number; // 0-100
}

// Violation types
export interface ConstraintViolation {
  asset_id: string;
  constraint_type: ConstraintType;
  severity: 'warning' | 'error';
  message: string;
  location?: Coordinate;
}

// Layout alternative types
export interface LayoutAlternative {
  id: string;
  name: string;
  description?: string;
  metrics: LayoutMetrics;
  assets: PlacedAsset[];
  road_network: RoadNetwork;
  constraint_zones: ConstraintZone[];
  buildable_areas: BuildableArea[];
  earthwork_zones: EarthworkZone[];
  violations: ConstraintViolation[];
  created_at: string;
}

// Map layer types
export const LayerType = {
  BASE_MAP: 'base_map',
  TERRAIN: 'terrain',
  PROPERTY_BOUNDARY: 'property_boundary',
  ASSETS: 'assets',
  ROADS: 'roads',
  CONSTRAINTS: 'constraints',
  BUILDABLE_AREAS: 'buildable_areas',
  EARTHWORK: 'earthwork',
} as const;

export type LayerType = typeof LayerType[keyof typeof LayerType];

export interface LayerVisibility {
  [LayerType.BASE_MAP]: boolean;
  [LayerType.TERRAIN]: boolean;
  [LayerType.PROPERTY_BOUNDARY]: boolean;
  [LayerType.ASSETS]: boolean;
  [LayerType.ROADS]: boolean;
  [LayerType.CONSTRAINTS]: boolean;
  [LayerType.BUILDABLE_AREAS]: boolean;
  [LayerType.EARTHWORK]: boolean;
}

// Results response from API
export interface OptimizationResults {
  project_id: string;
  project_name: string;
  property_boundary: Coordinate[];
  bounds: Bounds;
  alternatives: LayoutAlternative[];
  selected_alternative_id?: string;
  created_at: string;
  updated_at: string;
}

// Edit operation types for undo/redo
export const EditOperationType = {
  MOVE_ASSET: 'move_asset',
  ROTATE_ASSET: 'rotate_asset',
  DELETE_ASSET: 'delete_asset',
  ADD_ASSET: 'add_asset',
} as const;

export type EditOperationType = typeof EditOperationType[keyof typeof EditOperationType];

export interface EditOperation {
  type: EditOperationType;
  assetId: string;
  before?: Partial<PlacedAsset>;
  after?: Partial<PlacedAsset>;
  timestamp: number;
}

// Export format types
export const ExportFormat = {
  PDF: 'pdf',
  KMZ: 'kmz',
  GEOJSON: 'geojson',
  DXF: 'dxf',
  PNG: 'png',
} as const;

export type ExportFormat = typeof ExportFormat[keyof typeof ExportFormat];

export interface ExportOptions {
  format: ExportFormat;
  includeMetrics?: boolean;
  includeConstraints?: boolean;
  includeEarthwork?: boolean;
  pageSize?: 'letter' | 'legal' | 'tabloid' | 'a4' | 'a3';
  orientation?: 'portrait' | 'landscape';
}
