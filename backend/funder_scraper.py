import httpx
from bs4 import BeautifulSoup
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

async def fetch_funder_yields(url: str) -> List[Dict]:
    """
    Fetches the monthly yields from a Funder policy URL.
    Returns a list of dicts: [{"period": "YYYY-MM", "yield": 1.22}, ...]
    The list is ordered from NEWEST to OLDEST (as it appears on Funder).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        yields = []
        
        tables = soup.find_all('table')
        target_table = None
        for table in tables:
            headers_text = table.get_text()
            if "תקופה" in headers_text and "תשואה חודשית" in headers_text:
                target_table = table
                break
                
        if not target_table:
            logger.warning(f"Could not find yields table on {url}")
            return yields
            
        rows = target_table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if not cols or len(cols) < 2:
                continue
                
            col_texts = [c.get_text(strip=True) for c in cols]
            
            period_str = ""
            yield_str = ""
            
            for text in col_texts:
                if re.match(r'^\d{2}-\d{2}$', text):
                    period_str = text
                if '%' in text:
                    yield_str = text.replace('%', '').strip()
                    
            if period_str and yield_str:
                try:
                    mm, yy = period_str.split('-')
                    if len(yy) == 2:
                        yyyy = f"20{yy}"
                    formatted_period = f"{yyyy}-{mm}"
                    
                    yield_val = float(yield_str)
                    
                    yields.append({
                        "period": formatted_period,
                        "yield": yield_val
                    })
                except ValueError:
                    continue
                    
        return yields

    except Exception as e:
        logger.error(f"Error scraping {url}: {str(e)}")
        return []
