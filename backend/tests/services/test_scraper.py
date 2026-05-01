import pytest
from unittest.mock import patch, MagicMock
from services.scraper import fetch_bizportal_fund_data

@pytest.fixture
def mock_requests_get():
    with patch("services.scraper.requests.get") as m:
        yield m

def test_fetch_bizportal_fund_data_success_rise(mock_requests_get):
    """Test successful scrape with a positive percentage change."""
    # Arrange
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '''
        <html>
            <body>
                <div class="num">150.50</div>
                <span class="num percent rise">1.5%</span>
            </body>
        </html>
    '''
    mock_requests_get.return_value = mock_resp
    
    # Act
    result = fetch_bizportal_fund_data("1234")
    
    # Assert
    # current_price_agorot = 150.50 -> current_price = 1.505
    # pct_change = 1.5
    # prev_close = 1.505 / (1 + 0.015) = 1.505 / 1.015 = 1.48275...
    assert result is not None
    assert result["current_price"] == 1.505
    assert result["pct_change"] == 1.5
    assert abs(result["previous_close"] - 1.48275) < 0.001

def test_fetch_bizportal_fund_data_success_drop(mock_requests_get):
    """Test successful scrape with a negative percentage change."""
    # Arrange
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '''
        <html>
            <body>
                <div class="num">100.00</div>
                <span class="num percent drop">-5.0%</span>
            </body>
        </html>
    '''
    mock_requests_get.return_value = mock_resp
    
    # Act
    result = fetch_bizportal_fund_data("1234")
    
    # Assert
    assert result is not None
    assert result["current_price"] == 1.00
    assert result["pct_change"] == -5.0
    # prev_close = 1.00 / (1 - 0.05) = 1.05263...
    assert abs(result["previous_close"] - 1.0526) < 0.001

def test_fetch_bizportal_fund_data_missing_elements(mock_requests_get):
    """Test behavior when the expected HTML elements (.num) are missing."""
    # Arrange
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '<html><body><div>No price here</div></body></html>'
    mock_requests_get.return_value = mock_resp
    
    # Act
    result = fetch_bizportal_fund_data("1234")
    
    # Assert
    assert result is None

def test_fetch_bizportal_fund_data_http_error(mock_requests_get):
    """Test graceful failure on HTTP error."""
    # Arrange
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_requests_get.return_value = mock_resp
    
    # Act
    result = fetch_bizportal_fund_data("1234")
    
    # Assert
    assert result is None

def test_fetch_bizportal_fund_data_exception(mock_requests_get):
    """Test graceful failure on network exception."""
    # Arrange
    mock_requests_get.side_effect = Exception("Connection Timeout")
    
    # Act
    result = fetch_bizportal_fund_data("1234")
    
    # Assert
    assert result is None
