import datetime
import yfinance as yf
from services.scraper import fetch_bizportal_fund_data
import db_manager

def _calculate_stock_summary_data(stocks: list, fx_rate: float) -> dict:
    """Calculate aggregate totals for the stock portfolio in ILS."""
    if not stocks:
        return {"total_value": 0, "daily_return": 0, "total_return": 0}
        
    total_value_ils = 0.0
    total_daily_pnl_ils = 0.0
    total_pnl_ils = 0.0
    total_invested_ils = 0.0

    for stock in stocks:
        symbol = stock.get("symbol")
        if not symbol: continue
        
        currency = stock.get("currency", "USD")
        r = fx_rate if currency == "USD" else 1.0
        
        # Prefer new naming from scraper, fallback to Excel naming
        v_orig = stock.get("totalValueOriginal", stock.get("value", 0.0))
        dp_orig = stock.get("dailyPnlOriginal", stock.get("dailyPnl", 0.0))
        tp_orig = stock.get("totalPnlOriginal", stock.get("totalPnl", 0.0))
        
        val_ils = v_orig * r
        total_value_ils += val_ils
        total_daily_pnl_ils += dp_orig * r
        total_pnl_ils += tp_orig * r
        total_invested_ils += (val_ils - (tp_orig * r))

    daily_base = total_value_ils - total_daily_pnl_ils
    daily_return_pct = (total_daily_pnl_ils / daily_base * 100) if daily_base > 0 else 0.0
    total_return_pct = (total_pnl_ils / total_invested_ils * 100) if total_invested_ils > 0 else 0.0
    
    return {
        "total_value": total_value_ils,
        "daily_return": daily_return_pct,
        "total_return": total_return_pct
    }

