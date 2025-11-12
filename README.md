# Entmoot

AI-driven site layout automation for real estate due diligence.

## Overview

Entmoot is a geospatial analysis platform designed to automate site layout generation and feasibility analysis for real estate development projects. The system combines geospatial processing, regulatory compliance checking, and AI-driven optimization to streamline the due diligence process.

## Features

- Automated site boundary detection and analysis
- Setback and zoning compliance verification
- Building footprint optimization
- Parking layout generation
- Access and circulation planning
- Multi-unit site layout automation

## Technology Stack

- **Backend**: FastAPI (Python 3.10+)
- **Frontend**: React 19 with TypeScript, Vite, TailwindCSS
- **Geospatial**: GDAL, Shapely, GeoPandas, PyProj, MapLibre GL
- **Database**: PostGIS (PostgreSQL with spatial extensions)
- **Cache**: Redis
- **Testing**: pytest with coverage reporting
- **Code Quality**: black, flake8, mypy, pre-commit hooks
- **Containerization**: Docker, Docker Compose
- **CI/CD**: GitHub Actions

## Prerequisites

### For Docker (Recommended)
- Docker 20.10+
- Docker Compose v2.0+

### For Local Development
- Python 3.10 or higher
- Node.js 18+
- pip (Python package manager)
- npm or yarn
- Git
- (Optional) PostgreSQL with PostGIS extension
- (Optional) Redis

## Quick Start with Docker

The easiest way to run Entmoot is using Docker Compose. This will start all services (backend, frontend, database, cache) with a single command.

### 1. Clone and Configure

```bash
git clone <repository-url>
cd Entmoot

# Copy environment configuration
cp .env.example .env

# Edit .env file with your settings (use secure passwords in production!)
```

### 2. Start Services

```bash
# Production mode
docker compose up -d

# Development mode (with hot reload)
docker compose -f docker-compose.dev.yml up -d
```

### 3. Access the Application

- Frontend: http://localhost
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### 4. Stop Services

```bash
docker compose down

# Remove volumes (WARNING: deletes all data)
docker compose down -v
```

## Local Development Setup

For local development without Docker:

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Entmoot
```

### 2. Backend Setup

#### Create a Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

#### Install Backend Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies (for contributors)
pip install -r requirements-dev.txt

# Or install the package in editable mode with dev dependencies
pip install -e ".[dev]"
```

#### Install Pre-commit Hooks (Optional, for Contributors)

```bash
pre-commit install
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

### 4. Database Setup (Optional)

If using PostgreSQL locally:

```bash
# Create database
createdb entmoot

# Enable PostGIS extension
psql -d entmoot -c "CREATE EXTENSION postgis;"
```

## Project Structure

```
Entmoot/
├── src/
│   └── entmoot/              # Main application package
│       ├── api/              # FastAPI endpoints
│       ├── core/             # Core business logic
│       ├── models/           # Data models and schemas
│       ├── integrations/     # External API integrations
│       └── utils/            # Utility functions
├── frontend/                 # React frontend application
│   ├── src/                  # Frontend source code
│   ├── public/               # Static assets
│   ├── Dockerfile            # Frontend Docker image
│   └── nginx.conf            # Nginx configuration
├── tests/                    # Backend test suite
├── docs/                     # Documentation
├── .github/
│   └── workflows/            # CI/CD pipelines
│       ├── ci.yml            # Continuous Integration
│       └── deploy.yml        # Deployment workflow
├── Dockerfile                # Backend Docker image
├── docker-compose.yml        # Production Docker setup
├── docker-compose.dev.yml    # Development Docker setup
├── .dockerignore            # Docker ignore rules
├── .env.example             # Environment variables template
├── pyproject.toml           # Project configuration
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies
├── .gitignore               # Git ignore rules
├── .flake8                  # Flake8 configuration
├── .pre-commit-config.yaml  # Pre-commit hooks
└── README.md                # This file
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=src/entmoot --cov-report=html

# Run specific test file
pytest tests/test_sample.py

# Run tests with specific marker
pytest -m unit
```

### Code Quality

```bash
# Format code with black
black src/ tests/

# Check code style with flake8
flake8 src/ tests/

# Type checking with mypy
mypy src/

# Run all pre-commit hooks
pre-commit run --all-files
```

### Running the Application

#### With Docker (Recommended)

```bash
# Development mode with hot reload
docker compose -f docker-compose.dev.yml up

