# Testing and Development Guide

This document explains how to set up the development environment, run tests, and use linting tools for the WiFi Geolocation custom component.

## Development Setup

### Install Dependencies

```bash
# Install test dependencies
pip install -r requirements_test.txt

# Or using uv (faster)
uv pip install -r requirements_test.txt
```

### Install Pre-commit Hooks (Optional)

Pre-commit hooks automatically run linters before each commit:

```bash
pre-commit install
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Tests with Coverage

```bash
pytest --cov=custom_components.wifi_geolocation --cov-report=term-missing
```

### Run Specific Test File

```bash
pytest tests/test_config_flow.py
pytest tests/test_init.py
```

### Run with Verbose Output

```bash
pytest -v
```

## Linting

### Ruff (Formatter and Linter)

**Check for issues:**
```bash
ruff check .
```

**Auto-fix issues:**
```bash
ruff check --fix .
```

**Format code:**
```bash
ruff format .
```

### MyPy (Type Checking)

**Check types in source code:**
```bash
mypy .
```

Note: MyPy is configured to exclude tests from strict type checking.

### Run All Linters

```bash
# Check everything
ruff check .
mypy .

# Fix auto-fixable issues
ruff check --fix .
ruff format .
```

## Pre-commit

Pre-commit runs all configured linters automatically before each commit.

**Install hooks:**
```bash
pre-commit install
```

**Run manually on all files:**
```bash
pre-commit run --all-files
```

**Run on staged files only:**
```bash
pre-commit run
```

## Code Quality Standards

This component follows Home Assistant's code quality standards:

- **Code style**: Enforced by Ruff
- **Type hints**: Required for all functions and methods (checked by MyPy)
- **Test coverage**: Minimum 95% coverage required
- **Docstrings**: Required for all public functions, classes, and methods
- **Import sorting**: Enforced by Ruff (isort integration)

## Test Structure

```
tests/
├── __init__.py           # Test package marker
├── conftest.py          # Shared fixtures and test data
├── test_config_flow.py  # Config flow tests
└── test_init.py         # Integration tests
```

### Test Fixtures

Common fixtures are defined in `conftest.py`:

- `mock_config_entry` - Mock Home Assistant config entry
- `mock_aiohttp_session` - Mock HTTP session for API calls

### Test Data

Test data includes:
- WiFi access point samples (WIFI_APS_1, WIFI_APS_2)
- Mock Google Geolocation API responses (GOOGLE_RESPONSE_1, GOOGLE_RESPONSE_2)
- Test API key (API_KEY)

## Writing Tests

### Config Flow Tests

Test all configuration flow paths:
- User setup (success, errors)
- Duplicate entry prevention
- Reauth flow
- API validation

### Integration Tests

Test integration functionality:
- Setup and unload
- Service calls
- Caching behavior
- Error handling
- State change listeners

### Example Test

```python
async def test_my_feature(
    hass: HomeAssistant, mock_config_entry, mock_aiohttp_session
) -> None:
    """Test my feature."""
    # Setup
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Test
    # ... your test code ...

    # Assert
    assert expected_result
```

## Continuous Integration

When setting up CI/CD, run these commands:

```bash
# Install dependencies
pip install -r requirements_test.txt

# Run linters
ruff check .
mypy .

# Run tests with coverage
pytest --cov=custom_components.wifi_geolocation --cov-report=xml --cov-report=term

# Coverage should be >= 95%
```

## Troubleshooting

### Import Errors

If you get import errors when running tests:
- Ensure you're in the correct directory
- Check that `pytest-homeassistant-custom-component` is installed
- Verify Python path includes the component directory

### Type Checking Issues

If MyPy reports issues in tests:
- Tests are excluded from strict type checking
- Only source files need full type annotations
- Check `pyproject.toml` for MyPy configuration

### Pre-commit Hook Failures

If pre-commit hooks fail:
- Run `ruff check --fix .` to auto-fix issues
- Run `ruff format .` to format code
- Manually fix any remaining issues
- Commit again

## IDE Setup

### VS Code

Recommended extensions:
- Python (Microsoft)
- Ruff
- MyPy Type Checker

Settings (`.vscode/settings.json`):
```json
{
  "python.linting.enabled": true,
  "python.linting.mypyEnabled": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll": true,
      "source.organizeImports": true
    },
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

### PyCharm

1. Enable Ruff in Settings → Tools → Ruff
2. Enable MyPy in Settings → Tools → Python Integrated Tools
3. Set code style to match Ruff settings
