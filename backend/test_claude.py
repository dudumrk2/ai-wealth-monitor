import os
import sys
import json
from anthropic import Anthropic
from dotenv import load_dotenv

def test_claude_refinement():
    print("--- 🔍 Anthropic Refinement Test (V2) ---")
    
    if not load_dotenv():
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not found.")
        return

    client = Anthropic(api_key=api_key)
    
    # New Refined Prompt from app.py
    system_prompt = """You are a financial data extraction expert. 
    Analyze the provided images of an Israeli pension report.
    
    IMPORTANT CONTEXT:
    - The images are pages from a single report, in chronological order.
    - Financial products (Pension, Provident, Study funds) often SPAN MULTIPLE PAGES. 
    - If a product's data spans multiple pages, MERGE into a single JSON entry.
    - TREAT NUMBERS CAREFULLY: Do not reverse them. "50" must stay "50".
    - Israeli reports often mix LTR numbers in RTL text.
    
    Return ONLY a valid JSON object following this STRICT schema:
    {
      "products": [
        {
          "product_type": "MUST match one of: פנסיה, מנהלים, השתלמות, גמל, גמל להשקעה",
          "provider_name": "string",
          "track_name": "string",
          "policy_number": "string",
          "balance": "number",
          "monthly_deposit": "number",
          "management_fee_deposit": "number",
          "management_fee_accumulation": "number",
          "yield_1yr": "number",
          "yield_3yr": "number",
          "yield_5yr": "number"
        }
      ]
    }"""

    print(f"🧪 Sending refinement test to claude-sonnet-4-6...")
    try:
        # Note: In a real test we'd send an image, but for prompt-only logic check we can use text
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=system_prompt,
            messages=[{"role": "user", "content": "This is a test. Provide a sample JSON with one 'פנסיה' product where the track name is 'לבני 50 ומטה'. Ensure 50 is not reversed."}]
        )
        print(f"✅ Response received:")
        print(response.content[0].text)
        
        if "50" in response.content[0].text and "05" not in response.content[0].text:
            print("\n✅ NUMBER REVERSAL TEST PASSED!")
        else:
            print("\n⚠️ Check response for number reversal issues.")
            
        print("\n--- 🏁 TEST FINISHED ---")
        
    except Exception as e:
        print(f"❌ TEST FAILED: {str(e)}")

if __name__ == "__main__":
    test_claude_refinement()
