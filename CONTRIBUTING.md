# Contributing to Entmoot

Thank you for your interest in contributing to Entmoot! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Collaborate openly and transparently

## Getting Started

### 1. Set Up Your Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd Entmoot

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### 2. Verify Your Setup

```bash
# Run tests to ensure everything works
pytest

# Run linters
black src/ tests/
flake8 src/ tests/
mypy src/
```

## Development Workflow

### Branching Strategy

We use a feature-branch workflow:

- **main**: Production-ready code. All code here should be stable and tested.
- **feature/story-X.Y-description**: Feature branches for new functionality
  - Example: `feature/story-1.2-parcel-boundary-detection`
- **fix/description**: Bug fixes
  - Example: `fix/incorrect-setback-calculation`
- **hotfix/description**: Emergency production fixes
  - Example: `hotfix/api-authentication-error`

### Creating a Feature Branch

```bash
# Update main branch
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/story-X.Y-short-description

# Make your changes...

# Commit regularly with meaningful messages
git add .
git commit -m "feat: add parcel boundary detection"

# Push to remote
git push origin feature/story-X.Y-short-description
```

## Commit Message Guidelines

We follow conventional commit format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, no logic change)
- **refactor**: Code refactoring
- **test**: Adding or updating tests
- **chore**: Maintenance tasks

### Examples

```bash
feat(api): add endpoint for parcel boundary upload

Add POST /api/v1/parcels endpoint to handle parcel boundary
shapefile uploads. Includes validation and PostGIS storage.

Closes #123
```

```bash
fix(core): correct setback calculation for irregular polygons

Previously, setback calculation failed on non-convex polygons.
Updated algorithm to handle all polygon types correctly.
```

## Code Quality Standards

### Python Style Guide

- Follow PEP 8 style guidelines
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use meaningful variable and function names

### Code Formatting

We use **black** for automatic code formatting:

```bash
# Format all code
black src/ tests/

# Check what would be formatted
black --check src/ tests/
```

### Linting

We use **flake8** for linting:

```bash
# Run flake8
flake8 src/ tests/

# Configuration is in .flake8 file
```

### Type Checking

We use **mypy** for static type checking:

```bash
# Run mypy
mypy src/

# Configuration is in pyproject.toml
```

### Pre-commit Hooks

Pre-commit hooks automatically run before each commit:

- Trailing whitespace removal
- End-of-file fixer
- YAML/JSON/TOML validation
- Black formatting
- Flake8 linting
- Mypy type checking
- Import sorting (isort)
- Security checks (bandit)

```bash
# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

## Testing Guidelines

### Writing Tests

- Write tests for all new features
- Aim for 85%+ code coverage
- Use descriptive test names
- Follow AAA pattern: Arrange, Act, Assert

```python
def test_calculate_setback_for_residential_zone() -> None:
    """Test setback calculation for residential zoning."""
    # Arrange
    parcel = create_test_parcel()
    zone_type = ZoneType.RESIDENTIAL

    # Act
    setback = calculate_setback(parcel, zone_type)

    # Assert
    assert setback == 15.0
    assert isinstance(setback, float)
```

### Test Organization

- `tests/`: Root test directory
- `tests/unit/`: Unit tests (fast, isolated)
- `tests/integration/`: Integration tests (slower, external dependencies)
- `tests/fixtures/`: Shared test fixtures and data

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/entmoot --cov-report=html

# Run specific tests
pytest tests/test_sample.py
pytest tests/unit/

# Run tests with markers
pytest -m unit          # Only unit tests
pytest -m integration   # Only integration tests
pytest -m "not slow"    # Exclude slow tests

# Run tests in parallel (install pytest-xdist)
pytest -n auto
```

### Test Markers

Use markers to categorize tests:

```python
import pytest

@pytest.mark.unit
def test_simple_calculation() -> None:
    """Fast unit test."""
    assert 1 + 1 == 2

@pytest.mark.integration
def test_database_integration() -> None:
    """Integration test with database."""
    # Test with actual database
    pass

@pytest.mark.slow
def test_large_dataset_processing() -> None:
    """Slow test with large dataset."""
    # Process large file
    pass
```

## Pull Request Process

### Before Creating a PR

1. **Ensure all tests pass**
   ```bash
   pytest
   ```

2. **Ensure code is formatted**
   ```bash
   black src/ tests/
   ```

3. **Ensure linters pass**
   ```bash
   flake8 src/ tests/
   mypy src/
   ```

4. **Update documentation** if needed

5. **Add tests** for new functionality

### Creating a Pull Request

1. Push your feature branch to GitHub
2. Create a pull request from your branch to `main`
3. Fill out the PR template with:
   - Description of changes
   - Related issue numbers
   - Testing performed
   - Screenshots (if UI changes)

### PR Title Format

```
<type>(<scope>): <short description>
```

Examples:
- `feat(api): add parcel upload endpoint`
- `fix(core): correct setback calculation`
- `docs(readme): update installation instructions`

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Related Issues
Closes #123
Relates to #456

## Changes Made
- Added X feature
- Fixed Y bug
- Updated Z documentation

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed
- [ ] All tests pass locally

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added for new functionality
- [ ] All tests pass
- [ ] No new warnings introduced
```

### Review Process

1. At least one approval required before merging
2. All CI checks must pass
3. No unresolved conversations
4. Branch must be up to date with main

### After PR is Merged

1. Delete your feature branch
2. Pull latest main
   ```bash
   git checkout main
   git pull origin main
   ```

## Documentation

### Code Documentation

- Use docstrings for all modules, classes, and functions
- Follow Google-style docstring format

```python
def calculate_setback(parcel: Polygon, zone_type: ZoneType) -> float:
    """
    Calculate the required setback for a parcel based on zoning.

    Args:
        parcel: The parcel geometry as a Shapely Polygon.
        zone_type: The zoning type for the parcel.

    Returns:
        The required setback distance in feet.

    Raises:
        ValueError: If parcel is invalid or zone_type is unsupported.

    Example:
        >>> parcel = Polygon([...])
        >>> setback = calculate_setback(parcel, ZoneType.RESIDENTIAL)
        >>> print(setback)
        15.0
    """
    # Implementation
    pass
```

### Project Documentation

- Update README.md for user-facing changes
- Update docs/development.md for developer-facing changes
- Add inline comments for complex logic

## Development Tips

### Setting Up IDE

**VS Code** (recommended):
```json
{
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.mypyEnabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "python.testing.pytestEnabled": true
}
```

**PyCharm**:
- Enable black as external tool
- Configure flake8 and mypy inspections
- Set pytest as default test runner

### Debugging

```bash
# Run pytest with debugging
pytest --pdb

# Run specific test with print statements
pytest -s tests/test_sample.py::test_get_version
```

### Common Issues

**Import errors**: Ensure you've installed the package in editable mode:
```bash
pip install -e .
```

**Type checking errors**: Check mypy configuration in pyproject.toml

**Pre-commit hooks failing**: Run hooks manually to see detailed errors:
```bash
pre-commit run --all-files
```

## Getting Help

- Open an issue for bugs or feature requests
- Ask questions in pull request comments
- Review existing documentation in `docs/`

## Recognition

Contributors will be recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project documentation

Thank you for contributing to Entmoot!
