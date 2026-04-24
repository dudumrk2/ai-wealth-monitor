from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, List, Optional
import os
import json
import asyncio
import time
import httpx
import fitz

from google import genai
from google.genai import types
import db_manager
from auth import verify_token
import config
from services.demo_constants import DEMO_CHAT_RESPONSES

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
    
    # --- DEMO BYPASS ---
    if uid == config.DEMO_UID:
        q = request.question.lower()
        if "פנסיה" in q or "קרן" in q or "חיסכון" in q or "גמל" in q or "השתלמות" in q:
            ans = DEMO_CHAT_RESPONSES["pension"]
        elif "מניה" in q or "בורסה" in q or "תיק" in q:
            ans = DEMO_CHAT_RESPONSES["stocks"]
        elif "ביטוח" in q:
            ans = DEMO_CHAT_RESPONSES["insurance"]
        else:
            ans = DEMO_CHAT_RESPONSES["default"]
        return {"response": ans}

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

    # Build owner name map from portfolio root ownerName fields (set by PensionFlow / migration script)
    user_owner_name   = portfolios.get("user",   {}).get("ownerName", "משתמש ראשי")
    spouse_owner_name = portfolios.get("spouse", {}).get("ownerName", "בן/בת הזוג")

    system_prompt = f"""You are an expert family wealth advisor (Copilot).
Answer the user's question concisely in Hebrew, based ONLY on the provided financial data. 
If the user asks a deep contractual question requiring full details of a specific policy, use the `read_full_policy` tool with the policy's ID.

OWNER IDENTIFICATION — VERY IMPORTANT:
The financial data is organized hierarchically under "user" and "spouse" objects.
- The "user" object belongs to: {user_owner_name}
- The "spouse" object belongs to: {spouse_owner_name}
When the user asks about a specific person (e.g. "Does {user_owner_name} have a pension?"),
look for funds inside the object whose ownerName matches that person's name.

Data: {json.dumps(context_data, ensure_ascii=False)}
"""

    def read_full_policy(policy_id: str) -> str:
        """Call this tool to read the full text of a specific policy PDF document to answer deep contractual questions.
        Args:
            policy_id: The ID or policy number of the policy to read.
        """
        print(f"🛠️ [TOOL] read_full_policy called for {policy_id}")
        url = None
        for f in filtered_funds:
            if f.get("id") == policy_id or f.get("policy_number") == policy_id:
                url = f.get("source_document_url")
                break

        if not url:
            return f"Error: No source document URL found for policy {policy_id}. Cannot read document."

        try:
            resp = httpx.get(url, timeout=30.0)
            resp.raise_for_status()
            pdf_bytes = resp.content
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_content = ""
            for page in doc:
                text_content += page.get_text()
            doc.close()
            if len(text_content) > 35000:
                print(f"⚠️ [TOOL] Document text truncated (original length: {len(text_content)})")
                return "[DOCUMENT TRUNCATED DUE TO LENGTH]\n" + text_content[:35000]
            return text_content
        except Exception as e:
            return f"Error reading document: {str(e)}"

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ [CHAT] GEMINI_API_KEY not configured. Returning mock response.")
        return {"response": f"זוהי תשובת מערכת לדוגמה (חסר מפתח GEMINI_API_KEY). ההקשר שלך מבוסס על {len(filtered_funds)} מוצרים בקטגוריית {request.context_filter}."}
        
    try:
        client = genai.Client(api_key=api_key)
        max_retries = 5
        
        # Use chats.create to support automatic tool execution loop
        chat = client.chats.create(
            model=config.GEMINI_MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[read_full_policy],
                temperature=0.3
            )
        )
        
        for attempt in range(max_retries):
            try:
                print(f"\n--- AI CALL (COPILOT) ---")
                print(f"Model: {config.GEMINI_MODEL_NAME}")
                print(f"System Prompt: {system_prompt[:500]}...")
                print(f"User Question: {request.question}")
                print(f"-------------------------\n")
                
                print(f"🤖 [CHAT-AI] Sending question to Gemini {config.GEMINI_MODEL_NAME} (Attempt {attempt + 1}/{max_retries})...")
                start_ai = time.time()
                response = chat.send_message(request.question)
                duration = time.time() - start_ai
                print(f"✅ [CHAT-AI] Gemini responded successfully in {duration:.2f}s")
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

