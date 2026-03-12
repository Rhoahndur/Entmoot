# Entmoot

AI-driven site layout automation for real estate due diligence.

## Overview

Entmoot is a full-stack geospatial platform that automates site layout generation and feasibility analysis for real estate development. Upload a property boundary (KML/KMZ/GeoJSON), configure assets and constraints, and receive an optimized site plan produced by a genetic algorithm — complete with road networks, earthwork estimates, and exportable deliverables for CAD and GIS tools.

## Features

- **Site boundary parsing** — KML, KMZ, GeoJSON, and GeoTIFF input with automatic CRS detection and UTM projection
- **Genetic algorithm optimization** — multi-objective placement of buildings, parking lots, equipment yards, and storage tanks with configurable weights (cost, buildable area, accessibility, environmental impact, aesthetics)
- **Constraint enforcement** — setback distances, property-line compliance, exclusion zones, wetland buffers, slope limits, and inter-asset spacing
- **OpenStreetMap integration** — automatic detection of existing buildings, roads, utilities, and water features via Overpass API with typed buffer generation and road entry point identification
- **Road network generation** — MST-optimized topology with A\* grid-based pathfinding, road classification (primary/secondary/access), intersection generation, and grade-aware routing; falls back to straight-line roads on failure
- **Earthwork estimation** — cut/fill volume calculations with cost projections
- **Terrain analysis** — DEM loading, slope/aspect computation, buildability scoring, and slope-based exclusion zones
- **Regulatory data** — FEMA flood zone queries and USGS 3DEP elevation lookups via rate-limited async clients
- **Export** — KMZ (Google Earth), GeoJSON (QGIS), DXF (AutoCAD), and PDF site reports
- **Interactive frontend** — drag-and-drop upload, configuration wizard, MapLibre GL map viewer, and layout editor with shift+drag asset repositioning
- **API key authentication** — optional `X-API-Key` header protection for all `/api/v1` routes

## Technology Stack

| Layer | Tools |
|---|---|
| **Backend** | Python 3.12+, FastAPI, Pydantic v2, Uvicorn |
| **Frontend** | React 19, TypeScript 5, Vite 7, Tailwind CSS 4, MapLibre GL 5 |
| **Geospatial** | Shapely, PyProj, GDAL/Rasterio, NetworkX, simplekml, ezdxf |
| **Optimization** | Custom genetic algorithm (population-based, multi-objective) |
| **External data** | OpenStreetMap Overpass API, FEMA NFHL, USGS 3DEP |
| **Storage** | Redis (project/result persistence) with in-memory fallback |
| **Testing** | pytest (unit/integration/e2e markers, 1285+ tests) |
| **Code quality** | Black, Flake8, mypy (enforced in CI), Bandit, pre-commit hooks |
| **Infrastructure** | Docker multi-stage builds, Docker Compose, GitHub Actions CI/CD |

## Prerequisites

### Docker (recommended)

- Docker 20.10+
- Docker Compose v2.0+

### Local development

- Python 3.12+
- Node.js 18+
- pip, npm
- Git
- System libraries: `libgdal-dev`, `libproj-dev`, `libgeos-dev`
- (Optional) PostgreSQL with PostGIS, Redis

## Quick Start

### With Docker

```bash
git clone <repository-url>
cd Entmoot
cp .env.example .env   # edit passwords and secrets

# Production
docker compose up -d

# Development (hot reload)
docker compose -f docker-compose.dev.yml up -d
```

| Service | URL |
|---|---|
| Frontend | http://localhost |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

```bash
docker compose down       # stop
docker compose down -v    # stop + delete volumes
```

### Local development

