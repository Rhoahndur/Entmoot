/**
 * TypeScript types for API models
 */

export const FileType = {
  KMZ: 'kmz',
  KML: 'kml',
  GEOJSON: 'geojson',
  GEOTIFF: 'tif',
  TIFF: 'tiff',
} as const;

export type FileType = typeof FileType[keyof typeof FileType];

export const UploadStatus = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
} as const;

export type UploadStatus = typeof UploadStatus[keyof typeof UploadStatus];

export interface UploadResponse {
  upload_id: string;
  filename: string;
  file_size: number;
  message: string;
}

export interface ErrorResponse {
  error_code: string;
  message: string;
  details?: Record<string, any>;
}

export interface UploadMetadata {
  upload_id: string;
  filename: string;
  file_type: FileType;
  file_size: number;
  content_type: string;
  upload_time: string;
  status: UploadStatus;
  error_message?: string;
}

export interface HealthResponse {
  status: 'healthy' | 'unhealthy';
  service?: string;
  max_upload_size_mb?: number;
  allowed_extensions?: string[];
  virus_scan_enabled?: boolean;
  error?: string;
}