async def _perform_stock_prices_update(uid: str, source_label: str = "REFRESH") -> dict:
    """
    Unified logic to refresh stock prices and FX rates for a specific user.
    Called both by manual refresh and automated cron jobs.
    """
    # 1. Refresh USD/ILS FX Rate first
    fx_prev_close = 1.0
    new_rate = 1.0
    # Use a custom session with User-Agent to bypass cloud IP blocking by Yahoo Finance
    import requests
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    try:
        fx_ticker = yf.Ticker("USDILS=X", session=session)
        fx_data = fx_ticker.history(period="5d")
        if not fx_data.empty:
            new_rate = float(fx_data['Close'].iloc[-1])
            fx_prev_close = float(fx_data['Close'].iloc[-2]) if len(fx_data) > 1 else new_rate
            db_manager.save_fx_rate(new_rate, datetime.datetime.now().strftime("%Y-%m-%d"))
            print(f"💰 [{source_label}] Updated FX Rate: {new_rate} (Prev: {fx_prev_close})")
    except Exception as e:
        print(f"⚠️ [{source_label}] Failed to update FX rate: {e}")

    # 2. Identify stocks to update
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    if not portfolio_doc:
        return {"updated": 0, "message": "No portfolio found"}
        
    stocks = portfolio_doc.get("stocks", [])
    if not stocks:
        return {"updated": 0, "message": "No holdings found"}
        
    total_value = 0.0
    total_daily_return_value = 0.0
    total_invested = 0.0
    updated_count = 0
    
    print(f"🔄 [{source_label}] Starting refresh for UID: {uid} ({len(stocks)} symbols)")
    
    for holding in stocks:
        symbol = holding.get("symbol")
        if not symbol: continue
        
        is_cash = holding.get("is_cash", False)
        
        try:
            current_price = None
            previous_close = None
            method_label = "yfinance"

            if is_cash:
                current_price = 1.0
                currency = holding.get("currency", "USD")
                if currency == "USD" and fx_prev_close > 0:
                    # To reflect FX change in Daily P&L, previous native price should be:
                    # previous_native = 1.0 / (new_rate / fx_prev_close)
                    previous_close = 1.0 * (fx_prev_close / new_rate)
                else:
                    previous_close = 1.0
                method_label = "cash"
            else:
                # Normalize: if numeric, append .TA for Yahoo Finance
                ticker = str(symbol).strip()
        
                if ticker.isdigit():
                    # Israeli Mutual Fund / ETF - Use Bizportal
                    method_label = "Bizportal"
                    fund_data = fetch_bizportal_fund_data(ticker)
                    if fund_data:
                        current_price = fund_data["current_price"]
                        previous_close = fund_data["previous_close"]
                    else:
                        print(f"⚠️ [{source_label}] Bizportal fetch failed for {ticker}, skipping price update.")
                else:
                    # US/Other Stock - Use yfinance
                    try:
                        t = yf.Ticker(ticker, session=session)
                        hist = t.history(period="5d")
                        if not hist.empty:
                            current_price = float(hist['Close'].iloc[-1])
                            previous_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
                        else:
                            print(f"⚠️ [{source_label}] No yfinance history found for ticker {ticker}")
                    except Exception as yf_e:
                        print(f"⚠️ [{source_label}] yfinance error for {ticker}: {yf_e}")
        
            old_price = holding.get("lastPrice", holding.get("current_price", 0.0))
            
            if current_price is None:
                # Fallback to existing calculations if fetch failed
                shares = float(holding.get("qty", holding.get("shares", 0.0)))
                holding_value = shares * float(old_price)
                avg_cost = float(holding.get("avgCostPrice", holding.get("average_cost", old_price)))
                total_value += holding_value
                total_invested += shares * avg_cost
                total_daily_return_value += float(holding.get("dailyPnlOriginal", 0.0))
                continue
                
            # Extract shares for log
            shares_for_log = float(holding.get("qty", holding.get("shares", 0.0)))
    
            # Compute aggregations for THIS stock
            shares = float(holding.get("qty", holding.get("shares", 0.0)))
            avg_cost = float(holding.get("avgCostPrice", holding.get("average_cost", current_price)))
            
            holding_value = shares * current_price
            holding_invested = shares * avg_cost
            
            # Daily delta
            daily_delta = current_price - previous_close
            daily_pnl = shares * daily_delta
            total_pnl = holding_value - holding_invested
                
            # 1. Update the stock object for `portfolios` doc (the UI view)
            calc_daily_pct = (daily_delta / previous_close * 100) if previous_close > 0 else 0.0
            
            # Print the correct stats to matches what is saved
            print(f"📊 [{source_label}] {symbol} ({shares_for_log:,.2f} units) via {method_label}: Prev={previous_close:.2f} -> Curr={current_price:.2f} (Daily Δ: {daily_delta:+.2f}, {calc_daily_pct:+.2f}%)")
            
            holding["lastPrice"] = current_price
            holding["qty"] = shares  # Ensure qty is saved for the frontend
            
            holding["dailyChangePercent"] = calc_daily_pct
            holding["dailyPnlOriginal"] = daily_pnl
            holding["totalPnlOriginal"] = total_pnl
            holding["totalValueOriginal"] = holding_value
            holding["totalReturnPercent"] = (total_pnl / holding_invested * 100) if holding_invested > 0 else 0.0
            holding["last_updated"] = datetime.datetime.now().isoformat()
            
            if method_label == "Bizportal":
                print(f"🎯 [DEBUG-IL] {ticker} -> Price: {current_price}, Prev: {previous_close}, DailyDelta: {daily_delta:+.2f}, DailyChange%: {calc_daily_pct:+.2f}%")
    
            # 2. Update the `families/{uid}/holdings` subcollection for cron job sync
            updates_for_subcol = {
                "current_price": current_price,
                "shares": shares,
                "average_cost": avg_cost,
                "last_updated": datetime.datetime.now().isoformat(),
                "name": holding.get("name", ""),
                "currency": holding.get("currency", "USD")
            }
            db_manager.update_family_holding(uid, symbol, updates_for_subcol)
            
            updated_count += 1
            total_value += holding_value
            total_invested += holding_invested
            total_daily_return_value += daily_pnl
                    
        except Exception as e:
            print(f"⚠️ [{source_label}] Error updating {symbol}: {e}")
            shares = float(holding.get("qty", 0.0))
            total_value += shares * float(old_price)
            avg_cost = float(holding.get("avgCostPrice", holding.get("average_cost", old_price)))
            total_invested += shares * avg_cost
            total_daily_return_value += float(holding.get("dailyPnlOriginal", 0.0))
    
    if updated_count > 0:
        # Recalculate summary using the clean helper
        fx_rate_data = db_manager.get_fx_rate()
        fx_rate = fx_rate_data.get("rate", 3.70) if fx_rate_data else 3.70
        summary = _calculate_stock_summary_data(stocks, fx_rate)
        
        # Save back the whole portfolio doc to update the UI
        db_manager.save_processed_portfolio(uid, portfolio_doc)

        # Update the summary too
        db_manager.update_portfolio_summary(uid, summary["total_value"], summary["daily_return"], summary["total_return"])

    return {"updated": updated_count}
