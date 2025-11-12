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

- React 18
- TypeScript
- Vite (build tool)
- Tailwind CSS
- React Router v6
- Axios

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

## API Integration

The frontend integrates with the Entmoot backend API:

- `POST /api/v1/upload` - Upload geospatial files
- `GET /api/v1/upload/health` - Check upload service health
- `GET /health` - Check API health

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
- Add results/visualization page
- Implement WebSocket connection for real-time processing updates
- Add authentication and user management
- Implement project history and management
