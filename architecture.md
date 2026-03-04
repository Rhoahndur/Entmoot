# Architecture

System architecture for Entmoot — an AI-driven site layout automation platform.

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend                          │
│  UploadPage → ConfigPage → ResultsPage → ProjectsListPage  │
│  MapViewer (MapLibre GL) · LayoutEditor · ResultsDashboard  │
└──────────────────────────┬──────────────────────────────────┘
                           │  HTTP / REST (Axios)
                           │  X-API-Key header (when auth enabled)
┌──────────────────────────▼──────────────────────────────────┐
│                      FastAPI Backend                         │
│                                                              │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ API      │  │ Services     │  │ Core Modules           │  │
│  │ Routes   │→ │ project_svc  │→ │ parsers · crs · terrain│  │
│  │ auth.py  │  │ optim_svc    │  │ optimization · roads   │  │
│  │ upload   │  │              │  │ earthwork · constraints│  │
│  │ projects │  │              │  │ export · visualization │  │
│  └──────────┘  └──────────────┘  └───────────────────────┘  │
│                                                              │
│  ┌─────────────────┐  ┌──────────────────────────────────┐  │
│  │ Integrations    │  │ Infrastructure                    │  │
│  │ FEMA · USGS     │  │ Redis storage · File storage     │  │
│  │ rate_limiter    │  │ Cleanup service · Logging/Middleware│
│  └─────────────────┘  └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
    │  Redis  │         │  Disk   │         │ External│
    │ project │         │ uploads │         │  APIs   │
    │ results │         │ exports │         │FEMA/USGS│
    └─────────┘         └─────────┘         └─────────┘
```

---

## Request Lifecycle

A typical project creation flows through:

```
Client POST /api/v1/projects
  │
  ├─ RequestCorrelationMiddleware  → assigns X-Request-ID
  ├─ LoggingContextMiddleware      → injects request context into logs
  ├─ verify_api_key dependency     → validates X-API-Key (if auth enabled)
  │
  ▼
projects.py  create_project()
  ├─ ProjectService.validate_weights()
  ├─ Store project in Redis
  └─ asyncio.create_task(generate_layout_async)
       │
       ▼  (background, ThreadPoolExecutor)
  optimization_service.py  run_optimization_sync()
       ├─ Parse file (KML / KMZ / GeoJSON)
       ├─ Detect CRS → transform to UTM
       ├─ Build Asset instances from config
       ├─ Set up constraints + objectives
       ├─ Run GeneticOptimizer (GA)
       ├─ Inverse-transform results → WGS84
       ├─ Generate road network (A* pathfinding)
       ├─ Calculate earthwork (cut/fill)
       └─ Store LayoutResults in Redis

Client GET /api/v1/projects/{id}/results
  │
  ▼
projects.py  get_layout_results()
  └─ ProjectService.build_optimization_results()
       ├─ Assemble road network + intersections
       ├─ Detect constraint violations
       ├─ Compute constraint zones (setback buffer)
       ├─ Compute buildable areas (boundary minus setback)
       ├─ Calculate cost breakdown + metrics
       └─ Return OptimizationResults
