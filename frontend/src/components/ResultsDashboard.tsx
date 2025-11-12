/**
 * ResultsDashboard Component - Displays metrics, charts, and download options
 */

import React, { useState } from 'react';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type {
  LayoutMetrics,
  PlacedAsset,
  RoadNetwork,
  LayoutAlternative,
  ExportFormat,
} from '../types/results';

interface ResultsDashboardProps {
  metrics: LayoutMetrics;
  assets: PlacedAsset[];
  roadNetwork?: RoadNetwork;
  alternatives?: LayoutAlternative[];
  selectedAlternativeId?: string;
  onAlternativeSelect?: (alternativeId: string) => void;
  onExport?: (format: ExportFormat) => void;
  onReoptimize?: () => void;
}

export const ResultsDashboard: React.FC<ResultsDashboardProps> = ({
  metrics,
  assets,
  roadNetwork,
  alternatives = [],
  selectedAlternativeId,
  onAlternativeSelect,
  onExport,
  onReoptimize,
}) => {
  const [activeTab, setActiveTab] = useState<'metrics' | 'assets' | 'comparison'>('metrics');

  // Format numbers
  const formatNumber = (num: number): string => {
    return num.toLocaleString('en-US', { maximumFractionDigits: 0 });
  };

  const formatCurrency = (num: number): string => {
    return `$${num.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  };

  const formatPercentage = (num: number): string => {
    return `${num.toFixed(1)}%`;
  };

  // Prepare cost breakdown chart data
  // Filter out tiny slices (less than 3% of total) and group them as "Other"
  const totalCost = metrics.estimated_cost.total;
  const costItems = [
    { name: 'Earthwork', value: metrics.estimated_cost.earthwork, color: '#8B4513' },
    { name: 'Roads', value: metrics.estimated_cost.roads, color: '#555555' },
    { name: 'Construction', value: metrics.estimated_cost.utilities, color: '#1E90FF' },
    { name: 'Drainage', value: metrics.estimated_cost.drainage, color: '#4169E1' },
    { name: 'Landscaping', value: metrics.estimated_cost.landscaping, color: '#228B22' },
    { name: 'Contingency', value: metrics.estimated_cost.contingency, color: '#FFA500' },
  ];

  // Separate significant and tiny items
  const significantItems = costItems.filter((item) => (item.value / totalCost) >= 0.03);
  const tinyItems = costItems.filter((item) => (item.value / totalCost) < 0.03);

  // Add "Other" category if there are tiny items
  const costData = [...significantItems];
  if (tinyItems.length > 0) {
    const otherValue = tinyItems.reduce((sum, item) => sum + item.value, 0);
    costData.push({ name: 'Other', value: otherValue, color: '#CCCCCC' });
  }

  // Prepare earthwork chart data
  const earthworkData = [
    { name: 'Cut', value: Math.abs(metrics.earthwork_volumes.cut), color: '#DC143C' },
    { name: 'Fill', value: metrics.earthwork_volumes.fill, color: '#32CD32' },
  ];

  // Group assets by type
  const assetsByType = assets.reduce((acc, asset) => {
    acc[asset.type] = (acc[asset.type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const assetTypeData = Object.entries(assetsByType).map(([type, count]) => ({
    name: type.replace('_', ' '),
    count,
  }));

  return (
    <div className="bg-white rounded-lg shadow-md">
      {/* Tabs */}
      <div className="border-b border-gray-200">
        <div className="flex space-x-4 px-6">
          <button
            onClick={() => setActiveTab('metrics')}
            className={`py-4 px-2 border-b-2 font-medium text-sm ${
              activeTab === 'metrics'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Metrics
          </button>
          <button
            onClick={() => setActiveTab('assets')}
            className={`py-4 px-2 border-b-2 font-medium text-sm ${
              activeTab === 'assets'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Asset Details
          </button>
          {alternatives.length > 1 && (
            <button
              onClick={() => setActiveTab('comparison')}
              className={`py-4 px-2 border-b-2 font-medium text-sm ${
                activeTab === 'comparison'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Compare Alternatives
            </button>
          )}
        </div>
      </div>

      {/* Tab Content */}
      <div className="p-6">
        {activeTab === 'metrics' && (
          <div className="space-y-6">
            {/* Key Metrics Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-blue-50 rounded-lg p-4">
                <p className="text-sm text-blue-600 font-medium">Property Area</p>
                <p className="text-2xl font-bold text-blue-900 mt-1">
                  {formatNumber(metrics.property_area)}
                </p>
                <p className="text-xs text-blue-600 mt-1">sq ft</p>
              </div>

              <div className="bg-green-50 rounded-lg p-4">
                <p className="text-sm text-green-600 font-medium">Buildable Area</p>
                <p className="text-2xl font-bold text-green-900 mt-1">
                  {formatNumber(metrics.buildable_area)}
                </p>
                <p className="text-xs text-green-600 mt-1">
                  {formatPercentage(metrics.buildable_percentage)} of total
                </p>
              </div>

              <div className="bg-purple-50 rounded-lg p-4">
                <p className="text-sm text-purple-600 font-medium">Assets Placed</p>
                <p className="text-2xl font-bold text-purple-900 mt-1">{metrics.assets_placed}</p>
                <p className="text-xs text-purple-600 mt-1">total units</p>
              </div>

              <div className="bg-orange-50 rounded-lg p-4">
                <p className="text-sm text-orange-600 font-medium">Road Length</p>
                <p className="text-2xl font-bold text-orange-900 mt-1">
                  {formatNumber(metrics.total_road_length)}
                </p>
                <p className="text-xs text-orange-600 mt-1">feet</p>
              </div>
            </div>

            {/* Cost Summary */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Estimated Cost</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="space-y-2">
                    {Object.entries(metrics.estimated_cost)
                      .filter(([key]) => key !== 'total')
                      .map(([key, value]) => (
                        <div key={key} className="flex justify-between text-sm">
                          <span className="text-gray-600 capitalize">
                            {key.replace('_', ' ')}:
                          </span>
                          <span className="font-medium text-gray-900">
                            {formatCurrency(value)}
                          </span>
                        </div>
                      ))}
                  </div>
                  <div className="border-t border-gray-300 mt-3 pt-3">
                    <div className="flex justify-between text-base font-bold">
                      <span className="text-gray-900">Total:</span>
                      <span className="text-blue-600">
                        {formatCurrency(metrics.estimated_cost.total)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Cost Breakdown Chart */}
                <div className="h-48">
                  <ResponsiveContainer width="100%" height={192}>
                    <PieChart>
                      <Pie
                        data={costData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={60}
                        label={(entry) =>
                          `${entry.name}: ${formatPercentage((entry.value / metrics.estimated_cost.total) * 100)}`
                        }
                      >
                        {costData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => formatCurrency(value as number)} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Earthwork Summary */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Earthwork Summary</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-3">
                  <div>
                    <p className="text-sm text-gray-600">Cut Volume</p>
                    <p className="text-xl font-bold text-red-600">
                      {formatNumber(Math.abs(metrics.earthwork_volumes.cut))} yd³
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Fill Volume</p>
                    <p className="text-xl font-bold text-green-600">
                      {formatNumber(metrics.earthwork_volumes.fill)} yd³
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Net Volume</p>
                    <p className="text-xl font-bold text-blue-600">
                      {formatNumber(metrics.earthwork_volumes.net)} yd³
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Balance Ratio</p>
                    <p className="text-xl font-bold text-gray-900">
                      {metrics.earthwork_volumes.balance_ratio.toFixed(2)}
                    </p>
                  </div>
                </div>

                {/* Earthwork Chart */}
                <div className="h-48">
                  <ResponsiveContainer width="100%" height={192}>
                    <BarChart data={earthworkData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip formatter={(value) => `${formatNumber(value as number)} yd³`} />
                      <Bar dataKey="value">
                        {earthworkData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Optimization Score & Compliance */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-700 mb-2">Optimization Score</h3>
                <div className="flex items-end space-x-2">
                  <p className="text-4xl font-bold text-blue-600">
                    {metrics.optimization_score.toFixed(1)}
                  </p>
                  <p className="text-lg text-gray-500 pb-1">/ 100</p>
                </div>
                <div className="mt-2 bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all"
                    style={{ width: `${metrics.optimization_score}%` }}
                  />
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-700 mb-2">Constraint Compliance</h3>
                <div className="flex items-end space-x-2">
                  <p
                    className={`text-4xl font-bold ${
                      metrics.constraint_violations === 0 ? 'text-green-600' : 'text-red-600'
                    }`}
                  >
                    {metrics.constraint_violations}
                  </p>
                  <p className="text-lg text-gray-500 pb-1">violations</p>
                </div>
                <p className="text-sm text-gray-600 mt-2">
                  {metrics.constraint_violations === 0
                    ? 'All constraints satisfied'
                    : 'Review violations in editor'}
                </p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'assets' && (
          <div className="space-y-6">
            {/* Asset Type Distribution */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Asset Distribution by Type
              </h3>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={assetTypeData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="count" fill="#4F46E5" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Asset Table */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Asset Details</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        ID
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Type
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Size (ft)
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Rotation
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Position
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {assets.map((asset) => (
                      <tr key={asset.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-mono text-gray-900">
                          {asset.id.substring(0, 8)}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                          {asset.type.replace('_', ' ')}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {asset.width} × {asset.length}
                          {asset.height && ` × ${asset.height}`}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">{asset.rotation}°</td>
                        <td className="px-4 py-3 text-sm text-gray-600 font-mono">
                          {asset.position.latitude.toFixed(6)}, {asset.position.longitude.toFixed(6)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Road Network Summary */}
            {roadNetwork && (
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-3">Road Network</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-gray-600">Total Segments</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {roadNetwork.segments.length}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Total Length</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {formatNumber(roadNetwork.total_length)} ft
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Intersections</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {roadNetwork.intersections.length}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'comparison' && alternatives.length > 1 && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Alternative Layouts</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {alternatives.map((alt) => (
                <div
                  key={alt.id}
                  className={`border-2 rounded-lg p-4 cursor-pointer transition-all ${
                    alt.id === selectedAlternativeId
                      ? 'border-blue-600 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => onAlternativeSelect?.(alt.id)}
                >
                  <h4 className="font-semibold text-gray-900 mb-2">{alt.name}</h4>
                  {alt.description && (
                    <p className="text-sm text-gray-600 mb-3">{alt.description}</p>
                  )}
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <p className="text-gray-600">Score:</p>
                      <p className="font-medium">{alt.metrics.optimization_score}/100</p>
                    </div>
                    <div>
                      <p className="text-gray-600">Cost:</p>
                      <p className="font-medium">
                        {formatCurrency(alt.metrics.estimated_cost.total)}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-600">Assets:</p>
                      <p className="font-medium">{alt.metrics.assets_placed}</p>
                    </div>
                    <div>
                      <p className="text-gray-600">Violations:</p>
                      <p
                        className={`font-medium ${
                          alt.metrics.constraint_violations === 0
                            ? 'text-green-600'
                            : 'text-red-600'
                        }`}
                      >
                        {alt.metrics.constraint_violations}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="mt-6 flex flex-wrap gap-3 pt-6 border-t border-gray-200">
          <button
            onClick={() => onExport?.('pdf')}
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors text-sm"
          >
            Export PDF
          </button>
          <button
            onClick={() => onExport?.('kmz')}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm"
          >
            Export KMZ
          </button>
          <button
            onClick={() => onExport?.('geojson')}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors text-sm"
          >
            Export GeoJSON
          </button>
          <button
            onClick={() => onExport?.('dxf')}
            className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors text-sm"
          >
            Export DXF
          </button>
          {onReoptimize && (
            <button
              onClick={onReoptimize}
              className="ml-auto px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 transition-colors text-sm"
            >
              Re-optimize Layout
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
