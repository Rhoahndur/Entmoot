# Results UI Documentation

## Overview

The Results UI provides a comprehensive interface for viewing, analyzing, and editing site layout optimization results. It combines interactive mapping, metrics dashboards, and layout editing capabilities into a unified experience.

## Components

### 1. ResultsPage (`src/pages/ResultsPage.tsx`)

Main page that integrates all results components.

**Features:**
- Responsive grid layout
- Toggle between view and edit modes
- Layer visibility controls
- Alternative layout selection
- Quick stats sidebar

**URL Parameters:**
- `project_id` - Required project identifier

**Example:**
```
/results?project_id=abc123
```

### 2. MapViewer (`src/components/MapViewer.tsx`)

Interactive map visualization using Mapbox GL JS.

**Features:**
- Base map with satellite/terrain imagery
- Property boundary overlay
- Asset markers (clickable, color-coded)
- Road network visualization
- Constraint zones (color-coded by severity)
- Buildable areas
- Measurement tools
- Screenshot capture
- Fullscreen mode
- Zoom/pan controls

**Layer Types:**
- `base_map` - Satellite imagery
- `terrain` - Terrain data
- `property_boundary` - Property lines (red)
- `assets` - Placed assets (orange markers)
- `roads` - Road network (gray lines)
- `constraints` - Constraint zones (yellow/orange/red)
- `buildable_areas` - Usable areas (green)
- `earthwork` - Cut/fill zones

**Props:**
```typescript
interface MapViewerProps {
  bounds: Bounds;
  propertyBoundary: Coordinate[];
  assets: PlacedAsset[];
  roadNetwork?: RoadNetwork;
  constraintZones?: ConstraintZone[];
  buildableAreas?: BuildableArea[];
  layerVisibility: LayerVisibility;
  onAssetClick?: (asset: PlacedAsset) => void;
  onMapClick?: (coordinate: Coordinate) => void;
  editable?: boolean;
  selectedAssetId?: string;
}
```

### 3. ResultsDashboard (`src/components/ResultsDashboard.tsx`)

Metrics and data visualization dashboard.

**Tabs:**
1. **Metrics** - Key performance indicators and charts
2. **Asset Details** - Asset list and distribution
3. **Compare Alternatives** - Side-by-side comparison

**Metrics Cards:**
- Property area (sq ft)
- Buildable area (sq ft & %)
- Assets placed (count)
- Road length (ft)
- Earthwork volumes (yd³)
- Estimated cost ($)
- Constraint violations
- Optimization score (0-100)

**Charts:**
- Cost breakdown (pie chart)
- Earthwork summary (bar chart)
- Asset distribution by type (bar chart)

**Export Buttons:**
- PDF report
- KMZ/KML (Google Earth)
- GeoJSON
- DXF (AutoCAD)

### 4. LayoutEditor (`src/components/LayoutEditor.tsx`)

Interactive layout editing interface.

**Features:**
- Asset selection
- Rotation controls (±5°, ±15°, slider)
- Delete asset
- Undo/redo operations
- Constraint violation indicators
- Save changes
- Re-optimize button

**Operation History:**
- Move asset
- Rotate asset
- Delete asset
- Add asset

**Props:**
```typescript
interface LayoutEditorProps {
  assets: PlacedAsset[];
  violations: ConstraintViolation[];
  onAssetsChange: (assets: PlacedAsset[]) => void;
  onSave: () => void;
  onReoptimize: () => void;
  selectedAssetId?: string;
  onAssetSelect: (assetId: string | undefined) => void;
}
```

## Type Definitions

### Results Types (`src/types/results.ts`)

Key type definitions:

```typescript
// Core data structures
interface OptimizationResults {
  project_id: string;
  project_name: string;
  property_boundary: Coordinate[];
  bounds: Bounds;
  alternatives: LayoutAlternative[];
  selected_alternative_id?: string;
  created_at: string;
  updated_at: string;
}

interface LayoutAlternative {
  id: string;
  name: string;
  description?: string;
  metrics: LayoutMetrics;
  assets: PlacedAsset[];
  road_network: RoadNetwork;
  constraint_zones: ConstraintZone[];
  buildable_areas: BuildableArea[];
  earthwork_zones: EarthworkZone[];
  violations: ConstraintViolation[];
  created_at: string;
}

interface PlacedAsset {
  id: string;
  type: AssetType;
  position: Coordinate;
  rotation: number;
  width: number;
  length: number;
  height?: number;
  polygon: Coordinate[];
  properties?: Record<string, any>;
}
```

## API Integration

### API Endpoints (`src/api/client.ts`)

**Available Functions:**

```typescript
// Get optimization results
getOptimizationResults(projectId: string): Promise<OptimizationResults>

// Save edited layout
saveLayout(
  projectId: string,
  alternativeId: string,
  assets: PlacedAsset[]
): Promise<{ success: boolean }>

// Re-optimize with new constraints
reoptimizeLayout(
  projectId: string,
  config: Partial<ProjectConfig>
): Promise<OptimizationResults>

// Export layout
exportLayout(
  projectId: string,
  alternativeId: string,
  format: ExportFormat
): Promise<Blob>
```

