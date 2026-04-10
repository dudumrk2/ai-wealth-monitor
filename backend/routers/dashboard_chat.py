from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, List, Optional
import os
import json
import asyncio

from google import genai
from google.genai import types
import db_manager
from auth import verify_token

router = APIRouter(tags=["dashboard"])

class DashboardSummary(BaseModel):
    total_net_worth: float
    balances: Dict[str, float]
    allocation_percentages: Dict[str, float]
    recommendations: List[dict]

class ChatRequest(BaseModel):
    family_id: str
    question: str
    context_filter: str

@router.get("/api/dashboard/summary/{family_id}", response_model=DashboardSummary)
async def get_dashboard_summary(family_id: str, user: dict = Depends(verify_token)):
    if user.get("uid") != family_id and family_id != "CURRENT_UID":
         family_id = user.get("uid")

    uid = user.get("uid")
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    
    if not portfolio_doc:
        from mock_data import MOCK_DATA
        portfolio_doc = MOCK_DATA
        
    portfolios = portfolio_doc.get("portfolios", {})
    action_items = portfolio_doc.get("action_items", [])
    
    balances = {
        "pension": 0.0,
        "stocks": 0.0,
        "alternative": 0.0,
        "insurance_monthly": 0.0
    }
    
    pension_cats = ['pension', 'managers', 'study', 'provident', 'investment_provident']
    
    for owner_key in ["user", "spouse"]:
        funds = portfolios.get(owner_key, {}).get("funds", [])
        for fund in funds:
            cat = fund.get("category", "")
            bal = float(fund.get("balance", 0) or 0)
            if cat in pension_cats:
                balances["pension"] += bal
            elif cat == "stocks":
                balances["stocks"] += bal
            elif cat == "alternative":
                balances["alternative"] += bal
            elif cat == "insurance":
                balances["insurance_monthly"] += float(fund.get("monthly_deposit", 0) or 0)
                
    joint_stocks = portfolios.get("joint", {}).get("stock_investments", [])
    for fund in joint_stocks:
        balances["stocks"] += float(fund.get("balance", 0) or 0)
        
    alt_invest = portfolios.get("user", {}).get("alternative_investments", [])
    for a in alt_invest:
        balances["alternative"] += float(a.get("current_value", a.get("balance", 0)) or 0)

    total_net_worth = balances["pension"] + balances["stocks"] + balances["alternative"]
    alloc = {}
    if total_net_worth > 0:
        alloc["pension"] = round((balances["pension"] / total_net_worth) * 100, 2)
        alloc["stocks"] = round((balances["stocks"] / total_net_worth) * 100, 2)
        alloc["alternative"] = round((balances["alternative"] / total_net_worth) * 100, 2)

    return DashboardSummary(
        total_net_worth=total_net_worth,
        balances=balances,
        allocation_percentages=alloc,
        recommendations=action_items
    )

@router.post("/api/chat/ask")
async def copilot_chat_ask(request: ChatRequest, user: dict = Depends(verify_token)):
    uid = user.get("uid")
    
    family_profile = db_manager.get_family_profile(uid)
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    if not portfolio_doc:
        from mock_data import MOCK_DATA
        portfolio_doc = MOCK_DATA
        
    portfolios = portfolio_doc.get("portfolios", {})
    f_profile = family_profile.get("financial_profile", {}) if family_profile else {}
    
    filtered_funds = []
    pension_cats = ['pension', 'managers', 'study', 'provident', 'investment_provident']
    
    for owner_key in ["user", "spouse"]:
        for fund in portfolios.get(owner_key, {}).get("funds", []):
            cat = fund.get("category", "")
            
            if request.context_filter == "פנסיה" and cat not in pension_cats: continue
            if request.context_filter == "בורסה" and cat != "stocks": continue
            if request.context_filter == "כללי": pass
            if request.context_filter == "ביטוח" and cat != "insurance": continue
            
            filtered_funds.append(fund)
            
    if request.context_filter == "בורסה" or request.context_filter == "כללי":
        filtered_funds.extend(portfolios.get("joint", {}).get("stock_investments", []))
        
    context_data = {
        "profile": f_profile,
        "relevant_funds": filtered_funds
    }
    
    system_prompt = f"""You are an expert family wealth advisor (Copilot).
Answer the user's question concisely in Hebrew, based ONLY on the provided financial data.
Data: {json.dumps(context_data, ensure_ascii=False)}
"""

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ [CHAT] GEMINI_API_KEY not configured. Returning mock response.")
        return {"response": f"זוהי תשובת מערכת לדוגמה (חסר מפתח GEMINI_API_KEY). ההקשר שלך מבוסס על {len(filtered_funds)} מוצרים בקטגוריית {request.context_filter}."}
        
    try:
        client = genai.Client(api_key=api_key)
        max_retries = 5
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=request.question,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                    ),
                )
                return {"response": response.text}
            except Exception as e:
                err_str = str(e)
                print(f"⚠️ [CHAT] API Attempt {attempt + 1}/{max_retries} failed: {err_str}")
                
                # Check for rate limit or server overload
                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2) # wait 2 seconds before retrying
                        continue
                    return {"response": "המערכת חווה כרגע עומס עקב בקשות רבות. הניסיונות האוטומטיים כשלו, אנא נסה שוב בעוד מספר דקות."}
                else:
                    return {"response": "מצטער, חלה שגיאה ביצירת התשובה."}

    except Exception as e:
        print(f"❌ [CHAT] Gemini SDK Initialization Error: {e}")
        return {"response": "מצטער, חלה שגיאה פנימית."}
