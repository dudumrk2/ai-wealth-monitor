import os
import re
import json
import base64
import asyncio
import difflib
import fitz  # PyMuPDF
from anthropic import Anthropic

import market_data as market_data_module

import config

def _get_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()

def _is_index_mismatch(pdf_name: str, api_name: str) -> bool:
    """Returns True if the API fund is an index tracker but the PDF fund is not."""
    is_api_index = any(word in api_name for word in ["עוקב", "מדד", "S&P", "500", "s&p"])
    is_pdf_index = any(word in pdf_name for word in ["עוקב", "מדד", "S&P", "500", "s&p"])
    return is_api_index and not is_pdf_index

def _parse_float(val) -> float:
    """Convert a value to float, stripping %, commas, and whitespace."""
    try:
        return float(str(val).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return 0.0

def _redact_and_render_pdf(doc, target_strings: list[str]) -> list[str]:
    """
    Redact PII (target_strings) from a PDF document and render remaining pages as Base64 PNGs.
    Skips the first PDF_SKIP_PAGES pages if the document is long enough.
    Skips individual pages that fail to render.
    Closes the document before returning.
    """
    redacted_images_b64 = []
    start_page = config.PDF_SKIP_PAGES if len(doc) > config.PDF_SKIP_PAGES else 0
    skipped = 0

    for page_num in range(start_page, len(doc)):
        try:
            page = doc[page_num]
            if target_strings:
                for text in target_strings:
                    if not text or len(text.strip()) < 2:
                        continue
                    for inst in page.search_for(text):
                        page.draw_rect(inst, color=(0, 0, 0), fill=(0, 0, 0))
            
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            redacted_images_b64.append(base64.b64encode(img_data).decode("utf-8"))
        except Exception as page_err:
            skipped += 1
            print(f"⚠️ [REPORT_UTILS] Skipping page {page_num} due to render error: {page_err}")

    doc.close()
    if skipped:
        print(f"⚠️ [REPORT_UTILS] Rendering completed with {skipped} skipped page(s). Got {len(redacted_images_b64)} usable image(s).")
    return redacted_images_b64

def _extract_funds_via_ai(redacted_images_b64: list[str], api_key: str, source_id_prefix: str) -> list[dict]:
    """
    Sends redacted images to Claude Vision, parses the JSON response,
    and maps the products to the expected fund_data schema.
    """
    print("🧠 [REPORT_UTILS] Sending redacted images to Claude for extraction...")

    if not redacted_images_b64:
        raise ValueError(
            "לא ניתן היה לעבד את קובץ ה-PDF: כל הדפים נכשלו בעת הרינדור (ייתכן שהקובץ פגום, מוצפן, או שנוצר בפורמט לא נתמך). "
            "נסה לפתוח את הקובץ ב-Adobe Reader ולשמור אותו מחדש לפני ההעלאה."
        )

    anthropic_client = Anthropic(api_key=api_key)
    
    content_blocks = []
    for b64 in redacted_images_b64[:10]:
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })
    content_blocks.append({"type": "text", "text": "חלץ את כל המוצרים הפיננסיים מהדפים האלה. החזר JSON תקני בלבד."})

    response = anthropic_client.messages.create(
        model=config.CLAUDE_MODEL_NAME,
        max_tokens=4096,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content_blocks}],
    )

    response_text = response.content[0].text.strip()
    response_text = re.sub(r'^```(?:json)?\s*', '', response_text, flags=re.MULTILINE)
    response_text = re.sub(r'```\s*$', '', response_text, flags=re.MULTILINE).strip()

    start_idx = response_text.find('{')
    if start_idx == -1:
        raise ValueError(f"No JSON in Anthropic response: {response_text[:200]}")
    try:
        pension_data, _ = json.JSONDecoder().raw_decode(response_text, start_idx)
    except json.JSONDecodeError:
        brace_count = 0
        end_idx = start_idx
        for i, ch in enumerate(response_text[start_idx:], start_idx):
            if ch == '{': brace_count += 1
            elif ch == '}': brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break
        pension_data = json.loads(response_text[start_idx:end_idx])

    products = pension_data.get("products", [])
    print(f"✅ [REPORT_UTILS] AI Extraction SUCCESS. Found {len(products)} products.")
    
    extracted_funds = []
    for p in products:
        raw_type = p.get("product_type", "")
        if "פנסיה" in raw_type:            category = "pension"
        elif "מנהלים" in raw_type:         category = "managers"
        elif "השתלמות" in raw_type:        category = "study"
        elif "גמל להשקעה" in raw_type:     category = "investment_provident"
        elif "גמל" in raw_type:            category = "provident"
        else:                              category = "provident"

        fund_data = {
            "id": f"{source_id_prefix}_{os.urandom(2).hex()}",
            "category": category,
            "provider_name": p.get("provider_name", "Unknown"),
            "track_name": p.get("track_name", "Unknown"),
            "track_id": p.get("track_id", ""),
            "status": "active",
            "balance": p.get("balance", 0),
            "monthly_deposit": p.get("monthly_deposit", 0),
            "management_fee_deposit": p.get("management_fee_deposit", 0),
            "management_fee_accumulation": p.get("management_fee_accumulation", 0),
            "yield_1yr": p.get("yield_1yr", 0),
            "yield_3yr": p.get("yield_3yr_cumulative", p.get("yield_3yr", 0)),
            "yield_5yr": p.get("yield_5yr_cumulative", p.get("yield_5yr", 0)),
            "sharpe_ratio": p.get("sharpe_ratio", 0),
            "policy_number": p.get("policy_number", ""),
        }
        
        # Clean float values and apply anti-hallucination correction
        fund_data["yield_1yr"] = _parse_float(fund_data["yield_1yr"])
        fund_data["yield_3yr"] = _parse_float(fund_data["yield_3yr"])
        fund_data["yield_5yr"] = _parse_float(fund_data["yield_5yr"])
        
        y3 = fund_data["yield_3yr"]
        y5 = fund_data["yield_5yr"]
        y5_ann = _parse_float(p.get("yield_5yr_annualized", 0))
        
        if y5 == 0 and y5_ann > 0:
            fund_data["yield_5yr"] = round(((1 + (y5_ann / 100.0)) ** 5 - 1) * 100, 2)
            print(f"🤖 [REPORT_UTILS] Converted 5Y annualized ({y5_ann}%) → cumulative ({fund_data['yield_5yr']}%) for {fund_data['track_name']}")
        elif y3 > 0 and 0 < y5 < y3 * 0.4:
            y5_cumulative = round(((1 + (y5 / 100.0)) ** 5 - 1) * 100, 2)
            print(f"🤖 [REPORT_UTILS] Anti-Hallucination: 5Y ({y5}%) << 3Y ({y3}%), likely annualized. Converting → {y5_cumulative}% for {fund_data['track_name']}")
            fund_data["yield_5yr"] = y5_cumulative

        extracted_funds.append(fund_data)

    return extracted_funds