```

---

## Layer Responsibilities

### API Layer (`src/entmoot/api/`)

Thin HTTP handlers. No business logic — delegates to services.

| File | Responsibility |
|---|---|
| `main.py` | App factory, CORS, lifespan (startup/shutdown), middleware registration, health check |
| `projects.py` | Project CRUD, status polling, results retrieval, re-optimization, export, delete |
| `upload.py` | Multipart file upload with validation (extension, MIME, magic bytes, size) |
| `auth.py` | `verify_api_key` — FastAPI `Security` dependency using `APIKeyHeader("X-API-Key")` |
| `middleware.py` | `RequestCorrelationMiddleware` (X-Request-ID), `LoggingContextMiddleware` (context injection) |
| `error_handlers.py` | Maps `EntmootException` subclasses, Pydantic errors, and unhandled exceptions to JSON responses |

### Service Layer (`src/entmoot/services/`)

Business logic extracted from routes — testable without HTTP.

| File | Responsibility |
|---|---|
| `project_service.py` | Weight validation, result assembly, constraint violation detection, road intersection computation, setback zone / buildable area geometry |
| `optimization_service.py` | `generate_layout_async` (background task), `run_optimization_sync` (file parsing → CRS → GA → road gen → earthwork → results) |

### Core Modules (`src/entmoot/core/`)

Domain-specific processing engines.

| Module | What it does |
|---|---|
| `parsers/` | KML/KMZ parsing and validation; coordinate/geometry extraction |
| `crs/` | CRS detection from file content, UTM zone selection, coordinate transformation (PyProj) |
| `terrain/` | DEM loading/validation, slope calculation, aspect analysis, solar/wind exposure, buildability scoring |
| `constraints/` | Setback buffers, exclusion zones, regulatory constraints; spatial validation with Shapely |
| `optimization/` | `GeneticOptimizer` — population-based multi-objective optimization with collision detection, tournament selection, elitism, convergence detection |
| `roads/` | Graph-based road network, A\* pathfinding with grade constraints and turning-radius awareness |
| `earthwork/` | Pre/post-grading models, cut/fill volume calculation, cost estimation |
| `export/` | `KMZExporter`, `GeoJSONExporter`, `DXFExporter` — georeferenced output for Google Earth, QGIS, AutoCAD |
| `reports/` | PDF site report generation (ReportLab) |
| `visualization/` | 2D (Matplotlib) and 3D (Plotly) map rendering with multi-layer support |
| `config.py` | Pydantic `Settings` with `ENTMOOT_` env prefix; CORS validation (rejects `*` in production) |
| `redis_storage.py` | `RedisStorage` singleton — project/result persistence with in-memory fallback when Redis is unavailable |
| `storage.py` | `FileStorageService` — atomic file writes, metadata sidecar JSON, directory-per-upload |
| `cleanup.py` | Background async loop that deletes expired uploads (skips in-progress files) |
| `logging_config.py` | `JSONFormatter` (production), `ColoredFormatter` (dev), rotating file handler |

### Integrations (`src/entmoot/integrations/`)

Rate-limited async HTTP clients for external data sources.

| Module | API | Data |
|---|---|---|
| `fema/` | FEMA NFHL REST API | Flood zone designations by point or bounding box |
| `usgs/` | USGS EPQS / 3DEP | Point elevation, batch queries, DEM tile download & mosaic |
| `rate_limiter.py` | *(shared)* | Token-bucket `RateLimiter` with `wait_if_needed()` async convenience method |

### Models (`src/entmoot/models/`)

Pydantic v2 data models — serialization boundary between layers.

| File | Key types |
|---|---|
| `project.py` | `ProjectConfig`, `ProjectStatus`, `LayoutResults`, `OptimizationResults`, `PlacedAsset`, `RoadSegment`, `ConstraintViolation`, `CostBreakdown` |
| `assets.py` | `BuildingAsset`, `ParkingLotAsset`, `EquipmentYardAsset`, `StorageTankAsset` |
| `boundary.py` | `PropertyBoundary`, `SubParcel`, geometry metrics |
| `constraints.py` | `SetbackConstraint`, `ExclusionZoneConstraint`, `RegulatoryConstraint` |
| `terrain.py` | `DEMData`, `DEMMetadata`, `DEMValidationResult` |
| `elevation.py` | `ElevationPoint`, `ElevationQuery`, `DEMTileMetadata` |
| `regulatory.py` | `FloodplainData`, `FloodZone` |
| `upload.py` | `UploadMetadata`, `UploadResponse`, `FileType` |
| `errors.py` | `ErrorResponse`, custom exception hierarchy |

---

## Optimization Engine

```
                    ┌─────────────────────┐
                    │  GeneticOptimizer    │
                    │  (genetic_algorithm) │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                     ▼
  ┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐
  │ Initialization│  │ Selection       │  │ Variation        │
  │ Random / Grid │  │ Tournament (k=3)│  │ Crossover (0.7)  │
  │ / Heuristic   │  │ Elitism (15%)   │  │ Mutation (0.4)   │
  └───────────────┘  └─────────────────┘  └──────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Fitness Evaluation   │
                    │  OptimizationObj     │
                    │  (multi-objective)   │
                    └──────────┬──────────┘
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                     ▼
  ┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐
  │ Cut/fill cost │  │ Accessibility   │  │ Compactness      │
  │ weight        │  │ weight          │  │ weight           │
  └───────────────┘  └─────────────────┘  └──────────────────┘
          ▼                    ▼                     ▼
  ┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐
  │ Road length   │  │ Slope variance  │  │ Collision detect │
  │ weight        │  │ weight          │  │ (Shapely)        │
  └───────────────┘  └─────────────────┘  └──────────────────┘
