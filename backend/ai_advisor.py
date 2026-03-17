import datetime
import json
import os
import re
from anthropic import Anthropic

def generate_action_items(family_portfolio, market_data, financial_profile):
    """
    Generate actionable financial recommendations using Anthropic Claude.
    """
    print("\n🤖 [AI_ADVISOR] Starting Action Item generation...")
    print(f"DEBUG: Financial Profile received: {json.dumps(financial_profile, indent=2, ensure_ascii=False)}")
    
    current_year = datetime.datetime.now().year
    
    # Extract ages from financial_profile
    # Supports both snake_case (Firestore) and camelCase (legacy) key names
    s1_birth_year = (
        financial_profile.get("spouse_1_birth_year")
        or financial_profile.get("spouse1BirthYear")
        or financial_profile.get("birthYear")
    )
    s2_birth_year = (
        financial_profile.get("spouse_2_birth_year")
        or financial_profile.get("spouse2BirthYear")
    )
    
    spouse_1_age = current_year - int(s1_birth_year) if s1_birth_year else "Unknown"
    spouse_2_age = current_year - int(s2_birth_year) if s2_birth_year else "N/A"
    
    # Supports both "children_birth_years" (Firestore) and "children" (legacy)
    children_birth_years = (
        financial_profile.get("children_birth_years")
        or financial_profile.get("children")
        or []
    )
    children_ages = []
    print(f"DEBUG: Processing {len(children_birth_years)} children birth years...")
    for b_year in children_birth_years:
        year = None
        if isinstance(b_year, dict):
            year = b_year.get("birthYear") or b_year.get("birth_year")
        else:
            year = b_year
        
        if year:
            age = current_year - int(year)
            children_ages.append(age)
    
    # Supports both snake_case (Firestore) and camelCase (legacy)
    risk_tolerance = (
        financial_profile.get("risk_tolerance")
        or financial_profile.get("riskTolerance")
        or "medium"
    )
    investment_preference = (
        financial_profile.get("investment_preference")
        or financial_profile.get("investmentPreference")
        or "balanced"
    )
    
    print(f"✅ [AI_ADVISOR] Calculated Context: Spouse1_Age={spouse_1_age}, Spouse2_Age={spouse_2_age}, Children_Ages={children_ages}")
    print(f"Risk: {risk_tolerance}, Goal: {investment_preference}")

    # Build System Prompt

    system_prompt = f"""
You are an elite, fiduciary Israeli Pension Consultant and Wealth Manager.
Your objective is to deeply analyze the family's portfolio and provide highly specific, actionable insights.

CRITICAL FAMILY CONTEXT: 
- Spouse 1 is {spouse_1_age} years old. 
- Spouse 2 is {spouse_2_age} years old (if applicable). 
- Children ages: {children_ages}. 
- Risk tolerance is '{risk_tolerance}'.
- Investment goal is '{investment_preference}'.

ANALYTICAL FRAMEWORK (What to look for):
1. Management Fees (דמי ניהול): Identify any product where fees are above the Israeli market average. Suggest negotiation or moving to a cheaper provider/track.
2. Risk vs. Age Alignment: If the spouses are relatively young and have a 'high' or 'growth' risk tolerance, but their money is in solid/general tracks, strongly recommend moving to equity/S&P500 tracks to maximize compound interest. Conversely, ensure capital preservation for older ages.
3. Insurance Gaps/Overlaps (פנסיית שאירים): Use the children's ages. If children are nearing or over 21, explicitly suggest reducing/canceling the survivor's pension coverage for them to save money and increase the savings portion.
4. Tax & Product Optimization: Suggest maximizing Keren Hishtalmut contributions (tax-free capital gains) or utilizing Kupat Gemel LeHaskaa for liquidity, if relevant.
5. Consolidation (איחוד קופות): Identify inactive accounts (no recent deposits) with high fees that should be merged.

ADVISOR INSTRUCTIONS:
- Generate between 1 and 6 highly impactful, data-driven action items. Only output recommendations that truly add value based on the data.
- Sort the action items descending by severity, with 'high' severity items first.
- Base every recommendation purely on the provided data and family context. Do not invent numbers.

    OUTPUT ENFORCEMENT:
    Return ONLY a valid JSON array matching this exact schema:
    ```json
    [
      {{
        "id": "string (generate a unique short ID, e.g., 'fee_1', 'risk_2')",
        "type": "fee_negotiation | investment_strategy | insurance | tax_optimization",
        "title": "string (Clear, short action title in Hebrew)",
        "problem_explanation": "string (Detailed explanation in Hebrew of WHY this is an issue or opportunity, what the data shows)",
        "action_required": "string (Detailed explanation in Hebrew of WHAT exactly the user needs to do to resolve it)",
        "is_completed": false,
        "severity": "high | medium | low"
      }}
    ]
    Return ONLY the JSON array. Do not include markdown formatting like ```json or any conversational text.
    """

    # Prepare user content
    user_content = f"""
Market Data: {json.dumps(market_data, ensure_ascii=False)}
Family Portfolio: {json.dumps(family_portfolio, ensure_ascii=False)}

Generate the 3 action items now.
"""
    
    print("\n--- CLAUDE SYSTEM PROMPT ---")
    print(system_prompt)
    print("--- END SYSTEM PROMPT ---")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ [AI_ADVISOR] Error: ANTHROPIC_API_KEY not found")
        return []

    try:
        client = Anthropic(api_key=api_key)
        print("🧠 [AI_ADVISOR] Sending request to Claude 3.5 Sonnet...")
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}]
        )
        
        response_text = response.content[0].text.strip()
        
        # Strip markdown code blocks if Claude wrapped the response
        response_text = re.sub(r'^```(?:json)?\s*', '', response_text, flags=re.MULTILINE)
        response_text = re.sub(r'```\s*$', '', response_text, flags=re.MULTILINE)
        response_text = response_text.strip()
        
        print("\n--- CLAUDE RAW RESPONSE ---")
        print(response_text)
        print("--- END RAW RESPONSE ---")
        
        # Parse JSON array
        start = response_text.find('[')
        end = response_text.rfind(']') + 1
        if start == -1 or end == 0:
            print(f"❌ [AI_ADVISOR] Error: Claude did not return a valid JSON array.")
            return []
            
        action_items = json.loads(response_text[start:end])
        print(f"✅ [AI_ADVISOR] Successfully parsed {len(action_items)} action items.")
        return action_items
        
    except Exception as e:
        print(f"💥 [AI_ADVISOR] Error generating action items: {e}")
        return []
