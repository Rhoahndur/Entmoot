/**
 * Upload Page - File upload wizard
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../components/Header';
import { FileDropzone, FilePreview, UploadProgress } from '../components/FileDropzone';
import { useFileUpload } from '../hooks/useFileUpload';

export const UploadPage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const { uploading, progress, error, success, uploadResponse, uploadFile, resetState } =
    useFileUpload();

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    resetState();
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    resetState();
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    const response = await uploadFile(selectedFile);

    if (response) {
      // Wait a moment to show success, then navigate to config page
      setTimeout(() => {
        navigate(`/config?upload_id=${response.upload_id}`);
      }, 1500);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <Header subtitle="AI-driven site layout automation for real estate due diligence" />

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Step Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-center space-x-4">
            <div className="flex items-center">
              <div className="flex items-center justify-center w-10 h-10 rounded-full bg-blue-600 text-white font-semibold">
                1
              </div>
              <span className="ml-2 text-sm font-medium text-gray-900">Upload File</span>
            </div>

            <div className="w-16 h-1 bg-gray-300"></div>

            <div className="flex items-center">
              <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gray-300 text-gray-600 font-semibold">
                2
              </div>
              <span className="ml-2 text-sm font-medium text-gray-500">Configure</span>
            </div>

            <div className="w-16 h-1 bg-gray-300"></div>

            <div className="flex items-center">
              <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gray-300 text-gray-600 font-semibold">
                3
              </div>
              <span className="ml-2 text-sm font-medium text-gray-500">Generate</span>
            </div>
          </div>
        </div>

        {/* Upload Section */}
        <div className="bg-white rounded-lg shadow-md p-8">
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">Upload Site Boundary</h2>
          <p className="text-gray-600 mb-6">
            Upload a geospatial file (KMZ, KML, GeoJSON, or GeoTIFF) containing your property
            boundary.
          </p>

          {/* Dropzone */}
          {!selectedFile && !success && (
            <FileDropzone onFileSelect={handleFileSelect} disabled={uploading} />
          )}

          {/* File Preview */}
          {selectedFile && !uploading && !success && (
            <FilePreview file={selectedFile} onRemove={handleRemoveFile} />
          )}

          {/* Upload Progress */}
          {uploading && selectedFile && (
            <UploadProgress progress={progress} filename={selectedFile.name} />
          )}

          {/* Success Message */}
          {success && uploadResponse && (
            <div className="p-6 bg-green-50 border-2 border-green-400 rounded-lg shadow-lg">
              <div className="flex items-start space-x-4">
                <svg
                  className="w-12 h-12 text-green-600 flex-shrink-0"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-green-800 mb-1">Upload Successful!</h3>
                  <p className="text-sm text-green-700 mb-2">
                    {uploadResponse.message}
                  </p>
                  <div className="flex items-center space-x-2 mt-3">
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-green-300 border-t-green-600"></div>
                    <p className="text-sm font-medium text-green-800">
                      Redirecting to configuration...
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
              <div className="flex items-start">
                <svg
                  className="w-5 h-5 text-red-600 mt-0.5"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 9.586 8.707 8.293z"
                    clipRule="evenodd"
                  />
                </svg>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-red-800">Upload Failed</h3>
                  <p className="mt-1 text-sm text-red-700">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          {selectedFile && !uploading && !success && (
            <div className="mt-6 flex justify-end space-x-3">
              <button
                type="button"
                onClick={handleRemoveFile}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleUpload}
                className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                Upload & Continue
              </button>
            </div>
          )}
        </div>

        {/* Help Section */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-sm font-medium text-blue-900 mb-2">Need Help?</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• KMZ/KML files are commonly exported from Google Earth</li>
            <li>• GeoJSON files can be created from most GIS software</li>
            <li>• GeoTIFF files should contain georeferenced boundary data</li>
            <li>• Maximum file size is 50MB</li>
          </ul>
        </div>
      </main>
    </div>
  );
};