def _collect_market_data(portfolios: dict) -> dict:
    """Synchronous wrapper for market data collection."""
    print("\n📊 [REPORT_UTILS] Collecting market competitor data (sync)...")
    try:
        return asyncio.run(_collect_market_data_async(portfolios))
    except Exception as e:
        print(f"⚠️ [REPORT_UTILS] market data failed: {e}")
        return {}

async def _collect_market_data_async(portfolios: dict) -> dict:
    """Async-native version of market data collection."""
    print("\n📊 [REPORT_UTILS] Collecting market competitor data for all tracks (async)...")

    tasks: list[tuple[str, str]] = []
    for owner_key in ["user", "spouse"]:
        for fund in portfolios.get(owner_key, {}).get("funds", []):
            tasks.append((
                fund.get("category", ""),
                fund.get("track_name", ""),
            ))

    if not tasks:
        return {}

    results: dict = {}
    try:
        for product_type, track_name in tasks:
            if track_name and track_name not in results:
                competitors = await market_data_module.get_top_competitors(
                    product_type=product_type,
                    track_name=track_name,
                )
                results[track_name] = competitors
        return results
    except Exception as e:
        print(f"⚠️ [REPORT_UTILS] Market data collection failed: {e}.")
        return {}

def _attach_competitors_to_funds(portfolios: dict, market_data: dict) -> None:
    if not market_data:
        return

    print("🔗 [REPORT_UTILS] Attaching competitor data to individual funds...")
    for owner_key in ["user", "spouse"]:
        funds = portfolios.get(owner_key, {}).get("funds", [])
        for fund in funds:
            track = fund.get("track_name")
            if track and track in market_data:
                track_data = market_data[track]
                fund["top_competitors"] = track_data.get("top_competitors", [])
                
                user_provider = fund.get("provider_name", "").strip()
                track_id = str(fund.get("track_id", "") or "").strip()
                track_name_for_match = track or user_provider
                match = None
                best_score = 0
                
                for comp in track_data.get("all_competitors", []):
                    comp_provider = comp.get("provider_name", "")
                    comp_name = comp.get("fund_name", "")
                    comp_id = str(comp.get("fund_id", "") or "").strip()
                    
                    if track_id and comp_id and track_id == comp_id:
                        match = comp
                        break
                    
                    if user_provider and comp_provider:
                        p1 = user_provider.split(" ")[0].replace('"', '')
                        p2 = comp_provider.split(" ")[0].replace('"', '')
                        p_match = p1 == p2 or user_provider in comp_provider or comp_provider in user_provider
                        if not p_match:
                            continue
                            
                    if _is_index_mismatch(track_name_for_match, comp_name):
                        continue
                        
                    score = _get_similarity(track_name_for_match, comp_name)
                    if score > best_score:
                        best_score = score
                        match = comp
                
                is_exact_match = (match and track_id and str(match.get("fund_id", "")) == track_id)
                if match and not is_exact_match and best_score < 0.3:
                    match = None
                        
                if match:
                    fund["sharpe_ratio"] = match.get("sharpe_ratio", fund.get("sharpe_ratio"))

