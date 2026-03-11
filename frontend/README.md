# Entmoot Frontend

React frontend application for Entmoot - AI-driven site layout automation.

## Features

- **File Upload Wizard**: Drag-and-drop interface for uploading geospatial files (KMZ, KML, GeoJSON, GeoTIFF)
- **Configuration Panel**: Comprehensive UI for configuring:
  - Asset types and quantities
  - Constraint parameters (setbacks, buffers, exclusion zones)
  - Road design specifications
  - Optimization weights
- **Responsive Design**: Desktop-first responsive layout
- **Type Safety**: Full TypeScript implementation
- **API Integration**: Axios-based client with error handling

## Tech Stack

- React 19
- TypeScript 5
- Vite 7
- Tailwind CSS 4
- MapLibre GL 5
- React Router v7
- Axios
- Recharts

## Project Structure

```
frontend/
├── src/
│   ├── api/          # API client and HTTP utilities
│   ├── components/   # Reusable React components
│   ├── hooks/        # Custom React hooks
│   ├── pages/        # Page components
│   ├── types/        # TypeScript type definitions
│   ├── utils/        # Utility functions
│   ├── App.tsx       # Main application component
│   └── main.tsx      # Application entry point
├── public/           # Static assets
└── package.json
```

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API running on http://localhost:8000 (configurable)

### Installation

```bash
cd frontend
npm install
```

### Configuration

Create a `.env` file (or copy from `.env.example`):

```env
VITE_API_BASE_URL=http://localhost:8000
```

### Development

Start the development server:

```bash
npm run dev
```

The application will be available at http://localhost:5173

### Build

Build for production:

```bash
npm run build
```

Preview production build:

```bash
npm run preview
```

## Available Routes

- `/` - Redirects to upload page
- `/upload` - File upload wizard
- `/config` - Configuration panel (requires `upload_id` query parameter)
- `/results/:projectId` - Optimization results with map viewer, layout editor, and dashboard
- `/projects` - Projects list page

## API Integration

The frontend integrates with the Entmoot backend API:

- `POST /api/v1/upload` - Upload geospatial files
- `POST /api/v1/projects` - Create project and start optimization
- `GET /api/v1/projects/{id}/status` - Poll optimization progress
- `GET /api/v1/projects/{id}/results` - Retrieve optimization results
- `POST /api/v1/projects/{id}/validate-placement` - Validate asset placement (drag-and-drop)
- `POST /api/v1/projects/{id}/reoptimize` - Re-run optimization with updated config
- `PUT /api/v1/projects/{id}/alternatives/{alt}/` - Save edited layout

## Features in Detail

### File Upload

- Drag-and-drop interface
- File browser fallback
- Client-side validation:
  - File type checking
  - File size limits (50MB)
  - MIME type validation
- Upload progress indicator
- File preview with metadata
- Error messaging

### Configuration Panel

- Asset configuration:
  - Multiple asset types (buildings, yards, parking, etc.)
  - Quantity and size inputs
  - Dynamic asset addition/removal
- Constraint configuration:
  - Setback distance sliders
  - Wetland buffers
  - Slope limits
  - Boolean toggles for exclusion zones
- Road design parameters:
  - Width, grade, and turning radius
  - Surface type selection
  - Sidewalk options
- Optimization weights:
  - Slider controls for weight distribution
  - Real-time validation (must sum to 100%)

## Development Notes

- The app uses React Router for client-side routing
- All API calls go through the centralized API client in `src/api/client.ts`
- TypeScript types mirror the backend Pydantic models
- Tailwind CSS is configured for utility-first styling
- Error handling includes both network and validation errors

## Next Steps

- Implement configuration preset save/load functionality
- Wire in export endpoint (backend classes exist, API returns 501)
- Implement WebSocket connection for real-time processing updates
