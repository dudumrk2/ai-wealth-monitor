import datetime
import json
import os
import uuid
import prompts
from flow_utils import call_gemini_json

def generate_action_items(family_portfolio: dict, market_data: dict, family_profile: dict):
    """
    Generate actionable financial recommendations using Gemini 2.0 Flash.
    Shared logic for manual refreshes, inbox processing, and automated reports.
    """
    print("\n🤖 [AI_ADVISOR] Starting Action Item generation via Gemini...")
    
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ [AI_ADVISOR] Error: GEMINI_API_KEY not found")
        return []

    current_year = datetime.datetime.now().year
    financial_profile = family_profile.get("financial_profile", {})
    pii_data = family_profile.get("pii_data", {})
    
    # Extract names
    s1_name = pii_data.get("member1", {}).get("name", "בן/בת זוג 1")
    s2_name = pii_data.get("member2", {}).get("name", "בן/בת זוג 2")
    
    # Extract ages from financial_profile
    s1_birth_year = (
        financial_profile.get("spouse_1_birth_year")
        or financial_profile.get("spouse1BirthYear")
        or financial_profile.get("birth_year")
        or 1980
    )
    s2_birth_year = (
        financial_profile.get("spouse_2_birth_year")
        or financial_profile.get("spouse2BirthYear")
    )
    
    spouse_1_age = current_year - int(s1_birth_year) if s1_birth_year else "Unknown"
    spouse_2_age = current_year - int(s2_birth_year) if s2_birth_year else "N/A"
    
    # Children ages
    children_birth_years = (
        financial_profile.get("children_birth_years")
        or financial_profile.get("children")
        or []
    )
    children_ages = []
    for b_year in children_birth_years:
        year = None
        if isinstance(b_year, dict):
            year = b_year.get("birth_year") or b_year.get("birthYear")
        else:
            year = b_year
        if year:
            children_ages.append(str(current_year - int(year)))

    # Formatting system prompt using the shared PENSION_ADVISORY_PROMPT
    sys_prompt = prompts.PENSION_ADVISORY_PROMPT.format(
        spouse_1_name=s1_name,
        spouse_1_age=spouse_1_age,
        spouse_2_name=s2_name,
        spouse_2_age=spouse_2_age,
        children_ages=", ".join(children_ages) if children_ages else "None",
        risk_tolerance=financial_profile.get("risk_tolerance", "medium"),
        investment_preference=financial_profile.get("investment_preference", "growth")
    )

    # Build owner-aware portfolio structure
    portfolio_by_owner = {
        "member_1": {
            "name": s1_name,
            "role": "user",
            "funds": family_portfolio.get("user", {}).get("funds", [])
        },
        "member_2": {
            "name": s2_name,
            "role": "spouse",
            "funds": family_portfolio.get("spouse", {}).get("funds", [])
        }
    }
    
    user_prompt = f"Family Portfolio: {json.dumps(portfolio_by_owner, ensure_ascii=False)}"
    
    try:
        print("🧠 [AI_ADVISOR] Sending request to Gemini...")
        raw_result = call_gemini_json(gemini_api_key, sys_prompt, user_prompt)
        
        # Normalize returned items
        items_list = raw_result if isinstance(raw_result, list) else raw_result.get("action_items", [])
        
        for item in items_list:
            item["is_completed"] = False
            # Ensure every pension item has a 'pension_' prefix for correct replacement logic
            orig_id = item.get("id", uuid.uuid4().hex[:6])
            if not str(orig_id).startswith("pension_"):
                item["id"] = f"pension_{orig_id}"
            else:
                item["id"] = orig_id
                
        print(f"✅ [AI_ADVISOR] Successfully generated {len(items_list)} action items.")
        return items_list
        
    except Exception as e:
        print(f"💥 [AI_ADVISOR] Error generating action items: {e}")
        return []

def filter_pension_items(existing_items: list) -> list:
    """Returns a new list with all pension/wealth items removed, preserving insurance/alt items."""
    def is_pension_item(item):
        iid = str(item.get("id", ""))
        if iid.startswith("pension_"): return True
        # Legacy patterns detected in DB: fee_spouse, strategy_user, risk_david, etc.
        legacy_keywords = ["fee_", "strategy_", "risk_", "david_", "inbar_", "consolidate_", "insurance_survivors"]
        if any(keyword in iid for keyword in legacy_keywords) and not iid.startswith("ins_"):
            return True
        return False

    return [item for item in existing_items if not is_pension_item(item)]

async def run_family_advisory(uid: str, family_profile: dict):
    """Load the full family portfolio from Firestore and run the AI advisor."""
    import db_manager
    from report_utils import _collect_market_data_async, _attach_competitors_to_funds

    print(f"\n🧠 [AI_ADVISOR] Running full family advisory for {uid}")
    portfolio_doc = db_manager.get_processed_portfolio(uid)
    if not portfolio_doc:
        print(f"⚠️ [AI_ADVISOR] No portfolio doc found for {uid}")
        return {"status": "skipped", "reason": "no_portfolio_doc"}
        
    try:
        portfolios = portfolio_doc.get("portfolios", {})
        
        # Market enrichment
        live_market_data = await _collect_market_data_async(portfolios)
        _attach_competitors_to_funds(portfolios, live_market_data)

        # AI call with full family data
        action_items = generate_action_items(portfolios, live_market_data, family_profile)
        
        # Update pension action items using shared filter
        existing_items = portfolio_doc.get("action_items", [])
        filtered_items = filter_pension_items(existing_items)
        
        filtered_items.extend(action_items)
        portfolio_doc["action_items"] = filtered_items
        
        db_manager.save_processed_portfolio(uid, portfolio_doc)
        print(f"✅ [AI_ADVISOR] Saved {len(action_items)} new action items to DB for {uid}")
        return {"status": "success", "action_items_count": len(action_items)}
    except Exception as e:
        print(f"💥 [AI_ADVISOR] Family advisory failed for {uid}: {e}")
        return {"status": "error", "reason": str(e)}
