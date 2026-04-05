import asyncio
from app import _attach_competitors_to_funds, _collect_market_data

async def main():
    portfolios = {
        "user": {
            "funds": [
                {
                    "track_name": "מור השתלמות - מניות",
                    "provider_name": "מור גמל ופנסיה",
                    "yield_1yr": 0,
                    "yield_3yr": 0,
                    "yield_5yr": 0,
                    "sharpe_ratio": 0
                }
            ]
        }
    }
    
    market_data = await _collect_market_data(portfolios)
    _attach_competitors_to_funds(portfolios, market_data)
    
    print("AFTER OVERRIDE:")
    for f in portfolios["user"]["funds"]:
        print(f"[user]: {f.get('track_name')} - 1Y: {f.get('yield_1yr')} | 3Y: {f.get('yield_3yr')} | 5Y: {f.get('yield_5yr')} | Sharpe: {f.get('sharpe_ratio')}")

if __name__ == "__main__":
    asyncio.run(main())
