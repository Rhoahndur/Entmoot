/**
 * LayoutEditor Component - Interactive editor for modifying asset placements
 * Supports drag-and-drop, rotation, deletion, and undo/redo
 */

import React, { useState, useEffect } from 'react';
import type {
  PlacedAsset,
  ConstraintViolation,
  EditOperation,
} from '../types/results';

interface LayoutEditorProps {
  assets: PlacedAsset[];
  violations: ConstraintViolation[];
  onAssetsChange: (assets: PlacedAsset[]) => void;
  onSave: () => void;
  onReoptimize: () => void;
  selectedAssetId?: string;
  onAssetSelect: (assetId: string | undefined) => void;
  externalMoveOperation?: EditOperation | null;
  onUnsavedChangesChange?: (hasChanges: boolean) => void;
}

export const LayoutEditor: React.FC<LayoutEditorProps> = ({
  assets,
  violations,
  onAssetsChange,
  onSave,
  onReoptimize,
  selectedAssetId,
  onAssetSelect,
  externalMoveOperation,
  onUnsavedChangesChange,
}) => {
  const [editHistory, setEditHistory] = useState<EditOperation[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Refs for smooth slider rotation (no React re-renders during drag)
  const sliderRotationRef = React.useRef<number | null>(null);
  const rotationFrameRef = React.useRef<number | null>(null);
  const startRotationRef = React.useRef<number | null>(null);

  const selectedAsset = assets.find((a) => a.id === selectedAssetId);

  // Track changes for unsaved indicator
  useEffect(() => {
    if (editHistory.length > 0) {
      setHasUnsavedChanges(true);
    }
  }, [editHistory]);

  // Notify parent of unsaved changes
  useEffect(() => {
    onUnsavedChangesChange?.(hasUnsavedChanges);
  }, [hasUnsavedChanges, onUnsavedChangesChange]);

  // Track external move operations
  useEffect(() => {
    if (externalMoveOperation) {
      // Remove any operations after current index (for redo)
      const newHistory = editHistory.slice(0, historyIndex + 1);
      newHistory.push(externalMoveOperation);
      setEditHistory(newHistory);
      setHistoryIndex(newHistory.length - 1);
    }
  }, [externalMoveOperation]);

  // Cleanup animation frame on unmount
  useEffect(() => {
    return () => {
      if (rotationFrameRef.current !== null) {
        cancelAnimationFrame(rotationFrameRef.current);
      }
    };
  }, []);

  // Throttled slider rotation update (runs at most once per frame)
  const applySliderRotation = React.useCallback(() => {
    if (sliderRotationRef.current === null || !selectedAsset) {
      rotationFrameRef.current = null;
      return;
    }

    const targetRotation = sliderRotationRef.current;
    const updatedAssets = assets.map((asset) =>
      asset.id === selectedAssetId
        ? { ...asset, rotation: targetRotation }
        : asset
    );

    onAssetsChange(updatedAssets);
    rotationFrameRef.current = null;
  }, [assets, selectedAssetId, selectedAsset, onAssetsChange]);

  // Add operation to history
  const addToHistory = (operation: EditOperation) => {
    // Remove any operations after current index (for redo)
    const newHistory = editHistory.slice(0, historyIndex + 1);
    newHistory.push(operation);
    setEditHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
  };

  // Undo last operation
  const handleUndo = () => {
    if (historyIndex < 0) return;

    const operation = editHistory[historyIndex];
    const updatedAssets = [...assets];
    const assetIndex = updatedAssets.findIndex((a) => a.id === operation.assetId);

    if (assetIndex === -1) return;

    switch (operation.type) {
      case 'move_asset':
      case 'rotate_asset':
        if (operation.before) {
          updatedAssets[assetIndex] = {
            ...updatedAssets[assetIndex],
            ...operation.before,
          };
        }
        break;
      case 'delete_asset':
        // Re-add the deleted asset
        if (operation.before) {
          updatedAssets.push(operation.before as PlacedAsset);
        }
        break;
      case 'add_asset':
        // Remove the added asset
        updatedAssets.splice(assetIndex, 1);
        break;
    }

    onAssetsChange(updatedAssets);
    setHistoryIndex(historyIndex - 1);
  };

  // Redo last undone operation
  const handleRedo = () => {
    if (historyIndex >= editHistory.length - 1) return;

    const operation = editHistory[historyIndex + 1];
    const updatedAssets = [...assets];
    const assetIndex = updatedAssets.findIndex((a) => a.id === operation.assetId);

    switch (operation.type) {
      case 'move_asset':
      case 'rotate_asset':
        if (assetIndex !== -1 && operation.after) {
          updatedAssets[assetIndex] = {
            ...updatedAssets[assetIndex],
            ...operation.after,
          };
        }
        break;
      case 'delete_asset':
        if (assetIndex !== -1) {
          updatedAssets.splice(assetIndex, 1);
        }
        break;
      case 'add_asset':
        if (operation.after) {
          updatedAssets.push(operation.after as PlacedAsset);
        }
        break;
    }

    onAssetsChange(updatedAssets);
    setHistoryIndex(historyIndex + 1);
  };

  // Rotate selected asset - simple and immediate
  const handleRotate = (degrees: number) => {
    if (!selectedAsset) return;

    const newRotation = (selectedAsset.rotation + degrees) % 360;
    const normalizedRotation = newRotation < 0 ? newRotation + 360 : newRotation;

    const updatedAssets = assets.map((asset) =>
      asset.id === selectedAssetId
        ? { ...asset, rotation: normalizedRotation }
        : asset
    );

    addToHistory({
      type: 'rotate_asset',
      assetId: selectedAssetId!,
      before: { rotation: selectedAsset.rotation },
      after: { rotation: normalizedRotation },
      timestamp: Date.now(),
    });

    onAssetsChange(updatedAssets);
  };

  // Delete selected asset
  const handleDelete = () => {
    if (!selectedAsset) return;

    const updatedAssets = assets.filter((a) => a.id !== selectedAssetId);

    addToHistory({
      type: 'delete_asset',
      assetId: selectedAssetId!,
      before: { ...selectedAsset },
      timestamp: Date.now(),
    });

    onAssetsChange(updatedAssets);
    onAssetSelect(undefined);
  };

  // Note: Move functionality would be triggered by map drag in full implementation
  // Keeping this commented for future reference
  /*
  const handleMove = (newPosition: Coordinate) => {
    if (!selectedAsset) return;

    const updatedAssets = assets.map((asset) =>
      asset.id === selectedAssetId ? { ...asset, position: newPosition } : asset
    );

    addToHistory({
      type: 'move_asset',
      assetId: selectedAssetId!,
      before: { position: selectedAsset.position },
      after: { position: newPosition },
      timestamp: Date.now(),
    });

    onAssetsChange(updatedAssets);
  };
  */

  // Save changes
  const handleSave = () => {
    onSave();
    setHasUnsavedChanges(false);
    setEditHistory([]);
    setHistoryIndex(-1);
  };

  // Get violations for selected asset
  const assetViolations = selectedAsset
    ? violations.filter((v) => v.asset_id === selectedAsset.id)
    : [];

  const canUndo = historyIndex >= 0;
  const canRedo = historyIndex < editHistory.length - 1;

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 pb-3">
          <h3 className="text-lg font-semibold text-gray-900">Layout Editor</h3>
          {hasUnsavedChanges && (
            <span className="text-xs bg-orange-100 text-orange-800 px-2 py-1 rounded">
              Unsaved changes
            </span>
          )}
        </div>

        {/* Undo/Redo Controls */}
        <div className="flex items-center space-x-2">
          <button
            onClick={handleUndo}
            disabled={!canUndo}
            className="px-3 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed text-sm flex items-center space-x-1"
            title="Undo (Ctrl+Z)"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"
              />
            </svg>
            <span>Undo</span>
          </button>
          <button
            onClick={handleRedo}
            disabled={!canRedo}
            className="px-3 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed text-sm flex items-center space-x-1"
            title="Redo (Ctrl+Y)"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 10h-10a8 8 0 00-8 8v2m18-10l-6 6m6-6l-6-6"
              />
            </svg>
            <span>Redo</span>
          </button>
          <span className="text-xs text-gray-500 ml-2">
            {editHistory.length > 0 && `${historyIndex + 1}/${editHistory.length} operations`}
          </span>
        </div>

        {/* Selected Asset Controls */}
        {selectedAsset ? (
          <div className="border border-blue-200 rounded-lg p-4 bg-blue-50">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-medium text-blue-900">Selected Asset</h4>
              <button
                onClick={() => onAssetSelect(undefined)}
                className="text-blue-600 hover:text-blue-800 text-sm"
              >
                Deselect
              </button>
            </div>

            <div className="space-y-3">
              {/* Asset Info */}
              <div className="text-sm space-y-1">
                <p className="text-gray-700">
                  <span className="font-medium">Type:</span>{' '}
                  <span className="capitalize">{selectedAsset.type.replace('_', ' ')}</span>
                </p>
                <p className="text-gray-700">
                  <span className="font-medium">Size:</span> {selectedAsset.width.toFixed(1)}' ×{' '}
                  {selectedAsset.length.toFixed(1)}'
                  {selectedAsset.height && ` × ${selectedAsset.height.toFixed(1)}'`}
                </p>
                <p className="text-gray-700">
                  <span className="font-medium">Rotation:</span> {selectedAsset.rotation.toFixed(1)}°
                </p>
              </div>

              {/* Rotation Controls */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Rotation
                </label>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleRotate(-15)}
                    className="px-3 py-1 bg-white border border-gray-300 rounded-md hover:bg-gray-50 text-sm"
                  >
                    -15°
                  </button>
                  <button
                    onClick={() => handleRotate(-5)}
                    className="px-3 py-1 bg-white border border-gray-300 rounded-md hover:bg-gray-50 text-sm"
                  >
                    -5°
                  </button>
                  <input
                    type="range"
                    min="0"
                    max="360"
                    step="0.1"
                    value={selectedAsset.rotation}
                    onMouseDown={() => {
                      // Record starting rotation for history
                      startRotationRef.current = selectedAsset.rotation;
                    }}
                    onInput={(e) => {
                      // Update ref and schedule RAF update (throttled to 60fps)
                      const newRotation = parseFloat((e.target as HTMLInputElement).value);
                      sliderRotationRef.current = newRotation;

                      if (rotationFrameRef.current === null) {
                        rotationFrameRef.current = requestAnimationFrame(applySliderRotation);
                      }
                    }}
                    onMouseUp={() => {
                      // Commit the rotation change to history
                      if (startRotationRef.current !== null && selectedAsset) {
                        const finalRotation = selectedAsset.rotation;
                        if (startRotationRef.current !== finalRotation) {
                          addToHistory({
                            type: 'rotate_asset',
                            assetId: selectedAssetId!,
                            before: { rotation: startRotationRef.current },
                            after: { rotation: finalRotation },
                            timestamp: Date.now(),
                          });
                        }
                        startRotationRef.current = null;
                        sliderRotationRef.current = null;
                      }
                    }}
                    className="flex-1"
                  />
                  <button
                    onClick={() => handleRotate(5)}
                    className="px-3 py-1 bg-white border border-gray-300 rounded-md hover:bg-gray-50 text-sm"
                  >
                    +5°
                  </button>
                  <button
                    onClick={() => handleRotate(15)}
                    className="px-3 py-1 bg-white border border-gray-300 rounded-md hover:bg-gray-50 text-sm"
                  >
                    +15°
                  </button>
                </div>
              </div>

              {/* Delete Button */}
              <button
                onClick={handleDelete}
                className="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors text-sm"
              >
                Delete Asset
              </button>

              {/* Violations for this asset */}
              {assetViolations.length > 0 && (
                <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
                  <h5 className="text-sm font-medium text-red-900 mb-2">
                    Constraint Violations ({assetViolations.length})
                  </h5>
                  <ul className="space-y-1">
                    {assetViolations.map((violation, index) => (
                      <li key={index} className="text-xs text-red-700 flex items-start">
                        <span
                          className={`inline-block w-1.5 h-1.5 rounded-full mt-1 mr-2 ${
                            violation.severity === 'error' ? 'bg-red-600' : 'bg-yellow-600'
                          }`}
                        />
                        <span>{violation.message}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 text-center">
            <p className="text-sm text-gray-600">
              Click on an asset on the map to select and edit it
            </p>
          </div>
        )}

        {/* Overall Violations Summary */}
        {violations.length > 0 && !selectedAsset && (
          <div className="border border-orange-200 rounded-lg p-4 bg-orange-50">
            <h4 className="font-medium text-orange-900 mb-2">
              Layout Violations ({violations.length})
            </h4>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {violations.map((violation, index) => (
                <div key={index} className="text-xs text-orange-700">
                  <span className="font-medium">Asset {violation.asset_id.substring(0, 8)}:</span>{' '}
                  {violation.message}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="space-y-2 pt-3 border-t border-gray-200">
          <button
            onClick={handleSave}
            disabled={!hasUnsavedChanges}
            className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
          >
            Save Changes
          </button>
          <button
            onClick={onReoptimize}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm font-medium"
          >
            Re-optimize with Current Layout
          </button>
        </div>

        {/* Instructions */}
        <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600 space-y-1">
          <p className="font-medium text-gray-700">Editor Tips:</p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>Click assets on the map to select them</li>
            <li>Drag assets to move them (when enabled in map)</li>
            <li>Use rotation controls to adjust asset orientation</li>
            <li>Red markers indicate constraint violations</li>
            <li>Use Undo/Redo to revert changes</li>
            <li>Save your changes before re-optimizing</li>
          </ul>
        </div>

        {/* Statistics */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-gray-50 rounded p-2">
            <p className="text-gray-600">Total Assets</p>
            <p className="text-lg font-semibold text-gray-900">{assets.length}</p>
          </div>
          <div className="bg-gray-50 rounded p-2">
            <p className="text-gray-600">Violations</p>
            <p
              className={`text-lg font-semibold ${
                violations.length === 0 ? 'text-green-600' : 'text-red-600'
              }`}
            >
              {violations.length}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
