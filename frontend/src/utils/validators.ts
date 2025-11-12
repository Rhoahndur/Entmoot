/**
 * Client-side validation utilities
 */

import { FileType } from '../types/api';

const MAX_FILE_SIZE_MB = 50;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

const ALLOWED_EXTENSIONS = ['.kmz', '.kml', '.geojson', '.tif', '.tiff'];

const MIME_TYPES: Record<string, string[]> = {
  '.kmz': ['application/vnd.google-earth.kmz', 'application/zip'],
  '.kml': ['application/vnd.google-earth.kml+xml', 'application/xml', 'text/xml'],
  '.geojson': ['application/geo+json', 'application/json'],
  '.tif': ['image/tiff'],
  '.tiff': ['image/tiff'],
};

/**
 * Validate file extension
 */
export const validateFileExtension = (filename: string): string | null => {
  const extension = filename.toLowerCase().substring(filename.lastIndexOf('.'));

  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return `Invalid file type. Allowed types: ${ALLOWED_EXTENSIONS.join(', ')}`;
  }

  return null;
};

/**
 * Validate file size
 */
export const validateFileSize = (size: number): string | null => {
  if (size > MAX_FILE_SIZE_BYTES) {
    return `File size (${formatFileSize(size)}) exceeds maximum allowed size of ${MAX_FILE_SIZE_MB}MB`;
  }

  if (size === 0) {
    return 'File is empty';
  }

  return null;
};

/**
 * Validate file type matches expected MIME type
 */
export const validateFileType = (file: File): string | null => {
  const extension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
  const expectedMimeTypes = MIME_TYPES[extension];

  if (!expectedMimeTypes) {
    return `Unknown file extension: ${extension}`;
  }

  if (!expectedMimeTypes.includes(file.type) && file.type !== '') {
    return `File type mismatch. Expected one of: ${expectedMimeTypes.join(', ')}, got: ${file.type}`;
  }

  return null;
};

/**
 * Validate file completely
 */
export const validateFile = (file: File): string | null => {
  // Check extension
  const extError = validateFileExtension(file.name);
  if (extError) return extError;

  // Check size
  const sizeError = validateFileSize(file.size);
  if (sizeError) return sizeError;

  // Check MIME type
  const typeError = validateFileType(file);
  if (typeError) return typeError;

  return null;
};

/**
 * Format file size for display
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
};

/**
 * Get file icon based on extension
 */
export const getFileIcon = (filename: string): string => {
  const extension = filename.toLowerCase().substring(filename.lastIndexOf('.'));

  switch (extension) {
    case '.kmz':
    case '.kml':
      return '🗺️';
    case '.geojson':
      return '📍';
    case '.tif':
    case '.tiff':
      return '🖼️';
    default:
      return '📄';
  }
};

/**
 * Extract file type from filename
 */
export const getFileType = (filename: string): FileType | null => {
  const extension = filename.toLowerCase().substring(filename.lastIndexOf('.')).replace('.', '');

  if (Object.values(FileType).includes(extension as FileType)) {
    return extension as FileType;
  }

  return null;
};
