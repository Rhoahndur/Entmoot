/**
 * Configuration Page - Project configuration panel
 */

import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Header } from '../components/Header';
import { AssetType } from '../types/config';
import type {
  AssetConfig,
  ConstraintConfig,
  RoadConfig,
  OptimizationWeights,
  ProjectConfig,
} from '../types/config';
import { submitProjectConfig, checkProjectStatus } from '../api/client';

export const ConfigPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const uploadId = searchParams.get('upload_id');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // State for configuration
  const [projectName, setProjectName] = useState('');
  const [assets, setAssets] = useState<AssetConfig[]>([
    {
      type: AssetType.BUILDINGS,
      quantity: 1,
      width: 50,
      length: 100,
      height: 15,
    },
  ]);

  const [constraints, setConstraints] = useState<ConstraintConfig>({
    setback_distance: 20,
    min_distance_between_assets: 10,
    exclusion_zones_enabled: true,
    respect_property_lines: true,
    respect_easements: true,
    wetland_buffer: 50,
    slope_limit: 15,
  });

  const [roadConfig, setRoadConfig] = useState<RoadConfig>({
    min_width: 24,
    max_grade: 8,
    turning_radius: 25,
    surface_type: 'paved',
    include_sidewalks: true,
  });

  const [weights, setWeights] = useState<OptimizationWeights>({
    cost: 40,
    buildable_area: 30,
    accessibility: 15,
    environmental_impact: 10,
    aesthetics: 5,
  });

  const handleAddAsset = () => {
    setAssets([
      ...assets,
      {
        type: AssetType.BUILDINGS,
        quantity: 1,
        width: 50,
        length: 100,
      },
    ]);
  };

  const handleRemoveAsset = (index: number) => {
    setAssets(assets.filter((_, i) => i !== index));
  };

  const handleAssetChange = (index: number, field: keyof AssetConfig, value: any) => {
    const newAssets = [...assets];
    newAssets[index] = { ...newAssets[index], [field]: value };
    setAssets(newAssets);
  };

  const handleConstraintChange = (field: keyof ConstraintConfig, value: any) => {
    setConstraints({ ...constraints, [field]: value });
  };

  const handleRoadConfigChange = (field: keyof RoadConfig, value: any) => {
    setRoadConfig({ ...roadConfig, [field]: value });
  };

  const handleWeightChange = (field: keyof OptimizationWeights, value: number) => {
    // Ensure weights sum to 100
    const totalWithoutCurrent = Object.entries(weights).reduce((sum, [key, val]) => {
      return key === field ? sum : sum + val;
    }, 0);

    const maxValue = 100 - totalWithoutCurrent;
    const clampedValue = Math.min(value, maxValue);

    setWeights({ ...weights, [field]: clampedValue });
  };

  const handleSubmit = async () => {
    if (!uploadId) {
      setError('No upload ID found. Please upload a file first.');
      return;
    }

    const config: ProjectConfig = {
      project_name: projectName,
      upload_id: uploadId,
      assets,
      constraints,
      road_design: roadConfig,
      optimization_weights: weights,
    };

    try {
      setIsSubmitting(true);
      setError(null);

      console.log('Submitting project configuration...', config);
      const response = await submitProjectConfig(config);

      console.log('Project created:', response);

      // Navigate to results page with project ID
      navigate(`/results?project_id=${response.project_id}`);
    } catch (err: any) {
      console.error('Error submitting configuration:', err);
      setError(err.message || 'Failed to submit configuration. Please try again.');
      setIsSubmitting(false);
    }
  };

  const totalWeight = Object.values(weights).reduce((sum, val) => sum + val, 0);

  return (
    <div className="min-h-screen bg-gray-100">
      <Header subtitle="Configure your site layout" />

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Upload ID Display */}
        {uploadId && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-sm text-green-800">
              <span className="font-medium">Upload ID:</span> {uploadId}
            </p>
          </div>
        )}

        {/* Project Name */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Project Information</h2>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Project Name
            </label>
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter project name"
            />
          </div>
        </div>

        {/* Assets Configuration */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Assets</h2>
            <button
              onClick={handleAddAsset}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm"
            >
              + Add Asset
            </button>
          </div>

          <div className="space-y-4">
            {assets.map((asset, index) => (
              <div key={index} className="border border-gray-200 rounded-lg p-4">
                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-sm font-medium text-gray-700">Asset {index + 1}</h3>
                  {assets.length > 1 && (
                    <button
                      onClick={() => handleRemoveAsset(index)}
                      className="text-red-600 hover:text-red-800 text-sm"
                    >
                      Remove
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
                    <select
                      value={asset.type}
                      onChange={(e) =>
                        handleAssetChange(index, 'type', e.target.value as AssetType)
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {Object.values(AssetType).map((type) => (
                        <option key={type} value={type}>
                          {type.replace('_', ' ')}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Quantity
                    </label>
                    <input
                      type="number"
                      value={asset.quantity}
                      onChange={(e) =>
                        handleAssetChange(index, 'quantity', parseInt(e.target.value) || 1)
                      }
                      min="1"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Width (ft)
                    </label>
                    <input
                      type="number"
                      value={asset.width}
                      onChange={(e) =>
                        handleAssetChange(index, 'width', parseFloat(e.target.value) || 0)
                      }
                      min="1"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Length (ft)
                    </label>
                    <input
                      type="number"
                      value={asset.length}
                      onChange={(e) =>
                        handleAssetChange(index, 'length', parseFloat(e.target.value) || 0)
                      }
                      min="1"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  {asset.height !== undefined && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Height (ft)
                      </label>
                      <input
                        type="number"
                        value={asset.height}
                        onChange={(e) =>
                          handleAssetChange(index, 'height', parseFloat(e.target.value) || 0)
                        }
                        min="1"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Constraints Configuration */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Constraints</h2>

          <div className="space-y-6">
            {/* Distance Constraints */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Setback Distance (ft): {constraints.setback_distance}
              </label>
              <input
                type="range"
                min="0"
                max="100"
                value={constraints.setback_distance}
                onChange={(e) =>
                  handleConstraintChange('setback_distance', parseInt(e.target.value))
                }
                className="w-full"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Min Distance Between Assets (ft): {constraints.min_distance_between_assets}
              </label>
              <input
                type="range"
                min="0"
                max="50"
                value={constraints.min_distance_between_assets}
                onChange={(e) =>
                  handleConstraintChange('min_distance_between_assets', parseInt(e.target.value))
                }
                className="w-full"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Wetland Buffer (ft): {constraints.wetland_buffer}
              </label>
              <input
                type="range"
                min="0"
                max="200"
                value={constraints.wetland_buffer}
                onChange={(e) =>
                  handleConstraintChange('wetland_buffer', parseInt(e.target.value))
                }
                className="w-full"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Maximum Slope (%): {constraints.slope_limit}
              </label>
              <input
                type="range"
                min="0"
                max="30"
                value={constraints.slope_limit}
                onChange={(e) => handleConstraintChange('slope_limit', parseInt(e.target.value))}
                className="w-full"
              />
            </div>

            {/* Boolean Constraints */}
            <div className="space-y-3">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={constraints.exclusion_zones_enabled}
                  onChange={(e) =>
                    handleConstraintChange('exclusion_zones_enabled', e.target.checked)
                  }
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">Enable Exclusion Zones</span>
              </label>

              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={constraints.respect_property_lines}
                  onChange={(e) =>
                    handleConstraintChange('respect_property_lines', e.target.checked)
                  }
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">Respect Property Lines</span>
              </label>

              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={constraints.respect_easements}
                  onChange={(e) => handleConstraintChange('respect_easements', e.target.checked)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">Respect Easements</span>
              </label>
            </div>
          </div>
        </div>

        {/* Road Design */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Road Design</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Min Width (ft)
              </label>
              <input
                type="number"
                value={roadConfig.min_width}
                onChange={(e) =>
                  handleRoadConfigChange('min_width', parseFloat(e.target.value) || 0)
                }
                min="10"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Grade (%)
              </label>
              <input
                type="number"
                value={roadConfig.max_grade}
                onChange={(e) =>
                  handleRoadConfigChange('max_grade', parseFloat(e.target.value) || 0)
                }
                min="0"
                max="15"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Turning Radius (ft)
              </label>
              <input
                type="number"
                value={roadConfig.turning_radius}
                onChange={(e) =>
                  handleRoadConfigChange('turning_radius', parseFloat(e.target.value) || 0)
                }
                min="10"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Surface Type</label>
              <select
                value={roadConfig.surface_type}
                onChange={(e) =>
                  handleRoadConfigChange('surface_type', e.target.value as RoadConfig['surface_type'])
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="paved">Paved</option>
                <option value="gravel">Gravel</option>
                <option value="dirt">Dirt</option>
              </select>
            </div>

            <div className="col-span-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={roadConfig.include_sidewalks}
                  onChange={(e) => handleRoadConfigChange('include_sidewalks', e.target.checked)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">Include Sidewalks</span>
              </label>
            </div>
          </div>
        </div>

        {/* Optimization Weights */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Optimization Weights
            <span
              className={`ml-3 text-sm ${totalWeight === 100 ? 'text-green-600' : 'text-red-600'}`}
            >
              (Total: {totalWeight}% {totalWeight !== 100 && '- must equal 100%'})
            </span>
          </h2>

          <div className="space-y-4">
            {Object.entries(weights).map(([key, value]) => (
              <div key={key}>
                <label className="block text-sm font-medium text-gray-700 mb-2 capitalize">
                  {key.replace('_', ' ')}: {value}%
                </label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={value}
                  onChange={(e) =>
                    handleWeightChange(key as keyof OptimizationWeights, parseInt(e.target.value))
                  }
                  className="w-full"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
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
                <h3 className="text-sm font-medium text-red-800">Error</h3>
                <p className="mt-1 text-sm text-red-700">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Submit Button */}
        <div className="flex justify-end space-x-3">
          <button
            type="button"
            className="px-6 py-3 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
            disabled={isSubmitting}
          >
            Save Draft
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!projectName || totalWeight !== 100 || isSubmitting}
            className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
          >
            {isSubmitting ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                Generating...
              </>
            ) : (
              'Generate Layout'
            )}
          </button>
        </div>
      </main>
    </div>
  );
};