EXTRACTION_SYSTEM_PROMPT = """
אתה מומחה לחילוץ נתונים פיננסיים מדוחות פנסיה ישראליים.
חלץ את כל המוצרים הפיננסיים מהדוח והחזר JSON תקני בלבד.
שים לב: דוח יחיד יכול להכיל מס' מוצרים שונים. למשל, ב"ביטוח מנהלים" תחת אותה פוליסה יכולים להיות מספר מסלולים, או ב"קרן השתלמות" מספר חשבונות נפרדים. חלץ אותם כמוצרים נפרדים במערך "products".

המבנה חייב להיות:
{
  "products": [
    {
      "product_type": "string (סוג המוצר בעברית: פנסיה/ביטוח מנהלים/קרן השתלמות/קופת גמל/גמל להשקעה)",
      "provider_name": "string (שם חברת הביטוח/בית ההשקעות)",
      "track_name": "string (שם המסלול)",
      "track_id": "string (קוד מסלול / מספר אישור משרד האוצר - חלץ במידה וקיים בדוח, אחרת השאר מחרוזת ריקה)",
      "policy_number": "string",
      "balance": number, # סך צבירה (Total Balance)
      "monthly_deposit": number, # הפקדה חודשית (Monthly Deposit)
      "management_fee_deposit": number,
      "management_fee_accumulation": number,
      "yield_1yr": number, # תשואה ל-12 חודשים האחרונים
      "yield_3yr_cumulative": number, # תשואה מצטברת (Cumulative) ל-3 שנים
      "yield_3yr_annualized": number, # תשואה שנתית ממוצעת (Average Annual) ל-3 שנים
      "yield_5yr_cumulative": number, # תשואה מצטברת (Cumulative) ל-5 שנים
      "yield_5yr_annualized": number, # תשואה שנתית ממוצעת (Average Annual) ל-5 שנים
      "sharpe_ratio": number # מדד שארפ (Sharpe Ratio)
    }
  ]
}

הנחיות קריטיות - קרא בעיון:
1. הפקדות (monthly_deposit):
   - חלץ אך ורק *הפקדה חודשית ממוצעת או אחרונה* (למשל 1,500 \u20aa). 
   - סכנה: דוחות רבים מציגים "סך הפקדות בשנת הדיווח" או "הפקדות שוטפות" שהם בסכומים גבוהים מאוד (למשל 47,000 \u20aa). לעולם אל תחלץ סכומים שנתיים מצטברים אלו לתוך monthly_deposit! אם לא כתוב במפורש מה ההפקדה החודשית, השאר את field זה כ-0.
2. תשואות (Yields):
   - קיימים שני מונחים: "תשואה מצטברת" (Cumulative, לרוב מספר גבוה כמו 50%+) ו"תשואה שנתית ממוצעת" (Annualized, לרוב מספר נמוך כמו 10%).
   - הקפד לשים כל נתון בשדה המתאים (cumulative מול annualized).
   - חלץ בדיוק את המספר שמופיע בדוח בעמודה המתאימה ל-3 ול-5 שנים. אין להמציא ערכים.
3. מדד שארפ: חלץ את הערך המופיע בדוח. אם לא מופיע, החזר 0.

CRITICAL FORMATTING:
- החזר JSON תקני בלבד ללא בלוקים של markdown (ללא ```json) וללא כל טקסט חופשי.
- אל תכניס פסיקים או פסיק עליון במספרים (החזר 1234.56 במקום 1,234.56).
- אם שדה כלשהו לא מופיע בדוח, יש להחזיר 0 עבור מספרים ו-"" עבור מחרוזות. אל תשמיט שדות ממבנה ה-JSON הנדרש.
"""
