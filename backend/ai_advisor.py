import datetime
import json
import os
import uuid
import prompts
from flow_utils import call_gemini_json

def generate_action_items(family_portfolio: dict, market_data: dict, financial_profile: dict):
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
        spouse_1_age=spouse_1_age,
        spouse_2_age=spouse_2_age,
        children_ages=", ".join(children_ages) if children_ages else "None",
        risk_tolerance=financial_profile.get("risk_tolerance", "medium"),
        investment_preference=financial_profile.get("investment_preference", "growth")
    )

    # Flatten portfolio for easier AI consumption
    all_funds = (
        family_portfolio.get("user", {}).get("funds", []) +
        family_portfolio.get("spouse", {}).get("funds", [])
    )
    
    user_prompt = f"Portfolio: {json.dumps(all_funds, ensure_ascii=False)}"
    
    try:
        print("🧠 [AI_ADVISOR] Sending request to Gemini...")
        raw_result = call_gemini_json(gemini_api_key, sys_prompt, user_prompt)
        
        # Normalize returned items
        items_list = raw_result if isinstance(raw_result, list) else raw_result.get("action_items", [])
        
        for item in items_list:
            item["is_completed"] = False
            if "id" not in item:
                item["id"] = f"pension_{uuid.uuid4().hex[:6]}"
                
        print(f"✅ [AI_ADVISOR] Successfully generated {len(items_list)} action items.")
        return items_list
        
    except Exception as e:
        print(f"💥 [AI_ADVISOR] Error generating action items: {e}")
        return []
