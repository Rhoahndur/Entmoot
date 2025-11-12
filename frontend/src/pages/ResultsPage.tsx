/**
 * ResultsPage - Main page for displaying and editing optimization results
 * Integrates MapViewer, ResultsDashboard, and LayoutEditor
 */

import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Header } from '../components/Header';
import { MapViewer } from '../components/MapViewer';
import { ResultsDashboard } from '../components/ResultsDashboard';
import { LayoutEditor } from '../components/LayoutEditor';
import { exportLayout } from '../utils/export';
import { checkConstraintViolations, recalculateAssetPolygon } from '../utils/constraintChecker';
import { getOptimizationResults, checkProjectStatus, reoptimizeLayout, saveLayout } from '../api/client';
import type {
  OptimizationResults,
  PlacedAsset,
  LayerVisibility,
  LayerType,
  ExportFormat,
  EditOperation,
  Coordinate,
  ConstraintViolation,
} from '../types/results';

export const ResultsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const projectId = searchParams.get('project_id');

  // State
  const [results, setResults] = useState<OptimizationResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAlternativeId, setSelectedAlternativeId] = useState<string | undefined>();
  const [selectedAssetId, setSelectedAssetId] = useState<string | undefined>();
  const [editMode, setEditMode] = useState(false);
  const [externalMoveOperation, setExternalMoveOperation] = useState<EditOperation | null>(null);
  const [localViolations, setLocalViolations] = useState<ConstraintViolation[]>([]);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [layerVisibility, setLayerVisibility] = useState<LayerVisibility>({
    base_map: true,
    terrain: true,
    property_boundary: true,
    assets: true,
    roads: true,
    constraints: true,
    buildable_areas: true,
    earthwork: false,
  });

  // Fetch results from API - poll status first, then fetch results
  useEffect(() => {
    const fetchResults = async () => {
      if (!projectId) {
        setError('No project ID provided');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        // Poll project status until completion
        let status = 'processing';
        let attempts = 0;
        const maxAttempts = 120; // 2 minutes max (120 * 1s)

        while (status !== 'completed' && status !== 'failed' && attempts < maxAttempts) {
          const statusData = await checkProjectStatus(projectId);
          status = statusData.status;

          if (status === 'failed') {
            throw new Error(statusData.error || 'Optimization failed');
          }

          if (status !== 'completed') {
            // Wait 1 second before next poll
            await new Promise(resolve => setTimeout(resolve, 1000));
            attempts++;
          }
        }

        if (attempts >= maxAttempts) {
          throw new Error('Optimization timed out. Please try again.');
        }

        // Fetch final results
        const data = await getOptimizationResults(projectId);

        setResults(data);
        setSelectedAlternativeId(data.alternatives[0]?.id);
        setLoading(false);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load results';
        // Check if it's a network error (server restart, etc.)
        const isNetworkError = errorMessage.includes('Network') ||
                              errorMessage.includes('timeout') ||
                              errorMessage.includes('ECONNREFUSED');

        setError(isNetworkError
          ? 'Server connection lost. The server may be restarting.'
          : errorMessage
        );
        setLoading(false);
      }
    };

    fetchResults();
  }, [projectId]);

  // Retry function
  const handleRetry = () => {
    setError(null);
    setLoading(true);
    // Trigger refetch by updating state
    window.location.reload();
  };

  // Get current alternative
  const currentAlternative = results?.alternatives.find(
    (alt) => alt.id === selectedAlternativeId
  );

  // Hide roads when entering edit mode (they're outdated after moving assets)
  useEffect(() => {
    if (editMode) {
      // Hide roads in edit mode
      setLayerVisibility(prev => ({ ...prev, roads: false }));
    }
  }, [editMode]);

  // Helper function to recalculate violations
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const recalculateViolations = () => {
    if (!currentAlternative || !results) {
      setLocalViolations([]);
      return;
    }

    // Ensure all asset polygons are synced with their positions
    const assetsWithUpdatedPolygons = currentAlternative.assets.map(asset => ({
      ...asset,
      polygon: recalculateAssetPolygon(asset)
    }));

    const violations = checkConstraintViolations(
      assetsWithUpdatedPolygons,
      currentAlternative.constraint_zones,
      results.property_boundary
    );
    setLocalViolations(violations);
  };

  // Debounced violation check ref
  const violationCheckTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize violations on first load or alternative switch
  useEffect(() => {
    recalculateViolations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAlternativeId]); // Only when alternative ID changes

  // Handle asset changes from editor
  const handleAssetsChange = (updatedAssets: PlacedAsset[]) => {
    if (!results || !currentAlternative) return;

    const updatedAlternative = {
      ...currentAlternative,
      assets: updatedAssets,
      // Keep road network data - it's just hidden visually during edit mode
    };

    setResults({
      ...results,
      alternatives: results.alternatives.map((alt) =>
        alt.id === selectedAlternativeId ? updatedAlternative : alt
      ),
    });

    // Debounce violation check - wait 300ms after last change
    if (violationCheckTimeoutRef.current) {
      clearTimeout(violationCheckTimeoutRef.current);
    }
    violationCheckTimeoutRef.current = setTimeout(() => {
      recalculateViolations();
    }, 300);
  };

  // Handle asset move from drag
  const handleAssetMove = (assetId: string, newPosition: Coordinate) => {
    if (!results || !currentAlternative) return;

    // Find the asset and capture its current position before moving
    const asset = currentAlternative.assets.find((a) => a.id === assetId);
    if (!asset) return;

    const beforePosition = asset.position;

    // Update assets with new position AND recalculate polygon
    const updatedAssets = currentAlternative.assets.map((asset) => {
      if (asset.id === assetId) {
        const updatedAsset = { ...asset, position: newPosition };
        // Recalculate polygon based on new position
        updatedAsset.polygon = recalculateAssetPolygon(updatedAsset);
        return updatedAsset;
      }
      return asset;
    });

    handleAssetsChange(updatedAssets);

    // Create edit operation for tracking in history
    setExternalMoveOperation({
      type: 'move_asset',
      assetId,
      before: { position: beforePosition },
      after: { position: newPosition },
      timestamp: Date.now(),
    });

    // Debounce violation check - wait 300ms after last change
    if (violationCheckTimeoutRef.current) {
      clearTimeout(violationCheckTimeoutRef.current);
    }
    violationCheckTimeoutRef.current = setTimeout(() => {
      recalculateViolations();
    }, 300);
  };

  // Handle layer visibility toggle
  const toggleLayer = (layer: LayerType) => {
    setLayerVisibility({
      ...layerVisibility,
      [layer]: !layerVisibility[layer],
    });
  };

  // Handle export
  const handleExport = async (format: ExportFormat) => {
    if (!currentAlternative || !results || !selectedAlternativeId) return;

    try {
      await exportLayout(format, results, selectedAlternativeId);
    } catch (error) {
      console.error('Export failed:', error);
      alert(`Failed to export: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Handle save
  const handleSave = async () => {
    if (!results || !currentAlternative || !projectId || !selectedAlternativeId) return;

    try {
      // Save the updated assets to the backend
      await saveLayout(projectId, selectedAlternativeId, currentAlternative.assets);

      // Clear any pending debounced checks
      if (violationCheckTimeoutRef.current) {
        clearTimeout(violationCheckTimeoutRef.current);
      }

      // Immediately recalculate violations
      recalculateViolations();

      // Reset unsaved changes flag after successful save
      setHasUnsavedChanges(false);

      // No alert needed - the save is successful and persisted
    } catch (error) {
      console.error('Save failed:', error);
      alert(`Failed to save changes: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Handle edit mode toggle with unsaved changes check
  const handleEditModeToggle = async () => {
    if (editMode) {
      // Exiting edit mode - check for unsaved changes
      if (hasUnsavedChanges) {
        await handleSave();
      } else {
        // If no unsaved changes, still recalculate violations in case of debounced changes
        if (violationCheckTimeoutRef.current) {
          clearTimeout(violationCheckTimeoutRef.current);
        }
        recalculateViolations();
      }
      // Clear selected asset when exiting edit mode
      setSelectedAssetId(undefined);
    }
    setEditMode(!editMode);
  };

  // Handle re-optimize
  const handleReoptimize = async () => {
    if (!projectId) return;

    const confirmed = window.confirm(
      'This will run a new optimization with the current configuration. The process may take a moment. Continue?'
    );

    if (!confirmed) return;

    try {
      setLoading(true);
      setError(null);

      // Start re-optimization
      await reoptimizeLayout(projectId);

      // Poll project status until completion
      let status = 'processing';
      let attempts = 0;
      const maxAttempts = 120; // 2 minutes max (120 * 1s)

      while (status !== 'completed' && status !== 'failed' && attempts < maxAttempts) {
        const statusData = await checkProjectStatus(projectId);
        status = statusData.status;

        if (status === 'failed') {
          throw new Error(statusData.error || 'Re-optimization failed');
        }

        if (status !== 'completed') {
          // Wait 1 second before next poll
          await new Promise(resolve => setTimeout(resolve, 1000));
          attempts++;
        }
      }

      if (attempts >= maxAttempts) {
        throw new Error('Re-optimization timed out. Please try again.');
      }

      // Fetch updated results
      const data = await getOptimizationResults(projectId);
      setResults(data);
      setSelectedAlternativeId(data.alternatives[0]?.id);
      setEditMode(false); // Exit edit mode to show new results
      setLayerVisibility(prev => ({ ...prev, roads: true })); // Show new roads
      setLoading(false);

      // Show success message
      alert('Re-optimization completed successfully!');
    } catch (err) {
      console.error('Re-optimization failed:', err);
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(`Re-optimization failed: ${errorMessage}`);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="bg-white rounded-lg p-8 shadow-md">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading results...</p>
        </div>
      </div>
    );
  }

  if (error || !results || !currentAlternative) {
    const isServerError = error?.includes('Server connection lost') ||
                          error?.includes('Network') ||
                          error?.includes('timeout');

    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="bg-white rounded-lg p-8 shadow-md max-w-md">
          <div className="text-red-600 text-5xl mb-4">⚠️</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Error Loading Results</h2>
          <p className="text-gray-600 mb-4">{error || 'No results found'}</p>
          <div className="flex gap-3">
            {isServerError && projectId && (
              <button
                onClick={handleRetry}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm font-medium"
              >
                Retry
              </button>
            )}
            <button
              onClick={() => (window.location.href = '/')}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
            >
              Go Home
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Header
        title="Results"
        subtitle={results.project_name}
        actions={
          <>
            <button
              onClick={handleEditModeToggle}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                editMode
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {editMode ? 'Exit Edit Mode' : 'Edit Layout'}
            </button>
          </>
        }
      />

      {/* Main Content */}
      <main className="max-w-full px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-12 gap-6">
          {/* Left Column - Map */}
          <div className="col-span-12 lg:col-span-8">
            <div className="bg-white rounded-lg shadow-md p-4">
              <div className="h-[600px] relative">
                <MapViewer
                  bounds={results.bounds}
                  propertyBoundary={results.property_boundary}
                  assets={currentAlternative.assets}
                  roadNetwork={currentAlternative.road_network}
                  constraintZones={currentAlternative.constraint_zones}
                  buildableAreas={currentAlternative.buildable_areas}
                  layerVisibility={layerVisibility}
                  onAssetClick={(asset) => setSelectedAssetId(asset.id)}
                  onAssetMove={handleAssetMove}
                  editable={editMode}
                  selectedAssetId={selectedAssetId}
                  violatingAssetIds={localViolations.map(v => v.asset_id)}
                />
              </div>

              {/* Layer Controls */}
              <div className="mt-4 border-t border-gray-200 pt-4">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Map Layers</h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(layerVisibility).map(([layer, visible]) => (
                    <button
                      key={layer}
                      onClick={() => toggleLayer(layer as LayerType)}
                      className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                        visible
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
                      }`}
                    >
                      {layer.replace('_', ' ')}
                    </button>
                  ))}
                </div>
                {editMode && (
                  <div className="mt-2 text-xs text-orange-600 bg-orange-50 border border-orange-200 rounded p-2">
                    ℹ️ Roads are from the original layout and won't update as you move assets. Toggle them on to see original paths, or re-optimize to generate new roads.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Column - Editor or Dashboard */}
          <div className="col-span-12 lg:col-span-4">
            {editMode ? (
              <LayoutEditor
                assets={currentAlternative.assets}
                violations={localViolations}
                onAssetsChange={handleAssetsChange}
                onSave={handleSave}
                onReoptimize={handleReoptimize}
                selectedAssetId={selectedAssetId}
                onAssetSelect={setSelectedAssetId}
                externalMoveOperation={externalMoveOperation}
                onUnsavedChangesChange={setHasUnsavedChanges}
              />
            ) : (
              <div className="space-y-4">
                {/* Quick Stats */}
                <div className="bg-white rounded-lg shadow-md p-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">Quick Stats</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-blue-50 rounded p-2">
                      <p className="text-xs text-blue-600">Score</p>
                      <p className="text-lg font-bold text-blue-900">
                        {currentAlternative.metrics.optimization_score.toFixed(1)}
                      </p>
                    </div>
                    <div className="bg-green-50 rounded p-2">
                      <p className="text-xs text-green-600">Assets</p>
                      <p className="text-lg font-bold text-green-900">
                        {currentAlternative.metrics.assets_placed}
                      </p>
                    </div>
                    <div className="bg-purple-50 rounded p-2">
                      <p className="text-xs text-purple-600">Cost</p>
                      <p className="text-lg font-bold text-purple-900">
                        ${(currentAlternative.metrics.estimated_cost.total / 1000000).toFixed(2)}M
                      </p>
                    </div>
                    <div
                      className={`rounded p-2 ${
                        localViolations.length === 0
                          ? 'bg-green-50'
                          : 'bg-red-50'
                      }`}
                    >
                      <p
                        className={`text-xs ${
                          localViolations.length === 0
                            ? 'text-green-600'
                            : 'text-red-600'
                        }`}
                      >
                        Violations
                      </p>
                      <p
                        className={`text-lg font-bold ${
                          localViolations.length === 0
                            ? 'text-green-900'
                            : 'text-red-900'
                        }`}
                      >
                        {localViolations.length}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Violations Panel - Always Visible */}
                {localViolations.length > 0 && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4 mt-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold text-red-900">
                        ⚠️ Constraint Violations ({localViolations.length})
                      </h3>
                      {!editMode && (
                        <button
                          onClick={() => setEditMode(true)}
                          className="text-xs bg-red-600 text-white px-3 py-1 rounded-md hover:bg-red-700"
                        >
                          Fix in Editor
                        </button>
                      )}
                    </div>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {localViolations.map((violation, index) => {
                        const violatingAsset = currentAlternative.assets.find(a => a.id === violation.asset_id);
                        return (
                          <div
                            key={index}
                            onClick={() => {
                              setSelectedAssetId(violation.asset_id);
                              if (!editMode) setEditMode(true);
                            }}
                            className="bg-white p-3 rounded border border-red-200 cursor-pointer hover:border-red-400 transition-colors"
                          >
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                  <span
                                    className={`inline-block w-2 h-2 rounded-full ${
                                      violation.severity === 'error' ? 'bg-red-600' : 'bg-yellow-600'
                                    }`}
                                  />
                                  <span className="text-xs font-medium text-red-900">
                                    {violatingAsset?.type.replace('_', ' ').toUpperCase() || 'Asset'}
                                  </span>
                                  <span className="text-xs text-gray-500">
                                    ({violation.asset_id.substring(0, 8)})
                                  </span>
                                </div>
                                <p className="text-xs text-red-700 ml-4">{violation.message}</p>
                              </div>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedAssetId(violation.asset_id);
                                  setEditMode(true);
                                }}
                                className="text-xs text-red-600 hover:text-red-800 font-medium"
                              >
                                Select →
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <p className="text-xs text-red-600 mt-3 italic">
                      Click on a violation to select and fix the asset in the editor
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Full Width Dashboard */}
          <div className="col-span-12">
            <ResultsDashboard
              metrics={currentAlternative.metrics}
              assets={currentAlternative.assets}
              roadNetwork={currentAlternative.road_network}
              alternatives={results.alternatives}
              selectedAlternativeId={selectedAlternativeId}
              onAlternativeSelect={setSelectedAlternativeId}
              onExport={handleExport}
              onReoptimize={handleReoptimize}
            />
          </div>
        </div>
      </main>
    </div>
  );
};