class AdvisorChatRequest(BaseModel):
    family_id: str
    question: str

@router.get("/api/chat/advisor/history")
async def get_advisor_chat_history(family_id: str, limit: int = 50, user: dict = Depends(verify_token)):
    uid = user.get("uid")
    # Verify user can access this family_id or it's their own
    if family_id != "CURRENT_UID" and family_id != uid:
        pass # In a real app check permissions, here assume uid
    uid_to_use = uid if family_id == "CURRENT_UID" else uid
    
    msgs = db_manager.get_chat_history(uid_to_use, limit=limit)
    return {"history": msgs}

@router.post("/api/chat/advisor")
async def copilot_advisor_chat(request: AdvisorChatRequest, user: dict = Depends(verify_token)):
    uid = user.get("uid")
    
    # --- DEMO BYPASS ---
    if uid == config.DEMO_UID:
        reply = "אני יועץ ה-AI שלכם בסביבת הדמו. כאן תוכלו לראות איך אני מנתח את תיק ההשקעות שלכם ומציע תובנות. בגרסה האמיתית, אנתח עבורכם שינויים בשוק, אשווה בין מסלולי השקעה ואעזור לכם לקבל החלטות מושכלות."
        db_manager.save_chat_message(config.DEMO_UID, "user", request.question)
        db_manager.save_chat_message(config.DEMO_UID, "model", reply)
        return {"response": reply}

    uid_to_use = uid if request.family_id == "CURRENT_UID" else uid
    
    # 1. Fetch current portfolio context
    portfolio_doc = db_manager.get_processed_portfolio(uid_to_use)
    if not portfolio_doc:
        stocks_data = []
    else:
        stocks_data = portfolio_doc.get("stocks", [])
        
    portfolio_json_str = json.dumps(stocks_data, ensure_ascii=False)
    
    # 2. Get the prompt from prompts.py
    from prompts import ADVISOR_SYSTEM_PROMPT
    system_prompt = ADVISOR_SYSTEM_PROMPT.format(current_portfolio_json_string=portfolio_json_str)
    
    # 3. Save user's message to history
    db_manager.save_chat_message(uid_to_use, "user", request.question)
    
    # 4. Fetch last few conversation turns for context
    raw_history = db_manager.get_chat_history(uid_to_use, limit=10)
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
         print("⚠️ [CHAT] GEMINI_API_KEY not configured.")
         mock_res = "זוהי תגובת מערכת לדוגמה (חסר מפתח GEMINI). אנא הגדר מפתח."
         db_manager.save_chat_message(uid_to_use, "model", mock_res)
         return {"response": mock_res}
         
    try:
        client = genai.Client(api_key=api_key)
        
        # Format history for Gemini SDK — all turns except the one we just saved (current user message)
        history_contents = []
        for msg in raw_history[:-1]:
             role = msg.get("role", "user")
             if role not in ["user", "model"]: role = "user"
             history_contents.append(types.Content(role=role, parts=[types.Part(text=msg.get("text", ""))]))


        chat = client.chats.create(
            model=config.GEMINI_MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3
            ),
            history=history_contents
        )
        
        print(f"\n--- AI CALL (ADVISOR) ---")
        print(f"Model: {config.GEMINI_MODEL_NAME}")
        print(f"System Prompt: {system_prompt[:500]}...")
        print(f"User Question: {request.question.strip()}")
        print(f"-------------------------\n")
        
        print(f"🤖 [CHAT-ADVISOR] Sending question to Gemini {config.GEMINI_MODEL_NAME}...")
        response = chat.send_message(request.question)
        
        reply = response.text
        # Save model's reply
        db_manager.save_chat_message(uid_to_use, "model", reply)
        
        return {"response": reply}
        
    except Exception as e:
        print(f"❌ [CHAT-ADVISOR] Error: {e}")
        err_msg = "מצטער, חלה שגיאה ביצירת התשובה."
        db_manager.save_chat_message(uid_to_use, "model", err_msg)
        return {"response": err_msg}
