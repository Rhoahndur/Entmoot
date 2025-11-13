/**
 * API client using Axios
 */

import axios, { AxiosError, type AxiosInstance } from 'axios';
import type { ErrorResponse, HealthResponse, UploadResponse } from '../types/api';
import type { OptimizationResults, PlacedAsset, ExportFormat } from '../types/results';
import type { ProjectConfig } from '../types/config';

// API base URL - can be configured via environment variable
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_V1_PREFIX = '/api/v1';

// Debug logging
console.log('Environment variables:', {
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
  API_BASE_URL,
  MODE: import.meta.env.MODE,
  PROD: import.meta.env.PROD,
});

/**
 * Create configured Axios instance
 */
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000, // 30 seconds
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Request interceptor for logging
  client.interceptors.request.use(
    (config) => {
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor for error handling
  client.interceptors.response.use(
    (response) => {
      return response;
    },
    (error: AxiosError<ErrorResponse>) => {

      // Transform error to consistent format
      if (error.response?.data) {
        throw new ApiError(
          error.response.data.message || 'An error occurred',
          error.response.status,
          error.response.data.error_code,
          error.response.data.details
        );
      }

      throw new ApiError(
        error.message || 'Network error occurred',
        error.response?.status || 0
      );
    }
  );

  return client;
};

/**
 * Custom API Error class
 */
export class ApiError extends Error {
  public status: number;
  public code?: string;
  public details?: Record<string, any>;

  constructor(
    message: string,
    status: number,
    code?: string,
    details?: Record<string, any>
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// Create singleton instance
const apiClient = createApiClient();

/**
 * Upload a file to the server
 */
export const uploadFile = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<UploadResponse>(
    `${API_V1_PREFIX}/upload`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );

  return response.data;
};

/**
 * Upload a file with progress tracking
 */
export const uploadFileWithProgress = async (
  file: File,
  onProgress?: (progress: number) => void
): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<UploadResponse>(
    `${API_V1_PREFIX}/upload`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    }
  );

  return response.data;
};

/**
 * Check API health
 */
export const checkHealth = async (): Promise<HealthResponse> => {
  const response = await apiClient.get<HealthResponse>('/health');
  return response.data;
};

/**
 * Check upload service health
 */
export const checkUploadHealth = async (): Promise<HealthResponse> => {
  const response = await apiClient.get<HealthResponse>(`${API_V1_PREFIX}/upload/health`);
  return response.data;
};

/**
 * Submit project configuration and start optimization
 */
export const submitProjectConfig = async (config: ProjectConfig): Promise<{
  project_id: string;
  project_name: string;
  status: string;
  created_at: string;
  message: string;
}> => {
  const response = await apiClient.post(
    `${API_V1_PREFIX}/projects`,
    config
  );
  return response.data;
};

/**
 * Check project status
 */
export const checkProjectStatus = async (projectId: string): Promise<{
  project_id: string;
  status: string;
  progress: number;
  message: string;
  error?: string;
}> => {
  const response = await apiClient.get(
    `${API_V1_PREFIX}/projects/${projectId}/status`
  );
  return response.data;
};

/**
 * Get optimization results for a project
 */
export const getOptimizationResults = async (projectId: string): Promise<OptimizationResults> => {
  const response = await apiClient.get<OptimizationResults>(
    `${API_V1_PREFIX}/projects/${projectId}/results`
  );
  return response.data;
};

/**
 * Save edited layout
 */
export const saveLayout = async (
  projectId: string,
  alternativeId: string,
  assets: PlacedAsset[]
): Promise<{ success: boolean }> => {
  const response = await apiClient.put<{ success: boolean }>(
    `${API_V1_PREFIX}/projects/${projectId}/alternatives/${alternativeId}`,
    { assets }
  );
  return response.data;
};

/**
 * Re-optimize layout with new constraints
 */
export const reoptimizeLayout = async (
  projectId: string,
  config?: Partial<ProjectConfig>
): Promise<{
  project_id: string;
  project_name: string;
  status: string;
  created_at: string;
  message: string;
}> => {
  const response = await apiClient.post(
    `${API_V1_PREFIX}/projects/${projectId}/reoptimize`,
    config || {}
  );
  return response.data;
};

/**
 * Export layout in specified format
 */
export const exportLayout = async (
  projectId: string,
  alternativeId: string,
  format: ExportFormat
): Promise<Blob> => {
  const response = await apiClient.get(
    `${API_V1_PREFIX}/projects/${projectId}/alternatives/${alternativeId}/export/${format}`,
    {
      responseType: 'blob',
    }
  );
  return response.data;
};

/**
 * Get list of all projects
 */
export const getProjects = async (): Promise<Array<{ id: string; name: string; created_at: string }>> => {
  const response = await apiClient.get(`${API_V1_PREFIX}/projects`);
  return response.data;
};

/**
 * Delete a project
 */
export const deleteProject = async (projectId: string): Promise<{ success: boolean }> => {
  const response = await apiClient.delete<{ success: boolean }>(
    `${API_V1_PREFIX}/projects/${projectId}`
  );
  return response.data;
};

export default apiClient;
