import json
import db_manager

def check_5y_yields():
    print("--- 🔍 Checking Database for 5Y Yields ---")
    db_manager.initialize_firebase()
    
    # Fetch the exact JSON saved in Firebase
    data = db_manager.get_processed_portfolio('414PiKcFOWRO0PNRAfuVsD3fqoV2')
    if not data:
        print("❌ No data found in Firebase for this UID.")
        return
        
    funds = data.get('portfolios', {}).get('user', {}).get('funds', [])
    spouse_funds = data.get('portfolios', {}).get('spouse', {}).get('funds', [])
    all_funds = funds + spouse_funds
    
    print(f"📊 Found {len(all_funds)} total funds in DB.")
    print("-" * 50)
    
    for f in all_funds:
        provider = f.get('provider_name', '')
        track = f.get('track_name', '')
        y1 = f.get('yield_1yr')
        y3 = f.get('yield_3yr')
        y5 = f.get('yield_5yr')
        
        # We specifically want to check Mor and Analyst 5Y yields
        if 'מור' in provider or 'אנליסט' in provider:
            print(f"[{provider}] {track}")
            print(f"   -> 1Y: {y1}% | 3Y: {y3}% | 5Y: {y5}%")
            
            # Simple heuristic check
            if y3 is not None and y5 is not None and y3 > 40 and y5 < 20:
                print(f"   ⚠️ WARNING: 5Y ({y5}%) is bizarrely lower than 3Y ({y3}%). Claude hallucinated the annualized column again!")
            print("-" * 50)

if __name__ == "__main__":
    check_5y_yields()