# Production mode
docker compose up
```

#### Local Development

```bash
# Start backend
uvicorn entmoot.api.main:app --reload

# In a separate terminal, start frontend
cd frontend
npm run dev

# The frontend will be available at http://localhost:5173
# Backend API at http://localhost:8000
# API documentation at http://localhost:8000/docs
```

## Testing

The project uses pytest for testing with the following features:

- Unit tests marked with `@pytest.mark.unit`
- Integration tests marked with `@pytest.mark.integration`
- Code coverage targeting 85%+ coverage
- Coverage reports in HTML, XML, and terminal formats

### Test Organization

- `tests/`: All test files
- `tests/test_sample.py`: Sample tests demonstrating framework setup

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

### Development Workflow

1. Create a feature branch from `main`
   ```bash
   git checkout -b feature/story-X.Y-description
   ```

2. Make your changes and ensure tests pass
   ```bash
   pytest
   black src/ tests/
   flake8 src/ tests/
   ```

3. Commit your changes
   ```bash
   git add .
   git commit -m "feat: description of changes"
   ```

4. Push to your branch and create a pull request
   ```bash
   git push origin feature/story-X.Y-description
   ```

## Git Workflow

- **main**: Production-ready code
- **feature/story-X.Y-description**: Feature branches for development
- **hotfix/description**: Emergency fixes for production issues

All changes should go through pull request review before merging to main.

## Docker

### Docker Images

The project includes optimized multi-stage Docker builds:

- **Backend**: Python 3.10 slim with GDAL/PostGIS support (~400MB)
- **Frontend**: Nginx-served React app (~50MB)

### Docker Compose Services

- **postgres**: PostgreSQL 15 with PostGIS 3.4
- **redis**: Redis 7 for caching
- **backend**: FastAPI application
- **frontend**: React application with Nginx

### Environment Variables

See `.env.example` for all available configuration options:

```bash
cp .env.example .env
# Edit .env with your settings
```

Important variables:
- `POSTGRES_PASSWORD`: Database password (change in production!)
- `REDIS_PASSWORD`: Redis password (change in production!)
- `SECRET_KEY`: Application secret key (generate a strong random string)
- `CORS_ORIGINS`: Allowed origins for CORS

### Health Checks

All services include health checks:

```bash
# Check service health
docker compose ps

# View logs
docker compose logs -f backend
docker compose logs -f frontend
```

### Data Persistence

Volumes are used for data persistence:
- `postgres_data`: Database files
- `redis_data`: Redis persistence
- `upload_data`: User uploads
- `logs`: Application logs

## CI/CD

### GitHub Actions Workflows

The project includes automated CI/CD pipelines:

#### CI Pipeline (`.github/workflows/ci.yml`)
Runs on every push and pull request:
- Code quality checks (Black, Flake8, MyPy)
- Unit tests with coverage
- Security scanning (Bandit, Safety)
- Docker image builds
- Frontend linting and build

#### Deployment Pipeline (`.github/workflows/deploy.yml`)
Runs on releases:
- Builds and pushes Docker images to registry
- Deploys to staging (on develop branch)
- Deploys to production (on release tags)
- Automated rollback on failure

### Required Secrets

Configure these secrets in your GitHub repository:
- `DOCKER_USERNAME`: Docker Hub username
- `DOCKER_PASSWORD`: Docker Hub password/token
- `STAGING_HOST`: Staging server hostname
- `STAGING_USER`: SSH user for staging
- `STAGING_SSH_KEY`: SSH private key for staging
- `PRODUCTION_HOST`: Production server hostname
- `PRODUCTION_USER`: SSH user for production
- `PRODUCTION_SSH_KEY`: SSH private key for production
- `SLACK_WEBHOOK`: (Optional) Slack webhook for notifications

## Documentation

- [Development Guide](docs/development.md) - Detailed development instructions
- [Execution Plan](docs/execution-plan.md) - Project roadmap and implementation plan
- [Architecture](architecture.md) - System architecture overview
- [Frontend Quickstart](QUICKSTART_FRONTEND.md) - Frontend development guide

## License

MIT License - See LICENSE file for details

## Contact

For questions or support, please open an issue on GitHub.

## Acknowledgments

- Built with FastAPI and modern Python geospatial tools
- Inspired by the need to streamline real estate due diligence workflows
