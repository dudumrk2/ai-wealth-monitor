import requests
from typing import Optional
from bs4 import BeautifulSoup

def fetch_bizportal_fund_data(ticker: str) -> Optional[dict]:
    """
    Fetches the latest price for an Israeli mutual fund or ETF from Bizportal.
    Target URL: https://www.bizportal.co.il/mutualfunds/quote/generalview/{ticker}
    Returns a dict with 'current_price' and 'previous_close'.
    """
    url = f"https://www.bizportal.co.il/mutualfunds/quote/generalview/{ticker}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ [BIZPORTAL] HTTP {response.status_code} for fund {ticker}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract Current Price
        # Bizportal stores prices inside `<div class="num">`
        num_divs = soup.find_all('div', class_='num')
        if not num_divs:
            print(f"❌ [BIZPORTAL] Could not find price container (.num) for fund {ticker}")
            return None
        
        current_price_str = num_divs[0].get_text().strip().replace(",", "")
        current_price_agorot = float(current_price_str)
        
        # Bizportal prices are in AGOROT (1/100 of NIS), convert to NIS
        current_price = current_price_agorot / 100.0
        
        # Extract Daily PCT Change
        # Bizportal stores pct change in `<span class="num percent rise">` or `<span class="num percent drop">`
        pct_change = 0.0
        rise_span = soup.select_one('.num.percent.rise')
        drop_span = soup.select_one('.num.percent.drop')
        
        if rise_span:
            pct_str = rise_span.get_text().strip().replace("%", "").replace(",", "")
            pct_change = float(pct_str)
        elif drop_span:
            pct_str = drop_span.get_text().strip().replace("%", "").replace(",", "")
            # Bizportal includes the minus sign in the string, so we just convert it
            pct_change = float(pct_str)
            
        # Calculate Previous Close
        # formula: current_price = previous_close * (1 + pct_change/100) -> previous_close = current_price / (1 + pct_change/100)
        if pct_change != -100.0:
            previous_close = current_price / (1 + (pct_change / 100))
        else:
            previous_close = current_price # Fallback to prevent division by zero edge-cases
            
        print(f"🔍 [BIZPORTAL] Scraped {ticker}: Price={current_price}, Pct={pct_change}%, CalculatedPrev={previous_close}")
        return {
            "current_price": current_price,
            "previous_close": previous_close,
            "pct_change": pct_change
        }

    except Exception as e:
        print(f"❌ [BIZPORTAL] Failed to scrape Bizportal for fund {ticker}: {e}")
        return None
