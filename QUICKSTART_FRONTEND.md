# Entmoot Frontend - Quick Start Guide

## Prerequisites

- Node.js 18+ and npm
- Backend API running (optional for development)

## Installation

```bash
cd frontend
npm install
```

## Configuration

Create a `.env` file (or use the provided `.env.example`):

```bash
cp .env.example .env
```

Edit `.env`:
```env
VITE_API_BASE_URL=http://localhost:8000
```

## Development

Start the development server:

```bash
npm run dev
```

The app will be available at: **http://localhost:5173**

## Build for Production

```bash
npm run build
```

Built files will be in `dist/` directory.

## Preview Production Build

```bash
npm run preview
```

Preview will be available at: **http://localhost:4173**

## Project Structure

```
frontend/
├── src/
│   ├── api/          # API client (Axios)
│   ├── components/   # Reusable components
│   ├── hooks/        # Custom React hooks
│   ├── pages/        # Page components
│   ├── types/        # TypeScript types
│   ├── utils/        # Utility functions
│   └── App.tsx       # Main app with routing
├── public/           # Static assets
└── package.json      # Dependencies
```

## Available Scripts

```bash
npm run dev        # Start development server
npm run build      # Build for production
npm run preview    # Preview production build
npm run lint       # Run ESLint
```

## Features

### 1. File Upload Page (`/upload`)
- Drag-and-drop file upload
- Supports: KMZ, KML, GeoJSON, GeoTIFF
- Max file size: 50MB
- Real-time validation and progress tracking

### 2. Configuration Page (`/config`)
- Configure project assets
- Set constraints and buffers
- Design road parameters
- Adjust optimization weights

## Usage Flow

1. **Upload File** - Drop or select a geospatial file
2. **Configure** - Set project parameters
3. **Generate** - Submit configuration (API integration pending)

## API Integration

The frontend expects these endpoints:

```
POST   /api/v1/upload              # Upload files
GET    /api/v1/upload/health       # Check upload service
GET    /health                     # Check API health
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API URL |

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **React Router** - Navigation
- **Axios** - HTTP client

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## Troubleshooting

### Port Already in Use

If port 5173 is in use:
```bash
npm run dev -- --port 3000
```

### API Connection Issues

Check that:
1. Backend is running on configured URL
2. CORS is enabled on backend
3. `.env` has correct `VITE_API_BASE_URL`

### Build Errors

Clear node_modules and reinstall:
```bash
rm -rf node_modules package-lock.json
npm install
```

## Development Tips

- Hot module replacement (HMR) is enabled
- TypeScript errors show in terminal and browser
- React DevTools extension recommended
- Tailwind CSS IntelliSense VSCode extension recommended

## Documentation

See `frontend/README.md` for detailed documentation.

## Getting Help

- Check browser console for errors
- Review network tab for API calls
- Check backend logs for server errors

## Next Steps

After setting up:
1. Test file upload with sample files
2. Explore configuration options
3. Review generated TypeScript types
4. Customize styling as needed

---

**Ready to develop!** 🚀
