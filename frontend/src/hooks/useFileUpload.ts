/**
 * Custom hook for file upload functionality
 */

import { useState, useCallback } from 'react';
import { uploadFileWithProgress, ApiError } from '../api/client';
import type { UploadResponse } from '../types/api';
import { validateFile } from '../utils/validators';

export interface UploadState {
  uploading: boolean;
  progress: number;
  error: string | null;
  success: boolean;
  uploadResponse: UploadResponse | null;
}

export const useFileUpload = () => {
  const [state, setState] = useState<UploadState>({
    uploading: false,
    progress: 0,
    error: null,
    success: false,
    uploadResponse: null,
  });

  const resetState = useCallback(() => {
    setState({
      uploading: false,
      progress: 0,
      error: null,
      success: false,
      uploadResponse: null,
    });
  }, []);

  const uploadFile = useCallback(async (file: File) => {
    // Reset state
    setState({
      uploading: true,
      progress: 0,
      error: null,
      success: false,
      uploadResponse: null,
    });

    // Validate file
    const validationError = validateFile(file);
    if (validationError) {
      setState({
        uploading: false,
        progress: 0,
        error: validationError,
        success: false,
        uploadResponse: null,
      });
      return null;
    }

    try {
      // Upload file with progress tracking
      const response = await uploadFileWithProgress(file, (progress) => {
        setState((prev) => ({
          ...prev,
          progress,
        }));
      });

      setState({
        uploading: false,
        progress: 100,
        error: null,
        success: true,
        uploadResponse: response,
      });

      return response;
    } catch (error) {
      let errorMessage = 'Failed to upload file';

      if (error instanceof ApiError) {
        errorMessage = error.message;
        if (error.details) {
          errorMessage += `: ${JSON.stringify(error.details)}`;
        }
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }

      setState({
        uploading: false,
        progress: 0,
        error: errorMessage,
        success: false,
        uploadResponse: null,
      });

      return null;
    }
  }, []);

  return {
    ...state,
    uploadFile,
    resetState,
  };
};