## Export Functionality

### Export Utilities (`src/utils/export.ts`)

**Supported Formats:**

1. **PDF** - Comprehensive report with metrics, costs, and asset lists
2. **GeoJSON** - Standard geospatial format for GIS applications
3. **KML** - Google Earth compatible format
4. **DXF** - AutoCAD compatible format

**Usage:**
```typescript
import { exportLayout } from '../utils/export';

await exportLayout(
  'pdf',          // format
  results,        // OptimizationResults
  alternativeId,  // string
  {               // options (optional)
    pageSize: 'letter',
    orientation: 'landscape'
  }
);
```

**PDF Features:**
- Project summary
- Key metrics
- Cost breakdown
- Earthwork summary
- Complete asset list
- Timestamp and branding

**GeoJSON Features:**
- Property boundary
- Asset footprints
- Road network
- Constraint zones
- Buildable areas

## Environment Configuration

### Required Environment Variables

```env
# Mapbox API Token (required for map display)
VITE_MAPBOX_TOKEN=your_mapbox_token_here

# API Base URL (optional, defaults to localhost:8000)
VITE_API_BASE_URL=http://localhost:8000
```

### Getting a Mapbox Token

1. Sign up at [mapbox.com](https://www.mapbox.com)
2. Navigate to Account → Tokens
3. Create a new token with default permissions
4. Add to `.env` file as `VITE_MAPBOX_TOKEN`

## Usage Examples

### Basic Usage Flow

1. **Navigate to Results Page:**
   ```
   /results?project_id=your_project_id
   ```

2. **View Layout:**
   - Map displays with all layers
   - Dashboard shows metrics
   - Toggle layers with layer controls

3. **Edit Layout:**
   - Click "Edit Layout" button
   - Click asset on map to select
   - Use rotation controls
   - Delete unwanted assets
   - Save changes

4. **Export Data:**
   - Click export button for desired format
   - File downloads automatically

5. **Compare Alternatives:**
   - Switch to "Compare Alternatives" tab
   - Click alternative cards to switch
   - Side-by-side metrics comparison

### Advanced Features

**Measurement Tool:**
```typescript
// Click "Measure" button on map
// Click points on map to measure distance
// Results shown in measurement panel
```

**Re-optimization:**
```typescript
// Edit layout manually
// Click "Re-optimize with Current Layout"
// System generates new alternatives based on edits
```

**Custom Styling:**
```typescript
// Constraint zones are color-coded:
// - Yellow: Low severity
// - Orange: Medium severity
// - Red: High severity

// Assets are color-coded:
// - Orange: Normal state
// - Blue: Selected state
```

## Responsive Design

The UI is fully responsive with breakpoints:
- Mobile: < 640px (stack layout)
- Tablet: 640-1024px (adjusted grid)
- Desktop: > 1024px (full grid layout)

**Mobile Optimizations:**
- Simplified controls
- Touch-friendly buttons
- Collapsible panels
- Scrollable tables

## Performance Considerations

**Large Datasets:**
- Map uses clustering for 100+ assets
- Pagination for asset tables
- Lazy loading for charts
- Virtual scrolling for long lists

**Optimization Tips:**
- Limit visible layers for better performance
- Use measurement tool sparingly
- Export large datasets in background
- Close unused tabs in dashboard

## Troubleshooting

### Common Issues

1. **Map Not Loading:**
   - Check `VITE_MAPBOX_TOKEN` is set
   - Verify internet connection
   - Check browser console for errors

2. **Assets Not Displaying:**
   - Verify data format matches types
   - Check layer visibility toggles
   - Ensure coordinates are valid

3. **Export Fails:**
   - Check file-saver library is installed
   - Verify browser allows downloads
   - Check data completeness

4. **Edit Mode Issues:**
   - Ensure edit mode is enabled
   - Check asset is properly selected
   - Verify operation history is working

### Debug Mode

Enable detailed logging:
```typescript
// In browser console
localStorage.setItem('DEBUG', 'entmoot:*');
```

## Future Enhancements

**Planned Features:**
- 3D visualization mode
- Animated layout transitions
- Collaborative editing
- Real-time optimization
- Advanced filtering
- Custom layer creation
- Batch operations
- Mobile app

## Dependencies

```json
{
  "mapbox-gl": "^3.x",
  "recharts": "^2.x",
  "jspdf": "^2.x",
  "file-saver": "^2.x",
  "react": "^19.x",
  "react-router-dom": "^7.x"
}
```

## Browser Support

- Chrome 90+ ✅
- Firefox 88+ ✅
- Safari 14+ ✅
- Edge 90+ ✅

**WebGL Required:**
- Mapbox GL requires WebGL
- Disable hardware acceleration may cause issues

## Accessibility

**WCAG 2.1 AA Compliance:**
- Keyboard navigation support
- Screen reader compatible
- High contrast mode
- Focus indicators
- ARIA labels

**Keyboard Shortcuts:**
- `Ctrl+Z`: Undo
- `Ctrl+Y`: Redo
- `Escape`: Deselect asset
- `Delete`: Delete selected asset

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
- GitHub Issues: [Open an issue on the repository]
