import asyncio
from app import _attach_competitors_to_funds, _collect_market_data_async

async def main():
    portfolios = {
        "user": {
            "funds": [
                {
                    "track_name": "מור השתלמות - מניות",
                    "provider_name": "מור גמל ופנסיה",
                    "track_id": "12536",
                    "yield_1yr": 4.71,
                    "yield_3yr": 76.51,
                    "yield_5yr": 93.03,
                    "sharpe_ratio": 0
                }
            ]
        }
    }
    
    print("BEFORE OVERRIDE:")
    for f in portfolios["user"]["funds"]:
        print(f"[{f.get('track_name')}]: 1Y: {f.get('yield_1yr')} | 3Y: {f.get('yield_3yr')} | 5Y: {f.get('yield_5yr')} | Sharpe: {f.get('sharpe_ratio')}")
    
    market_data = await _collect_market_data_async(portfolios)
    _attach_competitors_to_funds(portfolios, market_data)
    
    print("\nAFTER OVERRIDE:")
    for f in portfolios["user"]["funds"]:
        print(f"[{f.get('track_name')}] (Sharpe injected?): 1Y: {f.get('yield_1yr')} | 3Y: {f.get('yield_3yr')} | 5Y: {f.get('yield_5yr')} | Sharpe: {f.get('sharpe_ratio')}")

if __name__ == "__main__":
    asyncio.run(main())
