import requests
from bs4 import BeautifulSoup

def fetch_israeli_prime_rate() -> float:
    """
    Fetch the current Israeli Prime Rate.
    Strategy: GET the Bank of Israel official JSON/XML API for the base rate, then add 1.5%.
    Falls back to 6.0 on any error.
    """
    FALLBACK_RATE = 6.0
    try:
        # BOI publishes base rate at this endpoint (returns JSON)
        url = "https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/BOI_REPO_RATE/1.0/REPO_RATE?format=sdmx-compact-2.1&startperiod=2024-01-01&endperiod=9999-01-01"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            # Parse XML: <Obs TIME_PERIOD="2025-01" OBS_VALUE="4.5" />
            soup = BeautifulSoup(resp.content, "xml")
            obs_tags = soup.find_all("Obs")
            if obs_tags:
                # Last entry is the most recent
                latest = obs_tags[-1]
                boi_rate = float(latest.get("OBS_VALUE", 4.5))
                prime_rate = round(boi_rate + 1.5, 2)
                print(f"✅ [PRIME_RATE] BOI base rate: {boi_rate}% -> Prime rate: {prime_rate}%")
                return prime_rate
    except Exception as e:
        print(f"⚠️ [PRIME_RATE] BOI XML fetch failed: {e}")

    print(f"ℹ️ [PRIME_RATE] Using fallback prime rate: {FALLBACK_RATE}%")
    return FALLBACK_RATE