```bash
# Backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt   # or: pip install -e ".[dev]"
pre-commit install                    # optional
uvicorn entmoot.api.main:app --reload

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

## Project Structure

```
Entmoot/
├── src/entmoot/
│   ├── api/                  # FastAPI route handlers
│   │   ├── main.py           #   app factory, CORS, lifespan, health check
│   │   ├── projects.py       #   project CRUD & results (thin, delegates to services)
│   │   ├── upload.py         #   file upload endpoint
│   │   ├── auth.py           #   API key authentication dependency
│   │   ├── error_handlers.py #   custom exception handlers
│   │   └── middleware.py     #   logging context & request correlation
│   ├── services/             # Business logic layer
│   │   ├── project_service.py      # validation, result assembly, violation detection
│   │   ├── optimization_service.py # layout generation & genetic algorithm orchestration
│   │   ├── terrain_service.py      # DEM loading, reprojection, slope computation
│   │   └── existing_conditions_service.py # OSM data fetch, buffer generation
│   ├── core/                 # Domain modules
│   │   ├── constraints/      #   setbacks, buffers, exclusion zones
│   │   ├── crs/              #   CRS detection, normalization, UTM projection
│   │   ├── earthwork/        #   cut/fill volume & cost estimation
│   │   ├── export/           #   KMZ, GeoJSON, DXF exporters
│   │   ├── optimization/     #   genetic algorithm, collision detection, problem defs
│   │   ├── parsers/          #   KML / KMZ parsers & validators
│   │   ├── reports/          #   PDF report generation
│   │   ├── roads/            #   navigation graph, A* pathfinding, MST road network
│   │   ├── terrain/          #   DEM loading, slope, aspect, buildability
│   │   ├── visualization/    #   2D / 3D map rendering
│   │   ├── config.py         #   pydantic-settings configuration
│   │   ├── redis_storage.py  #   Redis-backed project/result store
│   │   └── cleanup.py        #   upload retention / cleanup service
│   ├── integrations/         # External API clients
│   │   ├── rate_limiter.py   #   shared token-bucket rate limiter
│   │   ├── osm/              #   OpenStreetMap Overpass API (buildings, roads, utilities, water)
│   │   ├── fema/             #   FEMA NFHL flood zone queries
│   │   └── usgs/             #   USGS 3DEP elevation queries & DEM tiles
│   ├── models/               # Pydantic data models
│   └── utils/                # Logging, versioning helpers
├── frontend/
│   └── src/
│       ├── pages/            # UploadPage, ConfigPage, ResultsPage, ProjectsListPage
│       ├── components/       # FileDropzone, MapViewer, LayoutEditor, ResultsDashboard
│       ├── hooks/            # useFileUpload
│       ├── api/              # Axios API client (with API key interceptor)
│       └── types/            # TypeScript type definitions
├── tests/                    # pytest suite (64 test files, 1285+ tests)
│   ├── conftest.py           #   shared fixtures, auto-assigned markers
│   ├── test_constraints/     test_crs/       test_earthwork/
│   ├── test_export/          test_integrations/  test_optimization/
│   ├── test_reports/         test_roads/     test_terrain/
│   └── test_visualization/
├── scripts/
│   └── generate_openapi.py   # generates docs/openapi.yaml
├── docs/
│   └── openapi.yaml          # versioned OpenAPI schema (CI-checked)
├── .github/workflows/
│   └── ci.yml                # lint, test, security, build, frontend-lint
├── Dockerfile                # multi-stage backend image
├── docker-compose.yml        # production stack
├── docker-compose.dev.yml    # development stack
├── pyproject.toml            # project metadata, tool configs
├── requirements.in           # unpinned runtime deps (pip-compile input)
├── requirements-dev.in       # unpinned dev deps
├── requirements.txt          # pinned runtime deps
├── requirements-dev.txt      # pinned dev deps
└── LICENSE                   # MIT
```

## Configuration

All settings use the `ENTMOOT_` prefix and can be set via environment variables or a `.env` file. Key options:

| Variable | Default | Description |
|---|---|---|
| `ENTMOOT_ENVIRONMENT` | `development` | `development`, `staging`, or `production` |
| `ENTMOOT_CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated origins (wildcard `*` rejected in production) |
| `ENTMOOT_AUTH_ENABLED` | `true` | Enable API key authentication |
| `ENTMOOT_API_KEYS` | *(empty)* | Comma-separated valid API keys (empty = auth disabled) |
| `ENTMOOT_MAX_UPLOAD_SIZE_MB` | `50` | Maximum upload file size |
| `ENTMOOT_UPLOADS_DIR` | `./data/uploads` | Upload storage directory |

