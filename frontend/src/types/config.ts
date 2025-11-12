/**
 * TypeScript types for configuration models
 */

export const AssetType = {
  BUILDINGS: 'buildings',
  YARDS: 'yards',
  PARKING: 'parking',
  GREEN_SPACE: 'green_space',
  INFRASTRUCTURE: 'infrastructure',
} as const;

export type AssetType = typeof AssetType[keyof typeof AssetType];

export interface AssetConfig {
  type: AssetType;
  quantity: number;
  width: number;
  length: number;
  height?: number;
}

export interface ConstraintConfig {
  setback_distance: number;
  min_distance_between_assets: number;
  exclusion_zones_enabled: boolean;
  respect_property_lines: boolean;
  respect_easements: boolean;
  wetland_buffer: number;
  slope_limit: number;
}

export interface RoadConfig {
  min_width: number;
  max_grade: number;
  turning_radius: number;
  surface_type: 'paved' | 'gravel' | 'dirt';
  include_sidewalks: boolean;
}

export interface OptimizationWeights {
  cost: number;
  buildable_area: number;
  accessibility: number;
  environmental_impact: number;
  aesthetics: number;
}

export interface ProjectConfig {
  project_name: string;
  upload_id: string;
  assets: AssetConfig[];
  constraints: ConstraintConfig;
  road_design: RoadConfig;
  optimization_weights: OptimizationWeights;
  created_at?: string;
  updated_at?: string;
}

export interface ConfigPreset {
  id: string;
  name: string;
  description: string;
  config: Omit<ProjectConfig, 'project_name' | 'upload_id'>;
}
