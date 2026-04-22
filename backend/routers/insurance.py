from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import os
import db_manager
from auth import verify_token
import config
from google import genai
from google.genai import types
import config

router = APIRouter(tags=["insurance"])

class CompareRequest(BaseModel):
    policy_id: str

@router.post("/api/insurance/compare")
async def compare_insurance(request: CompareRequest, user: dict = Depends(verify_token)):
    uid = user.get("uid")
    
    # --- DEMO BYPASS ---
    if uid == config.DEMO_UID:
        return {"draft": "שלום, בדקתי את תנאי הפוליסה שלי וראיתי שישנן חלופות עם דמי ניהול נמוכים משמעותית. אשמח לבחון הוזלה בעלויות הנוכחיות שלי כדי שאוכל להישאר אצלכם. תודה!"}

    portfolio_doc = db_manager.get_processed_portfolio(uid)
    if not portfolio_doc:
        raise HTTPException(status_code=404, detail="לא נמצא תיק נתונים")
        
    portfolios = portfolio_doc.get("portfolios", {})
    
    target_fund = None
    for owner_key in ["user", "spouse"]:
        for fund in portfolios.get(owner_key, {}).get("funds", []):
            if fund.get("id") == request.policy_id or fund.get("policy_number") == request.policy_id:
                target_fund = fund
                break
        if target_fund:
            break
            
    if not target_fund:
        raise HTTPException(status_code=404, detail="הפוליסה לא נמצאה")
        
    top_competitors = target_fund.get("top_competitors", [])
    if not top_competitors:
        return {"draft": "לא נמצאו נתוני השוואה (מתחרים) עבור פוליסה זו בתיק הנתונים, ולכן לא ניתן להפיק טיוטה מדויקת למשא ומתן. מומלץ לוודא שהפוליסה מעודכנת או להעלות מסמך חדש."}
    
    system_prompt = """You are an expert Israeli financial insurance consultant.
Generate a concise, professional, and convincing WhatsApp draft message in Hebrew to send to the user's current insurance agent.
The goal of the WhatsApp message is to demand better matching conditions (e.g., lower management fees) or threatening to leave by explicitly citing the cheaper, better competitors we found. 
Format it politely but firmly. Do not invent names for the user or agent, leave them blank or general.
Only return the drafted text, ready to be sent."""

    user_prompt = f"""
Current Policy:
Provider: {target_fund.get("provider_name")}
Category: {target_fund.get("category")}
Track: {target_fund.get("track_name")}
Monthly Deposit: {target_fund.get("monthly_deposit")}
Balance: {target_fund.get("balance")}

Competitor Benchmarks for comparison:
{top_competitors}

Draft the WhatsApp message now:
"""

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
         return {"draft": "טיוטת וואטסאפ מדומה מטעמי מערכת חסרה."}
    
    try:
        client = genai.Client(api_key=api_key)
        
        print(f"\n--- AI CALL (INSURANCE COMPARISON) ---")
        print(f"Model: {config.GEMINI_MODEL_NAME}")
        print(f"System Prompt: {system_prompt}")
        print(f"User Prompt: {user_prompt}")
        print(f"---------------------------------------\n")
        
        print(f"🤖 [INSURANCE-AI] Calling Gemini {config.GEMINI_MODEL_NAME} for comparison draft...")
        import time
        start_ai = time.time()
        response = client.models.generate_content(
            model=config.GEMINI_MODEL_NAME,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
            ),
        )
        duration = time.time() - start_ai
        print(f"✅ [INSURANCE-AI] Gemini responded successfully in {duration:.2f}s")
        return {"draft": response.text.replace("```", "").strip()}
    except Exception as e:
        print(f"❌ [INSURANCE] Error generating whatsapp draft: {e}")
        raise HTTPException(status_code=500, detail="שגיאה ביצירת הטיוטה")
