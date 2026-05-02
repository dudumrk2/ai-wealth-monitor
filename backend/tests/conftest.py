"""
Shared test fixtures for backend tests.
Pytest automatically discovers and loads conftest.py files.
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_db_manager():
    """Mock the db_manager module. Patches the import target dynamically."""
    with patch("db_manager") as m:
        yield m


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for HTTP-dependent tests."""
    with patch("requests.get") as m:
        yield m
