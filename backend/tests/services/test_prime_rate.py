import pytest
from unittest.mock import patch, MagicMock
from services.prime_rate import fetch_israeli_prime_rate

@pytest.fixture
def mock_requests_get():
    with patch("services.prime_rate.requests.get") as m:
        yield m

@pytest.fixture
def mock_beautiful_soup():
    with patch("services.prime_rate.BeautifulSoup") as m:
        yield m

def test_fetch_israeli_prime_rate_success(mock_requests_get, mock_beautiful_soup):
    """Test successful fetching and parsing of BOI prime rate."""
    # Arrange
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_requests_get.return_value = mock_resp
    
    mock_obs1 = MagicMock()
    mock_obs1.get.return_value = "4.5"
    mock_obs2 = MagicMock()
    mock_obs2.get.return_value = "4.75"
    mock_beautiful_soup.return_value.find_all.return_value = [mock_obs1, mock_obs2]

    # Act
    result = fetch_israeli_prime_rate()

    # Assert
    # The last Obs tag has OBS_VALUE = 4.75. Prime rate is BOI + 1.5.
    assert result == 6.25

def test_fetch_israeli_prime_rate_missing_tags(mock_requests_get, mock_beautiful_soup):
    """Test fallback to 6.0 when the XML structure does not contain <Obs> tags."""
    # Arrange
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_requests_get.return_value = mock_resp
    
    mock_beautiful_soup.return_value.find_all.return_value = []

    # Act
    result = fetch_israeli_prime_rate()

    # Assert
    assert result == 6.0

def test_fetch_israeli_prime_rate_http_error(mock_requests_get):
    """Test fallback to 6.0 on an HTTP error status code."""
    # Arrange
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_requests_get.return_value = mock_resp

    # Act
    result = fetch_israeli_prime_rate()

    # Assert
    assert result == 6.0

def test_fetch_israeli_prime_rate_exception(mock_requests_get):
    """Test fallback to 6.0 on a network exception."""
    # Arrange
    mock_requests_get.side_effect = Exception("Connection Error")

    # Act
    result = fetch_israeli_prime_rate()

    # Assert
    assert result == 6.0