```

**Configurable parameters:** population size (50), generations (150), time limit (120 s), convergence patience (20), diversity weight (0.2).

**Output:** Best solution + diverse alternatives, convergence history, generation metadata.

---

## Frontend Architecture

```
┌──────────────────────────────────────────────────────────┐
│                       React 19 + Vite                     │
│                                                           │
│  Pages                         Components                 │
│  ┌────────────┐               ┌──────────────────┐       │
│  │ UploadPage │──FileDropzone─│ FileDropzone     │       │
│  │ ConfigPage │               │ (drag & drop)    │       │
│  │ ResultsPage│──MapViewer────│ MapViewer        │       │
│  │ ProjectsList               │ (MapLibre GL)    │       │
│  └────────────┘               ├──────────────────┤       │
│                               │ LayoutEditor     │       │
│  Hooks                        │ (move/rotate/    │       │
│  ┌──────────────┐             │  undo/redo)      │       │
│  │useFileUpload │             ├──────────────────┤       │
│  └──────────────┘             │ ResultsDashboard │       │
│                               │ (Recharts)       │       │
│  API Client (Axios)           │ cost pie chart   │       │
│  ┌──────────────┐             │ earthwork bars   │       │
│  │ X-API-Key    │             │ asset table      │       │
│  │ interceptor  │             └──────────────────┘       │
│  └──────────────┘                                        │
└──────────────────────────────────────────────────────────┘
```

**MapViewer layers:** property boundary (red polygon), asset footprints (colored by type), constraint zones, buildable areas, road network (multi-layer: border + surface + centerline), measurement tool (Haversine), shift+drag asset repositioning, screenshot export.

**LayoutEditor:** select asset → move / rotate (±5°, ±15°, slider) / delete. Full undo/redo history. Violation overlay per asset. Unsaved-changes tracking.

**ResultsDashboard:** property metrics, cost breakdown (pie), earthwork volumes (bar), optimization score (0–100), constraint compliance, asset distribution by type, road network summary, alternative comparison, export buttons (PDF / KMZ / GeoJSON / DXF).

---

## Data Storage

```
┌──────────────┐     ┌──────────────────────────────────┐
│    Redis     │     │         Disk (FileStorage)        │
│              │     │                                    │
│  project:*   │     │  data/uploads/{uuid}/             │
│  → config    │     │    ├── original_file.kmz          │
│  → status    │     │    └── metadata.json              │
│  → progress  │     │                                    │
│  → boundary  │     │  Atomic writes (temp → rename)    │
│  → bounds    │     │  Auto-cleanup of expired uploads   │
│              │     │                                    │
│  results:*   │     └──────────────────────────────────┘
│  → assets    │
│  → roads     │     Fallback: in-memory dicts when
│  → earthwork │     Redis is unavailable
│  → costs     │
└──────────────┘
```

Redis is the primary store for project state and optimization results. The `FileStorageService` handles raw uploaded files on disk with JSON sidecar metadata. A background `CleanupService` removes expired uploads (configurable retention, skips in-progress files).

---

## Authentication

```
Request
  │
  ├─ ENTMOOT_AUTH_ENABLED=false  →  pass through (no-op)
  ├─ ENTMOOT_API_KEYS=""         →  pass through (no keys configured)
  │
  └─ auth enabled + keys set
       ├─ X-API-Key header matches  →  allow
       └─ missing / invalid         →  401 Unauthorized
