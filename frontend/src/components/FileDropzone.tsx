/**
 * File Dropzone component with drag-and-drop support
 */

import React, { useCallback, useState } from 'react';
import { formatFileSize, getFileIcon, validateFile } from '../utils/validators';

interface FileDropzoneProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
}

export const FileDropzone: React.FC<FileDropzoneProps> = ({ onFileSelect, disabled = false }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleDragEnter = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled) {
        setIsDragging(true);
      }
    },
    [disabled]
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      if (disabled) return;

      const files = Array.from(e.dataTransfer.files);
      if (files.length === 0) return;

      const file = files[0];
      const error = validateFile(file);

      if (error) {
        setValidationError(error);
        return;
      }

      setValidationError(null);
      onFileSelect(file);
    },
    [disabled, onFileSelect]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files || files.length === 0) return;

      const file = files[0];
      const error = validateFile(file);

      if (error) {
        setValidationError(error);
        return;
      }

      setValidationError(null);
      onFileSelect(file);
      e.target.value = ''; // Reset input
    },
    [onFileSelect]
  );

  return (
    <div className="w-full">
      <div
        className={`
          relative border-2 border-dashed rounded-lg p-12 text-center transition-colors
          ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:border-blue-400 hover:bg-blue-50'}
        `}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => !disabled && document.getElementById('file-input')?.click()}
      >
        <input
          id="file-input"
          type="file"
          className="hidden"
          onChange={handleFileInput}
          disabled={disabled}
          accept=".kmz,.kml,.geojson,.tif,.tiff"
        />

        <div className="flex flex-col items-center">
          <svg
            className="w-16 h-16 text-gray-400 mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>

          <p className="text-lg font-medium text-gray-700 mb-2">
            {isDragging ? 'Drop file here' : 'Drag and drop file here'}
          </p>

          <p className="text-sm text-gray-500 mb-4">or</p>

          <button
            type="button"
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={disabled}
            onClick={(e) => {
              e.stopPropagation();
              document.getElementById('file-input')?.click();
            }}
          >
            Browse Files
          </button>

          <p className="text-xs text-gray-400 mt-4">
            Supported formats: KMZ, KML, GeoJSON, GeoTIFF (max 50MB)
          </p>
        </div>
      </div>

      {validationError && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-600">{validationError}</p>
        </div>
      )}
    </div>
  );
};

interface FilePreviewProps {
  file: File;
  onRemove: () => void;
}

export const FilePreview: React.FC<FilePreviewProps> = ({ file, onRemove }) => {
  return (
    <div className="mt-4 p-4 bg-white border border-gray-200 rounded-lg shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <span className="text-3xl">{getFileIcon(file.name)}</span>
          <div>
            <p className="text-sm font-medium text-gray-900">{file.name}</p>
            <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
          </div>
        </div>

        <button
          type="button"
          onClick={onRemove}
          className="p-2 text-gray-400 hover:text-red-600 transition-colors"
          aria-label="Remove file"
        >
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </div>
    </div>
  );
};

interface UploadProgressProps {
  progress: number;
  filename: string;
}

export const UploadProgress: React.FC<UploadProgressProps> = ({ progress, filename }) => {
  return (
    <div className="mt-4 p-6 bg-blue-50 border-2 border-blue-400 rounded-lg shadow-lg">
      <div className="flex items-start space-x-4">
        {/* Animated Spinner */}
        <div className="flex-shrink-0">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-200 border-t-blue-600"></div>
        </div>

        {/* Upload Info */}
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-blue-900 mb-1">
            Uploading File...
          </h3>
          <p className="text-sm text-blue-700 mb-3">{filename}</p>

          {/* Progress Bar */}
          <div className="w-full bg-blue-200 rounded-full h-3 mb-2">
            <div
              className="bg-blue-600 h-3 rounded-full transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-blue-800">{progress}%</span>
            <span className="text-xs text-blue-600">Please wait...</span>
          </div>
        </div>
      </div>
    </div>
  );
};
