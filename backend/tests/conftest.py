"""
Shared test fixtures for backend tests.
Pytest automatically discovers and loads conftest.py files.
"""
import sys
from pathlib import Path

# Add backend directory to Python path so tests can import routers, services, etc.
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

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
