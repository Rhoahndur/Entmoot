# Development Guide

This guide provides detailed instructions for developers working on the Entmoot project.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Project Structure](#project-structure)
3. [Development Environment](#development-environment)
4. [Running Tests](#running-tests)
5. [Code Quality Tools](#code-quality-tools)
6. [Development Workflow](#development-workflow)
7. [Common Tasks](#common-tasks)
8. [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git
- (Optional) PostgreSQL 13+ with PostGIS extension
- (Optional) Docker for containerized development

### Initial Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Entmoot
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   # Install all dependencies including dev tools
   pip install -r requirements-dev.txt

   # OR install package in editable mode
   pip install -e ".[dev]"
   ```

4. **Install pre-commit hooks:**
   ```bash
   pre-commit install
   ```

5. **Verify installation:**
   ```bash
   pytest
   black --check src/
   flake8 src/
   ```

## Project Structure

```
Entmoot/
├── src/
│   └── entmoot/              # Main application package
│       ├── __init__.py       # Package initialization
│       ├── api/              # FastAPI endpoints and routing
│       │   ├── __init__.py
│       │   ├── main.py       # FastAPI app instance (to be created)
│       │   ├── routes/       # API route modules
│       │   └── dependencies/ # Dependency injection
│       ├── core/             # Core business logic
│       │   ├── __init__.py
│       │   ├── geometry/     # Geospatial processing
│       │   ├── analysis/     # Site analysis algorithms
│       │   └── optimization/ # Layout optimization
│       ├── models/           # Data models and schemas
│       │   ├── __init__.py
│       │   ├── domain.py     # Domain models
│       │   └── schemas.py    # Pydantic schemas
│       └── utils/            # Utility functions
│           ├── __init__.py
│           ├── version.py    # Version utilities
│           └── geo_utils.py  # Geospatial utilities
├── tests/                    # Test suite
│   ├── __init__.py
│   ├── test_sample.py        # Sample tests
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── fixtures/             # Test fixtures
├── docs/                     # Documentation
│   ├── development.md        # This file
│   ├── execution-plan.md     # Implementation roadmap
│   └── sprint-status.yaml    # Current sprint status
├── pyproject.toml            # Project configuration
├── requirements.txt          # Production dependencies
├── requirements-dev.txt      # Development dependencies
├── .gitignore               # Git ignore rules
├── .flake8                  # Flake8 configuration
├── .pre-commit-config.yaml  # Pre-commit hooks
├── README.md                # Project overview
└── CONTRIBUTING.md          # Contribution guidelines
```

### Module Responsibilities

#### `src/entmoot/api/`
- FastAPI application and routing
- Request/response handling
- Authentication and authorization
- API documentation

#### `src/entmoot/core/`
- Core business logic
- Geospatial processing algorithms
- Site analysis and optimization
- Domain-specific calculations

#### `src/entmoot/models/`
- Pydantic models for API schemas
- Domain models for business entities
- Database models (when implemented)

#### `src/entmoot/utils/`
- Shared utility functions
- Helper functions
- Common constants and configurations

## Development Environment

### Python Version

The project requires Python 3.10+. We recommend using Python 3.10 or 3.11 for development.

Check your Python version:
```bash
python3 --version
```

### Virtual Environment

Always use a virtual environment to isolate project dependencies:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Deactivate when done
deactivate
```

### Installing Dependencies

```bash
# Production dependencies only
pip install -r requirements.txt

# Development dependencies (includes production)
pip install -r requirements-dev.txt

# Install package in editable mode with dev extras
pip install -e ".[dev]"
```

### IDE Configuration

#### VS Code

Recommended extensions:
- Python (Microsoft)
- Pylance
- Python Test Explorer
- GitLens

Recommended settings (`.vscode/settings.json`):
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.mypyEnabled": true,
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["--line-length=100"],
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
```

#### PyCharm

1. Set Python interpreter to virtual environment
2. Enable black as file watcher or external tool
3. Configure flake8 and mypy as inspections
4. Set pytest as default test runner

## Running Tests

### Basic Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_sample.py

# Run specific test function
pytest tests/test_sample.py::test_get_version

# Run tests matching pattern
pytest -k "version"
```

### Coverage Reporting

```bash
# Run with coverage
pytest --cov=src/entmoot

# Generate HTML coverage report
pytest --cov=src/entmoot --cov-report=html

# Open coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Test Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Exclude slow tests
pytest -m "not slow"

# Run multiple markers
pytest -m "unit or integration"
```

### Test Organization

- **Unit tests**: Fast, isolated tests of individual functions/classes
  - Place in `tests/unit/`
  - Mock external dependencies
  - Target: < 100ms per test

- **Integration tests**: Tests involving multiple components or external systems
  - Place in `tests/integration/`
  - May require database or external services
  - Target: < 1s per test

- **Test fixtures**: Shared test data and setup
  - Place in `tests/fixtures/`
  - Use pytest fixtures for reusability

## Code Quality Tools

### Black (Code Formatter)

Black automatically formats code to ensure consistency.

```bash
# Format all code
black src/ tests/

# Check what would be formatted
black --check src/ tests/

# Format specific file
black src/entmoot/utils/version.py

# Configuration in pyproject.toml
```

Configuration:
- Line length: 100 characters
- Target versions: Python 3.10, 3.11, 3.12

### Flake8 (Linter)

Flake8 checks for code style and potential errors.

```bash
# Run flake8 on all code
flake8 src/ tests/

# Run on specific directory
flake8 src/entmoot/api/

# Show statistics
flake8 --statistics src/

# Configuration in .flake8
```

### Mypy (Type Checker)

Mypy performs static type checking.

```bash
# Run mypy on source code
mypy src/

# Run on specific module
mypy src/entmoot/utils/

# Show error codes
mypy --show-error-codes src/

# Configuration in pyproject.toml
```

### Pre-commit Hooks

Pre-commit automatically runs checks before each commit.

```bash
# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files

# Update hook versions
pre-commit autoupdate

# Skip hooks for a commit (not recommended)
git commit --no-verify
```

## Development Workflow

### Story-Based Development

The project follows a story-based development approach aligned with the execution plan:

1. **Story Structure**: Each story is identified as `X.Y` (e.g., 1.1, 2.3)
   - Wave number (X): Major phase (1-6)
   - Story number (Y): Specific task within wave

2. **Branch Naming**: `feature/story-X.Y-description`
   ```bash
   git checkout -b feature/story-1.2-parcel-boundary-detection
   ```

3. **Development Cycle**:
   - Review story requirements in `docs/execution-plan.md`
   - Create feature branch
   - Write tests first (TDD encouraged)
   - Implement feature
   - Ensure all tests pass
   - Run linters and formatters
   - Commit with descriptive messages
   - Create pull request

### Daily Workflow

1. **Start of day**:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/story-X.Y-description
   ```

2. **During development**:
   ```bash
   # Make changes
   # Run tests frequently
   pytest tests/

   # Format code
   black src/ tests/

   # Check linting
   flake8 src/ tests/

   # Commit regularly
   git add .
   git commit -m "feat: add X functionality"
   ```

3. **Before pushing**:
   ```bash
   # Run all quality checks
   pytest
   black src/ tests/
   flake8 src/ tests/
   mypy src/

   # Push to remote
   git push origin feature/story-X.Y-description
   ```

4. **End of day**:
   ```bash
   # Ensure work is committed and pushed
   git status
   git push origin feature/story-X.Y-description
   ```

## Common Tasks

### Adding a New API Endpoint

1. Create route module in `src/entmoot/api/routes/`
2. Define Pydantic schemas in `src/entmoot/models/schemas.py`
3. Implement business logic in `src/entmoot/core/`
4. Write tests in `tests/integration/api/`
5. Update API documentation

### Adding Geospatial Processing

1. Create module in `src/entmoot/core/geometry/`
2. Use Shapely/GeoPandas for processing
3. Write unit tests with sample geometries
4. Document coordinate systems and projections

### Running Development Server

```bash
# Start FastAPI server (when implemented)
uvicorn entmoot.api.main:app --reload

# Access at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Database Migrations (Future)

```bash
# Initialize Alembic (when implemented)
alembic init alembic

# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Troubleshooting

### Import Errors

**Problem**: Cannot import entmoot modules

**Solution**:
```bash
# Install package in editable mode
pip install -e .

# OR add src/ to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"
```

### GDAL Installation Issues

**Problem**: GDAL fails to install via pip

**Solution**:
```bash
# macOS
brew install gdal
pip install gdal==$(gdal-config --version)

# Ubuntu/Debian
sudo apt-get install gdal-bin libgdal-dev
pip install gdal==$(gdal-config --version)

# Windows
# Download OSGeo4W installer
# Or use conda: conda install gdal
```

### Virtual Environment Activation

**Problem**: Virtual environment not activating

**Solution**:
```bash
# Ensure you created it first
python3 -m venv venv

# Try full path
source /full/path/to/venv/bin/activate

# On Windows, use backslashes
venv\Scripts\activate
```

### Pre-commit Hook Failures

**Problem**: Pre-commit hooks fail on commit

**Solution**:
```bash
# Run hooks manually to see errors
pre-commit run --all-files

# Update hooks
pre-commit autoupdate

# Reinstall hooks
pre-commit uninstall
pre-commit install
```

### Test Failures

**Problem**: Tests fail unexpectedly

**Solution**:
```bash
# Run with verbose output
pytest -vv

# Run specific test
pytest tests/test_sample.py::test_get_version -vv

# Check for missing dependencies
pip install -r requirements-dev.txt

# Clear pytest cache
rm -rf .pytest_cache
pytest --cache-clear
```

### Type Checking Errors

**Problem**: Mypy reports errors in third-party libraries

**Solution**:
- Add library to `ignore_missing_imports` in pyproject.toml
- Install type stubs: `pip install types-<library>`

### Coverage Below Target

**Problem**: Code coverage below 85%

**Solution**:
```bash
# Generate detailed coverage report
pytest --cov=src/entmoot --cov-report=html

# Open report to see uncovered lines
open htmlcov/index.html

# Add tests for uncovered code
# OR add `# pragma: no cover` for untestable code
```

## Next Steps for DEV-2 and DEV-3

Once this foundational setup is complete, other developers can:

1. **DEV-2**: Implement data models and API structure (Story 1.2-1.3)
   - Create Pydantic models
   - Set up FastAPI application
   - Define initial API endpoints

2. **DEV-3**: Implement geospatial utilities (Story 2.1)
   - Add coordinate transformation utilities
   - Implement geometry validation
   - Create geospatial helper functions

3. **All Developers**: Follow the execution plan
   - Reference `docs/execution-plan.md` for story details
   - Check `docs/sprint-status.yaml` for current progress
   - Follow contribution guidelines in `CONTRIBUTING.md`

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Shapely Documentation](https://shapely.readthedocs.io/)
- [GeoPandas Documentation](https://geopandas.org/)
- [pytest Documentation](https://docs.pytest.org/)
- [Black Documentation](https://black.readthedocs.io/)

## Questions or Issues?

- Check existing documentation
- Review `CONTRIBUTING.md`
- Open an issue on GitHub
- Ask in pull request comments

Happy coding!

## Error Handling & Logging

### Error Handling Overview

Entmoot uses a comprehensive error handling framework to ensure consistent error responses and proper error tracking across the entire application.

#### Custom Exception Hierarchy

All custom exceptions inherit from `EntmootException` base class:

```python
from entmoot.core.errors import (
    EntmootException,      # Base exception
    ValidationError,       # Input validation failures (400)
    ParseError,           # KML/KMZ parsing failures (422)
    GeometryError,        # Invalid geometry issues (422)
    CRSError,            # Coordinate system issues (422)
    StorageError,         # File storage issues (500)
    APIError,            # API-specific errors (variable)
    ServiceUnavailableError,  # Service unavailability (503)
    ConfigurationError,   # Configuration issues (500)
)
```

#### Using Custom Exceptions

```python
from entmoot.core.errors import ValidationError, ParseError

# Raise validation error
if not valid_input:
    raise ValidationError(
        message="Invalid file format",
        field="file_type",
        details={"expected": ["kml", "kmz"], "received": "txt"},
        suggestions=["Upload a KML or KMZ file"]
    )

# Raise parse error
try:
    parse_kml(content)
except Exception as e:
    raise ParseError(
        message="Failed to parse KML file",
        file_type="KML",
        line_number=42,
        details={"error": str(e)}
    )
```

#### Error Response Format

All errors follow a standardized JSON format:

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Invalid file format",
  "details": {
    "field": "file_type",
    "expected": ["kml", "kmz"],
    "received": "txt"
  },
  "timestamp": "2025-11-10T15:30:00Z",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "suggestions": [
    "Upload a KML or KMZ file"
  ]
}
```

### Logging Framework

#### Setting Up Logging

Logging is automatically configured on application startup. For manual configuration:

```python
from entmoot.core.logging_config import setup_logging

# Development setup
setup_logging(
    log_level="DEBUG",
    enable_console=True,
)

# Production setup
setup_logging(
    log_level="INFO",
    log_file=Path("/var/log/entmoot/app.log"),
    json_logs=True,  # Use JSON format for log aggregation
    enable_console=True,
)
```

#### Using Loggers

```python
import logging

logger = logging.getLogger(__name__)

# Basic logging
logger.info("Processing upload")
logger.warning("File size exceeds recommended limit")
logger.error("Failed to process file", exc_info=True)

# Logging with context
logger.info(
    "Upload successful",
    extra={
        "upload_id": upload_id,
        "file_size": file_size,
        "duration_ms": 123.45
    }
)
```

#### Logging Decorators

```python
from entmoot.utils.logging import (
    log_function_call,
    log_performance,
    log_async_function_call,
    log_async_performance,
    redact_sensitive,
)

# Log function calls
@log_function_call(log_level=logging.DEBUG)
def process_data(data: dict) -> dict:
    return {"processed": True}

# Log performance
@log_performance(threshold_ms=100)
def slow_operation():
    # Only logged if takes > 100ms
    time.sleep(0.2)

# Async function logging
@log_async_function_call()
async def async_operation():
    await some_async_task()

# Performance tracking for async
@log_async_performance(threshold_ms=50)
async def async_slow_operation():
    await asyncio.sleep(0.1)
```

#### Redacting Sensitive Data

```python
from entmoot.utils.logging import redact_sensitive

# Automatically redacts passwords, API keys, tokens, emails, etc.
data = {
    "username": "john",
    "password": "secret123",
    "api_key": "abc123"
}

safe_data = redact_sensitive(data)
# Result: {"username": "john", "password": "***REDACTED***", "api_key": "***REDACTED***"}

logger.info(f"User data: {redact_sensitive(data)}")
```

#### Performance Monitoring

```python
from entmoot.utils.logging import PerformanceTimer

# Context manager for timing
with PerformanceTimer("database_query"):
    result = db.query(...)
# Automatically logs: "database_query completed in 45.23ms"

# With threshold (only log if slow)
with PerformanceTimer("fast_operation", threshold_ms=100):
    quick_task()  # Not logged if < 100ms
```

#### Request Correlation

All requests automatically get a unique request ID that's tracked through logs:

```python
# In route handlers
from fastapi import Request

async def my_endpoint(request: Request):
    request_id = request.state.request_id
    logger.info(f"Processing request", extra={"request_id": request_id})
```

The request ID is:
- Automatically generated or extracted from `X-Request-ID` header
- Included in all log messages
- Returned in error responses
- Added to response headers

### Retry Mechanism

For handling transient failures:

```python
from entmoot.core.retry import retry, async_retry

# Synchronous retry
@retry(max_attempts=3, base_delay=1.0)
def fetch_external_data():
    response = requests.get("https://api.example.com/data")
    return response.json()

# Async retry
@async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
async def async_fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.example.com/data") as resp:
            return await resp.json()

# Custom retryable exceptions
@retry(
    max_attempts=5,
    retryable_exceptions=(ConnectionError, TimeoutError, CustomTransientError)
)
def unreliable_operation():
    # Will only retry on specified exceptions
    pass

# With retry callback
def on_retry_callback(exc: Exception, attempt: int):
    logger.warning(f"Retry attempt {attempt} after {exc}")

@retry(max_attempts=3, on_retry=on_retry_callback)
def operation_with_callback():
    pass
```

### Best Practices

#### Error Handling

1. **Use specific exceptions**: Choose the most appropriate exception type
   ```python
   # Good
   raise ValidationError("Invalid email format", field="email")
   
   # Avoid
   raise Exception("Invalid email")
   ```

2. **Provide actionable suggestions**: Help users fix the issue
   ```python
   raise ValidationError(
       "File size exceeds limit",
       suggestions=[
           "Reduce file size to under 50MB",
           "Compress the file before uploading"
       ]
   )
   ```

3. **Include context in details**: Add technical information for debugging
   ```python
   raise StorageError(
       "Failed to save file",
       operation="save",
       details={
           "disk_space": disk_space,
           "required": file_size
       }
   )
   ```

#### Logging

1. **Use appropriate log levels**:
   - `DEBUG`: Detailed information for debugging
   - `INFO`: General informational messages
   - `WARNING`: Warning messages (not errors, but noteworthy)
   - `ERROR`: Error messages
   - `CRITICAL`: Critical errors requiring immediate attention

2. **Add context to logs**:
   ```python
   logger.info(
       "File processed successfully",
       extra={
           "upload_id": upload_id,
           "file_type": file_type,
           "duration_ms": duration
       }
   )
   ```

3. **Always redact sensitive data**:
   ```python
   # Use redact_sensitive for user data
   logger.info(f"User details: {redact_sensitive(user_data)}")
   ```

4. **Log exceptions with traceback**:
   ```python
   try:
       risky_operation()
   except Exception as e:
       logger.error("Operation failed", exc_info=True)
       raise
   ```

### Debugging Guide

#### Viewing Logs

Development mode (console):
```bash
# Logs appear in console with colors
python -m uvicorn entmoot.api.main:app --reload
```

Production mode (files):
```bash
# Check log files
tail -f /var/log/entmoot/app.log

# JSON logs can be parsed with jq
tail -f /var/log/entmoot/app.log | jq '.'
```

#### Tracing Requests

Use request IDs to trace a request through the system:

```bash
# Search logs for specific request
grep "550e8400-e29b-41d4-a716-446655440000" /var/log/entmoot/app.log

# With JSON logs
cat /var/log/entmoot/app.log | jq 'select(.request_id == "550e8400-e29b-41d4-a716-446655440000")'
```

#### Common Issues

**Issue: Logs not appearing**
- Check log level configuration
- Verify log handlers are configured
- Check file permissions for log directory

**Issue: Sensitive data in logs**
- Always use `redact_sensitive()` for user data
- Review log output before production
- Configure additional sensitive patterns if needed

**Issue: Performance problems**
- Use `@log_performance` decorators to identify slow operations
- Check `duration_ms` fields in logs
- Adjust `threshold_ms` to focus on slowest operations

### Adding New Error Types

To add a new custom exception:

1. **Define the exception in `src/entmoot/core/errors.py`**:
   ```python
   class MyNewError(EntmootException):
       """Description of when this error occurs."""
       
       def __init__(
           self,
           message: str,
           custom_field: Optional[str] = None,
           details: Optional[Dict[str, Any]] = None,
           suggestions: Optional[List[str]] = None,
       ):
           error_details = details or {}
           if custom_field:
               error_details["custom_field"] = custom_field
           
           super().__init__(
               message=message,
               error_code="MY_NEW_ERROR",
               status_code=400,  # Choose appropriate status code
               details=error_details,
               suggestions=suggestions or ["Default suggestion"]
           )
   ```

2. **Register with error handlers** (if needed):
   Error handlers automatically catch all `EntmootException` subclasses.

3. **Add tests** in `tests/test_errors.py`:
   ```python
   def test_my_new_error():
       exc = MyNewError("Test error", custom_field="value")
       assert exc.error_code == "MY_NEW_ERROR"
       assert exc.status_code == 400
   ```

4. **Update documentation**: Add the new error type to this guide.

