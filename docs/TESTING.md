# Testing Guide - arXiv Paper Curator

## Issue: HTTP 429 (Rate Limiting) Error from arXiv API

### Root Cause

The integration test `test_arxiv_client_basic` was making **real HTTP requests** to the arXiv API without mocking. The arXiv API enforces strict rate limiting:

- **Minimum delay between requests**: 3 seconds
- **Max requests per session**: Limited
- **Exceeded limit response**: HTTP 429 (Too Many Requests)

When running tests rapidly, especially multiple tests or repeated runs, you quickly hit this rate limit.

---

## The Fix

### What Changed

1. **Updated `tests/integration/test_services.py`**:
   - Added `@pytest.mark.asyncio` decorator to the async test
   - Wrapped the HTTP request in `patch("httpx.AsyncClient")` to mock the network call
   - Test now uses a mock XML response instead of hitting the real API

2. **Added `tests/conftest.py`**:
   - Created reusable pytest fixtures for mock responses
   - `mock_arxiv_response` — realistic arXiv API XML response
   - `mock_empty_arxiv_response` — empty result set response
   - These fixtures are available to all tests

3. **Created `pytest.ini`**:
   - Configured pytest for async tests (`asyncio_mode = auto`)
   - Added custom markers for test organization
   - Test discovery patterns and output options

### Code Example: Before vs After

**Before (Makes Real API Call):**

```python
async def test_arxiv_client_basic():
    client = make_arxiv_client()
    papers = await client.fetch_papers_with_query("cat:cs.AI", max_results=1)
    assert isinstance(papers, list)
```

**After (Uses Mocking):**

```python
@pytest.mark.asyncio
async def test_arxiv_client_basic(mock_arxiv_response):
    """Test arXiv client with mocked API response to avoid rate limiting."""
    client = make_arxiv_client()

    with patch("httpx.AsyncClient") as mock_http_client:
        mock_response = MagicMock()
        mock_response.text = mock_arxiv_response
        mock_response.raise_for_status.return_value = None

        mock_http_client.return_value.__aenter__.return_value.get.return_value = mock_response

        papers = await client.fetch_papers(max_results=1)

        assert isinstance(papers, list)
        assert len(papers) == 1
```

---

## Running Tests

### Run All Tests (With Mocking — No Rate Limiting)

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Run Specific Test Categories

```bash
# Run only unit tests (fast, no external dependencies)
pytest tests/unit/ -v

# Run only API tests
pytest tests/api/ -v

# Run only integration tests
pytest tests/integration/ -v

# Run without slow tests
pytest -m "not slow" tests/
```

### Run Individual Tests

```bash
# Run specific test file
pytest tests/integration/test_services.py -v

# Run specific test function
pytest tests/integration/test_services.py::test_arxiv_client_basic -v

# Run with live output (don't capture prints)
pytest tests/integration/test_services.py::test_arxiv_client_basic -v -s
```

### Debug Mode

```bash
# Show full tracebacks for errors
pytest tests/ -v --tb=long

# Drop into debugger on failures
pytest tests/ --pdb

# Show print output
pytest tests/ -v -s
```

---

## Best Practices for Tests

### ✅ DO: Mock External API Calls

```python
# Good: Tests are fast and don't hit rate limits
@pytest.mark.asyncio
async def test_fetch_papers(mock_arxiv_response):
    with patch("httpx.AsyncClient") as mock_client:
        # configure mock
        papers = await client.fetch_papers()
        assert len(papers) == 1
```

### ❌ DON'T: Make Real API Calls in Tests

```python
# Bad: Tests are slow and hit rate limits
async def test_fetch_papers():
    papers = await client.fetch_papers()  # Real API call!
    assert isinstance(papers, list)
```

### ✅ DO: Use Fixtures for Reusable Data

```python
# In conftest.py
@pytest.fixture
def mock_arxiv_response():
    return """<?xml version="1.0"?>..."""

# In test file
def test_something(mock_arxiv_response):
    # Fixture is automatically injected
    assert mock_arxiv_response.startswith("<?xml")
```

### ✅ DO: Mark Tests Appropriately

```python
# Unit tests (no external deps)
def test_query_builder():
    ...

# Integration tests (may need external services)
@pytest.mark.integration
def test_arxiv_integration():
    ...

# Slow tests
@pytest.mark.slow
def test_expensive_operation():
    ...
```

---

## Common Issues & Solutions

### Issue: `asyncio.TimeoutError` or `test_arxiv_client_basic` Hangs

**Solution**: Ensure you're using the `@pytest.mark.asyncio` decorator:

```python
@pytest.mark.asyncio  # ← Don't forget this!
async def test_arxiv_client_basic(mock_arxiv_response):
    ...
```

### Issue: Import Errors When Running Tests

**Solution**: Install development dependencies:

```bash
python -m pip install -e ".[dev]"
```

### Issue: Tests Still Hitting Real API

**Solution**: Check that `patch()` context manager is correctly wrapping the HTTP call:

```python
# Patch the right location
with patch("httpx.AsyncClient"):  # ← Correct
    # not patch("src.services.arxiv.client.httpx.AsyncClient")
```

### Issue: Mock Response Not Working

**Solution**: Ensure mock response has all required XML elements:

```python
mock_response = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2024.0001v1</id>
    <!-- Other required fields -->
  </entry>
</feed>"""
```

---

## Test Structure

```
tests/
├── conftest.py                     # Shared fixtures (available to all tests)
├── unit/                           # Unit tests (no external dependencies)
│   └── services/
│       ├── test_arxiv_client.py
│       ├── test_pdf_parser.py
│       └── test_opensearch_query_builder.py
├── api/                            # API endpoint tests
│   ├── conftest.py                # API-specific fixtures
│   └── routers/
│       ├── test_ask.py
│       ├── test_hybrid_search.py
│       └── test_ping.py
└── integration/                    # Integration tests (with mocking)
    └── test_services.py
```

---

## Running Tests in CI/CD

For GitHub Actions or similar CI systems, tests should be run with mocking (as configured):

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    python -m pip install -e ".[dev]"
    pytest tests/ --cov=src --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

Since all external API calls are mocked, tests will run quickly without rate limiting issues.

---

## Adding New Tests with Mocking

When adding new integration tests that call external APIs:

1. **Create a fixture** in `tests/conftest.py` for the mock response
2. **Use `@pytest.mark.asyncio`** if the test is async
3. **Patch external calls** using `unittest.mock.patch()`
4. **Inject fixture** as a function parameter

Example:

```python
# tests/conftest.py
@pytest.fixture
def mock_external_api():
    return """expected response data"""

# tests/integration/test_new_feature.py
@pytest.mark.asyncio
async def test_my_feature(mock_external_api):
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.text = mock_external_api
        mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

        result = await my_function()
        assert result is not None
```

---

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Asyncio](https://pytest-asyncio.readthedocs.io/)
- [Python unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [arXiv API Documentation](https://arxiv.org/help/api/)
- [arXiv Rate Limiting](https://arxiv.org/help/api/user-manual#detailed_comments)