```

Public routes (`/`, `/health`, `/docs`, `/redoc`, `/openapi.json`) are excluded — auth is applied only to `/api/v1` router prefixes.

---

## Infrastructure

### Docker

Multi-stage builds:

| Image | Base | Size |
|---|---|---|
| Backend | `python:3.10-slim` + GDAL runtime | ~400 MB |
| Frontend | `nginx:alpine` serving Vite build | ~50 MB |

### Docker Compose Services

| Service | Image | Purpose |
|---|---|---|
| `postgres` | `postgis/postgis:15-3.4-alpine` | Spatial database (optional) |
| `redis` | `redis:7-alpine` | Project/result persistence |
| `backend` | Custom Dockerfile | FastAPI application |
| `frontend` | Custom Dockerfile | React SPA via Nginx |

### CI/CD (GitHub Actions)

| Job | What it does |
|---|---|
| **lint** | Black + Flake8 + mypy (enforced) across Python 3.10–3.12 |
| **test** | pytest with PostgreSQL + Redis services, coverage upload |
| **security** | Bandit (SAST) + Safety (dependency audit) |
| **build** | Docker image builds for backend + frontend |
| **frontend-lint** | ESLint + production build |
| **openapi-check** | Regenerates `docs/openapi.yaml` and `git diff --exit-code` |
| **deploy** | Staging (develop branch), production (release tags), auto-rollback |

### Observability

- **Request correlation** — `X-Request-ID` header propagated through all logs
- **Structured logging** — JSON in production (`JSONFormatter`), colored console in development
- **Rotating log files** — 10 MB per file, 5 backups
- **Error tracking** — Centralized `ErrorResponse` model with error codes, suggestions, and request IDs

---

## Mermaid Diagram

```mermaid
graph TB
    subgraph "Frontend (React 19 + Vite)"
        Upload[UploadPage]
        Config[ConfigPage]
        Results[ResultsPage]
        Projects[ProjectsListPage]
        MapView[MapViewer<br/>MapLibre GL]
        LayoutEd[LayoutEditor]
        Dashboard[ResultsDashboard<br/>Recharts]
    end

    subgraph "API Layer (FastAPI)"
        Auth[auth.py<br/>X-API-Key]
        UploadAPI[upload.py]
        ProjectsAPI[projects.py]
        Middleware[Middleware<br/>correlation · logging]
        ErrorH[Error Handlers]
    end

    subgraph "Service Layer"
        ProjSvc[ProjectService<br/>validation · results · violations]
        OptSvc[OptimizationService<br/>layout generation]
    end

    subgraph "Core Modules"
        Parsers[Parsers<br/>KML · KMZ · GeoJSON]
        CRS[CRS<br/>detection · UTM transform]
        Terrain[Terrain<br/>DEM · slope · aspect]
        Constraints[Constraints<br/>setbacks · buffers · zones]
        GA[GeneticOptimizer<br/>multi-objective GA]
        Roads[Roads<br/>graph · A* pathfinding]
        Earthwork[Earthwork<br/>cut/fill · cost]
        ExportMod[Export<br/>KMZ · GeoJSON · DXF]
        Viz[Visualization<br/>2D · 3D maps]
        Reports[Reports<br/>PDF generation]
    end

    subgraph "Integrations"
        RateLim[RateLimiter<br/>token bucket]
        FEMA[FEMA Client<br/>flood zones]
        USGS[USGS Client<br/>elevation · DEM tiles]
    end

    subgraph "Storage"
        Redis[(Redis<br/>projects · results)]
        Disk[(Disk<br/>uploads · exports)]
    end

    Upload -->|HTTP| Auth
    Config -->|HTTP| Auth
    Results -->|HTTP| Auth
    Projects -->|HTTP| Auth

    Auth --> UploadAPI
    Auth --> ProjectsAPI
    UploadAPI --> Disk
    ProjectsAPI --> ProjSvc
    ProjectsAPI --> OptSvc

    ProjSvc --> Redis
    OptSvc --> Parsers
    OptSvc --> CRS
    OptSvc --> GA
    OptSvc --> Roads
    OptSvc --> Earthwork
    OptSvc --> Redis

    GA --> Constraints
    GA --> Terrain
    Constraints --> FEMA
    Terrain --> USGS
    FEMA --> RateLim
    USGS --> RateLim

    Results --> MapView
    Results --> LayoutEd
    Results --> Dashboard

    classDef frontend fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef api fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef service fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    classDef core fill:#fff8e1,stroke:#f57f17,stroke-width:2px
    classDef integration fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef storage fill:#f3e5f5,stroke:#4a148c,stroke-width:2px

    class Upload,Config,Results,Projects,MapView,LayoutEd,Dashboard frontend
    class Auth,UploadAPI,ProjectsAPI,Middleware,ErrorH api
    class ProjSvc,OptSvc service
    class Parsers,CRS,Terrain,Constraints,GA,Roads,Earthwork,ExportMod,Viz,Reports core
    class RateLim,FEMA,USGS integration
    class Redis,Disk storage
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **Service layer between routes and core** | Keeps route handlers thin (~5 lines each); business logic is testable without HTTP |
| **Redis with in-memory fallback** | Works in production (Redis) and local dev (dict fallback) without config changes |
| **Genetic algorithm over linear solver** | Multi-objective spatial optimization with irregular constraints doesn't fit LP/MIP well; GA handles arbitrary fitness functions and produces diverse alternatives |
| **CRS auto-detection + UTM projection** | Users upload in WGS84 (lat/lon); optimization runs in meters (UTM); results inverse-transform back to WGS84 |
| **Shared RateLimiter** | FEMA and USGS clients had identical token-bucket implementations; extracted to single async-compatible module |
| **Background ThreadPoolExecutor for optimization** | CPU-bound GA must not block the async event loop; wraps sync code in a thread |
| **Optional API key auth** | Disabled by default in development; enabled in production via env vars |
| **Atomic file writes** | Upload files written to temp path then renamed — prevents partial files on crash |
