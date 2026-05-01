import pytest
from unittest.mock import patch, MagicMock
from services.stock_updater import _calculate_stock_summary_data, _perform_stock_prices_update

# ==========================================
# 1. Tests for synchronous calculations
# ==========================================

def test_calculate_stock_summary_data_empty():
    """Test that an empty stock list returns 0 for all totals."""
    result = _calculate_stock_summary_data([], 3.7)
    assert result == {"total_value": 0, "daily_return": 0, "total_return": 0}

def test_calculate_stock_summary_data_with_usd_and_ils():
    """Test aggregation of a mixed USD and ILS portfolio, including FX conversions."""
    # Arrange
    stocks = [
        {"symbol": "AAPL", "currency": "USD", "totalValueOriginal": 1000.0, "dailyPnlOriginal": 10.0, "totalPnlOriginal": 100.0},
        {"symbol": "5109889", "currency": "ILS", "totalValueOriginal": 2000.0, "dailyPnlOriginal": -20.0, "totalPnlOriginal": 50.0}
    ]
    fx_rate = 3.7
    
    # Act
    result = _calculate_stock_summary_data(stocks, fx_rate)
    
    # Assert
    # total_value: 1000*3.7 + 2000*1.0 = 5700
    assert result["total_value"] == 5700.0
    
    # total_daily_pnl: 10*3.7 + (-20)*1.0 = 17
    # total_pnl: 100*3.7 + 50*1.0 = 420
    # total_invested: (3700 - 370) + (2000 - 50) = 3330 + 1950 = 5280
    # daily_base: 5700 - 17 = 5683
    # daily_return: (17 / 5683) * 100
    # total_return: (420 / 5280) * 100
    assert abs(result["daily_return"] - (17 / 5683 * 100)) < 0.001
    assert abs(result["total_return"] - (420 / 5280 * 100)) < 0.001

def test_calculate_stock_summary_data_fallback_keys():
    """Test aggregation handles legacy Excel property names fallback."""
    # Arrange
    stocks = [{"symbol": "AAPL", "currency": "USD", "value": 1000.0, "dailyPnl": 10.0, "totalPnl": 100.0}]
    
    # Act
    result = _calculate_stock_summary_data(stocks, 3.7)
    
    # Assert
    assert result["total_value"] == 3700.0


# ==========================================
# 2. Tests for async updates (mocking DB & External APIs)
# ==========================================

@pytest.fixture
def mock_db():
    with patch("services.stock_updater.db_manager") as m:
        yield m

@pytest.fixture
def mock_yf():
    with patch("services.stock_updater.yf") as m:
        yield m

@pytest.fixture
def mock_bizportal():
    with patch("services.stock_updater.fetch_bizportal_fund_data") as m:
        yield m

@pytest.fixture
def mock_requests():
    with patch("requests.Session") as m:
        yield m

@pytest.mark.asyncio
async def test_perform_stock_prices_update_no_portfolio(mock_db):
    """Test that function handles missing portfolio gracefully."""
    # Arrange
    mock_db.get_processed_portfolio.return_value = None
    
    # Act
    result = await _perform_stock_prices_update("user1")
    
    # Assert
    assert result == {"updated": 0, "message": "No portfolio found"}

@pytest.mark.asyncio
async def test_perform_stock_prices_update_no_stocks(mock_db):
    """Test that function handles empty stocks gracefully."""
    # Arrange
    mock_db.get_processed_portfolio.return_value = {"stocks": []}
    
    # Act
    result = await _perform_stock_prices_update("user1")
    
    # Assert
    assert result == {"updated": 0, "message": "No holdings found"}

@pytest.mark.asyncio
async def test_perform_stock_prices_update_bizportal(mock_db, mock_yf, mock_bizportal, mock_requests):
    """Test updating Israeli mutual funds via Bizportal scraper."""
    # Arrange
    # Mock YF returning empty history for the FX rate to keep it simple
    mock_yf.Ticker.return_value.history.return_value.empty = True
    
    mock_db.get_processed_portfolio.return_value = {
        "stocks": [{"symbol": "5109889", "qty": 100.0, "avgCostPrice": 150.0}]
    }
    mock_db.get_fx_rate.return_value = {"rate": 3.7}
    
    # Mock bizportal response
    mock_bizportal.return_value = {"current_price": 160.0, "previous_close": 155.0}
    
    # Act
    result = await _perform_stock_prices_update("user1")
    
    # Assert
    assert result["updated"] == 1
    mock_bizportal.assert_called_once_with("5109889")
    
    # Validate DB update calls
    args, kwargs = mock_db.update_family_holding.call_args
    assert args[0] == "user1"
    assert args[1] == "5109889"
    assert args[2]["current_price"] == 160.0
    assert args[2]["shares"] == 100.0

@pytest.mark.asyncio
async def test_perform_stock_prices_update_yfinance(mock_db, mock_yf, mock_bizportal, mock_requests):
    """Test updating US stocks via yfinance library."""
    # Arrange
    fx_hist = MagicMock()
    fx_hist.empty = True
    
    # Mock yfinance pandas response
    stock_close = MagicMock()
    stock_close.iloc = [145.0, 150.0]
    stock_hist = MagicMock()
    stock_hist.empty = False
    stock_hist.__len__.return_value = 2
    stock_hist.__getitem__.return_value = stock_close
    
    def ticker_side_effect(ticker, session=None):
        m = MagicMock()
        if ticker == "USDILS=X":
            m.history.return_value = fx_hist
        elif ticker == "AAPL":
            m.history.return_value = stock_hist
        return m
        
    mock_yf.Ticker.side_effect = ticker_side_effect
    
    mock_db.get_processed_portfolio.return_value = {
        "stocks": [{"symbol": "AAPL", "qty": 10.0, "avgCostPrice": 120.0}]
    }
    mock_db.get_fx_rate.return_value = {"rate": 3.7}
    
    # Act
    result = await _perform_stock_prices_update("user1")
    
    # Assert
    assert result["updated"] == 1
    
    # Validate DB update calls
    args, kwargs = mock_db.update_family_holding.call_args
    assert args[1] == "AAPL"
    assert args[2]["current_price"] == 150.0