See [`.env.example`](.env.example) for the full list.

## Development

### Running tests

```bash
pytest                        # all tests (markers auto-assigned by conftest.py)
pytest -m unit                # unit tests only
pytest -m integration         # integration tests only
pytest -m "not slow"          # skip slow tests
pytest --cov=src/entmoot --cov-report=html   # with HTML coverage report
```

### Code quality

```bash
black src/ tests/             # format
flake8 src/ tests/            # lint
mypy src/                     # type check (enforced in CI)
pre-commit run --all-files    # all hooks at once
```

### OpenAPI schema

```bash
python scripts/generate_openapi.py          # regenerate docs/openapi.yaml
python scripts/generate_openapi.py --check  # verify schema is current (CI uses this)
```

### Dependency management

Runtime and dev dependencies are declared in `requirements.in` / `requirements-dev.in`. Generate pinned lock files with:

```bash
pip-compile requirements.in -o requirements.txt
pip-compile requirements-dev.in -o requirements-dev.txt
```

## API Overview

All `/api/v1` routes require an `X-API-Key` header when authentication is enabled.

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | API info (public) |
| `GET` | `/health` | Health check (public) |
| `POST` | `/api/v1/upload` | Upload KML/KMZ/GeoJSON/TIFF |
| `GET` | `/api/v1/upload/health` | Upload service health |
| `GET` | `/api/v1/projects` | List all projects |
| `POST` | `/api/v1/projects` | Create project & start optimization |
| `GET` | `/api/v1/projects/{id}/status` | Poll optimization progress |
| `GET` | `/api/v1/projects/{id}/results` | Retrieve optimization results |
| `POST` | `/api/v1/projects/{id}/reoptimize` | Re-run with updated config |
| `POST` | `/api/v1/projects/{id}/validate-placement` | Validate single asset placement (drag-and-drop) |
| `PUT` | `/api/v1/projects/{id}/alternatives/{alt}/` | Save edited layout |
| `GET` | `/api/v1/projects/{id}/alternatives/{alt}/export/{fmt}` | Export layout (not yet implemented) |
| `DELETE` | `/api/v1/projects/{id}` | Delete project |

Interactive documentation is available at `/docs` (Swagger UI) and `/redoc`.

## CI/CD

### CI Pipeline (`.github/workflows/ci.yml`)

Runs on every push/PR to `main` and `develop`:

1. **Lint** — Black, Flake8, mypy (Python 3.12)
2. **Test** — pytest with PostgreSQL + Redis services, coverage upload
3. **Security** — Bandit (SAST) and Safety (dependency audit)
4. **Build** — Docker image builds for backend and frontend
5. **Frontend lint** — ESLint + production build

## Docker

Multi-stage builds produce slim images:

- **Backend** — Python 3.12-slim with GDAL runtime (~400 MB)
- **Frontend** — Nginx-served React build (~50 MB)

Docker Compose services: `postgres` (PostGIS 15), `redis` (7-alpine), `backend`, `frontend`.

Persistent volumes: `postgres_data`, `redis_data`, `upload_data`, `logs`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for coding standards, branch naming, and PR workflow.

```bash
git checkout -b feature/story-X.Y-description
# make changes, then:
pytest && black src/ tests/ && flake8 src/ tests/ && mypy src/
git commit -m "feat: description of changes"
git push origin feature/story-X.Y-description
```

## Documentation

- [Architecture](ARCHITECTURE.md) — system architecture and design decisions
- [Development Guide](docs/development.md) — detailed local setup
- [Deployment Guide](docs/deployment.md) — production deployment
- [Contributing](CONTRIBUTING.md) — contributor guidelines
- [Frontend README](frontend/README.md) — frontend-specific docs
- [FEMA Integration](src/entmoot/integrations/fema/QUICKSTART.md) — FEMA API quickstart

## License

MIT License — see [LICENSE](LICENSE) for details.
