import os
import json
import uuid
import fitz
import io
import pandas as pd
import base64
from typing import Any
from abc import ABC, abstractmethod

from flow_utils import call_claude_vision, call_gemini_json
import prompts
import report_utils
import db_manager
import config


def _parse_float(val) -> float:
    """Convert a value to float, stripping %, commas, and whitespace."""
    try:
        if val is None: return 0.0
        return float(str(val).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return 0.0


def _map_product_type_to_category(product_type: str) -> str:
    """Maps Hebrew product type string to the English category slug using keyword matching."""
    pt = (product_type or "").lower()
    if "פנסיה" in pt: return "pension"
    if "מנהלים" in pt: return "managers"
    if "השתלמות" in pt: return "study"
    if "גמל להשקעה" in pt: return "investment_provident"
    if "גמל" in pt or "תגמולים" in pt: return "provident"
    if "מניות" in pt or "ניירות ערך" in pt: return "stocks"
    
    # Fallback to config map if keywords don't match
    return config.PRODUCT_TYPE_TO_CATEGORY.get(product_type, "provident")

class BaseDocumentFlow(ABC):
    """
    Abstract base class for all document processing flows.
    """
    def __init__(self, f_profile: dict = None):
        self.f_profile = f_profile or {}
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.owner_key: str = "user"  # Default owner — may be overridden by subclasses
    
    @abstractmethod
    async def extract_data(self, file_bytes: bytes, filename: str, uid: str) -> Any:
        pass
        
    async def enrich_data(self, extracted_data: Any) -> Any:
        return extracted_data
        
    @abstractmethod
    async def analyze_and_advise(self, enriched_data: Any) -> list[dict]:
        pass
        
    @abstractmethod
    async def save_to_db(self, uid: str, final_data: Any, action_items: list[dict]):
        pass
        
    async def process(self, file_bytes: bytes, filename: str, uid: str) -> dict:
        print(f"\n🚀 [FLOW] Starting {self.__class__.__name__} for {filename}")
        
        print(f"🔄 [FLOW] Step 1/4: Extraction...")
        extracted_data = await self.extract_data(file_bytes, filename, uid)
        print(f"✅ [FLOW] Extraction completed successfully.")
        
        print(f"🔄 [FLOW] Step 2/4: Data Enrichment...")
        enriched_data = await self.enrich_data(extracted_data)
        print(f"✅ [FLOW] Data Enrichment completed successfully.")
        
        print(f"🔄 [FLOW] Step 3/4: Analysis & Advisory...")
        try:
            action_items = await self.analyze_and_advise(enriched_data)
            print(f"✅ [FLOW] Advisory completed. Generated {len(action_items)} action items.")
        except Exception as e:
            print(f"⚠️ [FLOW] Advisory failed (possibly AI Server overload): {e}. Proceeding without advisory.")
            action_items = []
        
        print(f"🔄 [FLOW] Step 4/4: Saving to Database...")
        await self.save_to_db(uid, enriched_data, action_items)
        print(f"✅ [FLOW] Database update completed successfully. Flow {self.__class__.__name__} finished!\n")
        
        c = len(enriched_data) if isinstance(enriched_data, list) else 1
        validation_warnings = getattr(self, '_validation_warnings', [])
        return {
            "status": "success",
            "flow": self.__class__.__name__,
            "extracted_count": c,
            "action_items_count": len(action_items),
            "validation_warnings": validation_warnings
        }


def _merge_funds_list(existing: list, new_funds: list) -> list:
    """Helper to merge without duplicates based on provider, track, and policy number."""
    merged = existing.copy()
    for new_fund in new_funds:
        is_dup = False
        new_provider = (new_fund.get("provider_name") or "").strip()
        new_track = (new_fund.get("track_name") or "").strip()
        new_policy = str(new_fund.get("policy_number") or "").strip()
        
        for ex in merged:
            ex_provider = (ex.get("provider_name") or "").strip()
            ex_track = (ex.get("track_name") or "").strip()
            ex_policy = str(ex.get("policy_number") or "").strip()
            
            # Match criteria: same provider AND same track
            # AND (either policy numbers match, or both are missing)
            if ex_provider == new_provider and ex_track == new_track:
                if (not ex_policy and not new_policy) or (ex_policy == new_policy):
                    is_dup = True
                    ex.update(new_fund) # Update existing
                    break
                    
        if not is_dup:
            merged.append(new_fund)
    return merged


def _validate_extraction(products: list, expected_summary: dict) -> list[str]:
    """
    Compares extracted product balances against the PDF's own summary table.
    Returns a list of warning strings for any significant discrepancies (>5% or >10,000 ILS).
    """
    CATEGORY_HEB_TO_SLUG = {
        "פנסיה": "pension",
        "ביטוח מנהלים": "managers",
        "קרן השתלמות": "study",
        "קופת גמל": "provident",
        "גמל להשקעה": "investment_provident",
    }
    if not expected_summary:
        return []
    
    # Compute actual totals from extracted products
    actual: dict[str, float] = {}
    for p in products:
        slug = _map_product_type_to_category(p.get("product_type", ""))
        actual[slug] = actual.get(slug, 0) + _parse_float(p.get("balance", 0))
    
    warnings = []
    for heb_type, expected_val in expected_summary.items():
        slug = CATEGORY_HEB_TO_SLUG.get(heb_type)
        if slug is None:
            continue
        expected_val = _parse_float(expected_val)
        if expected_val == 0:
            continue
        actual_val = actual.get(slug, 0)
        diff = abs(actual_val - expected_val)
        pct = (diff / expected_val) * 100
        if diff > 10000 and pct > 5:
            msg = (f"⚠️  [{heb_type}] Expected ₪{expected_val:,.0f} "
                   f"but extracted ₪{actual_val:,.0f} "
                   f"(diff ₪{diff:,.0f} / {pct:.1f}%)")
            print(f"🔍 [FLOW] Validation mismatch: {msg}")
            warnings.append(msg)
    
    if not warnings:
        total_extracted = sum(actual.values())
        total_expected = sum(_parse_float(v) for v in expected_summary.values())
        print(f"✅ [FLOW] Validation passed. Extracted ₪{total_extracted:,.0f} vs expected ₪{total_expected:,.0f}")
    
    return warnings


class PensionFlow(BaseDocumentFlow):
    
    def __init__(self, f_profile: dict = None):
        super().__init__(f_profile)
        self.expected_summary: dict = {}
    
    async def extract_data(self, file_bytes: bytes, filename: str, uid: str) -> list[dict]:
        # Guard: PensionFlow only processes PDFs
        filename_lower = (filename or "").lower()
        if not filename_lower.endswith(".pdf"):
            raise ValueError(
                f"קובץ הפנסיה חייב להיות בפורמט PDF. הקובץ שהועלה '{filename}' אינו PDF. "
                "אנא הורד את הדו'ח כ-PDF מהאתר ונסה שוב."
            )
        
        # 1. PII Redaction and Document Authentication
        from flow_utils import prepare_pdf_for_vision
        doc, pii_targets, authenticated_id = prepare_pdf_for_vision(file_bytes, self.f_profile)
        
        # Determine owner from the ID that unlocked the document
        if authenticated_id:
            f_pii = self.f_profile.get("pii_data", {})
            m2_id = f_pii.get("member2", {}).get("idNumber", "")
            self.owner_key = "spouse" if authenticated_id == m2_id else "user"
            print(f"👤 [FLOW] Document owner detected as '{self.owner_key}' (ID: {authenticated_id})")
        
        redacted_images_b64 = report_utils._redact_and_render_pdf(doc, pii_targets)
        
        # 2. Extract specific data
        parsed_json = call_claude_vision(
            api_key=self.anthropic_api_key,
            images_b64=redacted_images_b64,
            prompt=prompts.PENSION_EXTRACTION_PROMPT
        )
        
        # Store expected_summary for validation in save_to_db
        self.expected_summary = parsed_json.get("expected_summary", {})
        return parsed_json.get("products", [])

    async def enrich_data(self, extracted_data: list[dict]) -> list[dict]:
        # Wrap into expected dict for _collect_market_data
        temp_portfolios = {"user": {"funds": extracted_data}}
        market_data = await report_utils._collect_market_data_async(temp_portfolios)
        report_utils._attach_competitors_to_funds(temp_portfolios, market_data)
        return temp_portfolios["user"]["funds"]

    async def analyze_and_advise(self, enriched_data: list[dict]) -> list[dict]:
        if not self.gemini_api_key or not enriched_data:
            return []
            
        # Parse profile for prompt
        s1_age = 2026 - int(self.f_profile.get("spouse_1_birth_year", 1980))
        s2_age = 2026 - int(self.f_profile.get("spouse_2_birth_year", 1980)) if self.f_profile.get("spouse_2_birth_year") else "N/A"
        children_ages = []
        for child in self.f_profile.get("children", []):
            if child.get("birth_year"):
                children_ages.append(str(2026 - int(child["birth_year"])))
                
        sys_prompt = prompts.PENSION_ADVISORY_PROMPT.format(
            spouse_1_age=s1_age,
            spouse_2_age=s2_age,
            children_ages=", ".join(children_ages) if children_ages else "None",
            risk_tolerance=self.f_profile.get("risk_tolerance", "medium"),
            investment_preference=self.f_profile.get("investment_preference", "growth")
        )
        
        user_prompt = f"Portfolio: {json.dumps(enriched_data, ensure_ascii=False)}"
        
        action_items = call_gemini_json(self.gemini_api_key, sys_prompt, user_prompt)
        
        # Normalize returned items
        items_list = action_items if isinstance(action_items, list) else action_items.get("action_items", [])
        for item in items_list:
             item["is_completed"] = False
             if "id" not in item:
                 item["id"] = f"pension_{uuid.uuid4().hex[:6]}"
                 
        return items_list

    async def save_to_db(self, uid: str, final_data: list[dict], action_items: list[dict]):
        # Load existing
        existing_doc = db_manager.get_processed_portfolio(uid) or {
            "portfolios": {"user": {"funds": []}, "spouse": {"funds": []}}, 
            "action_items": []
        }
        
        # Map product_type (Hebrew) -> category (English slug) for each fund
        for fund in final_data:
            if "category" not in fund:
                fund["category"] = _map_product_type_to_category(fund.get("product_type", ""))
            if "id" not in fund:
                fund["id"] = f"pension_{uuid.uuid4().hex[:8]}"

            # --- Yield Processing Logic (Restored from old flow) ---
            # 1. Basic Mapping
            y3_cum = _parse_float(fund.get("yield_3yr_cumulative", 0))
            y3_ann = _parse_float(fund.get("yield_3yr_annualized", 0))
            y5_cum = _parse_float(fund.get("yield_5yr_cumulative", 0))
            y5_ann = _parse_float(fund.get("yield_5yr_annualized", 0))

            # Preferred: cumulative
            fund["yield_3yr"] = y3_cum if y3_cum != 0 else y3_ann
            fund["yield_5yr"] = y5_cum if y5_cum != 0 else y5_ann

            # 2. Conversion/Anti-Hallucination
            y3 = fund["yield_3yr"]
            y5 = fund["yield_5yr"]

            if y5 == 0 and y5_ann > 0:
                fund["yield_5yr"] = round(((1 + (y5_ann / 100.0)) ** 5 - 1) * 100, 2)
                print(f"🤖 [FLOW] Converted 5Y annualized ({y5_ann}%) → cumulative ({fund['yield_5yr']}%) for {fund.get('track_name')}")
            elif y3 > 0 and 0 < y5 < y3 * 0.4:
                y5_cumulative = round(((1 + (y5 / 100.0)) ** 5 - 1) * 100, 2)
                print(f"🤖 [FLOW] Anti-Hallucination: 5Y ({y5}%) << 3Y ({y3}%), likely annualized. Converting → {y5_cumulative}% for {fund.get('track_name')}")
                fund["yield_5yr"] = y5_cumulative
            # --- Layer 4: track_name Override (safety net) ---
            track_name_lower = (fund.get("track_name") or "").lower()
            if "השתלמות" in track_name_lower and fund.get("category") != "study":
                print(f"🔧 [FLOW] Override: '{fund.get('track_name')}' category forced from '{fund.get('category')}' → 'study'")
                fund["category"] = "study"
            elif "גמל להשקעה" in track_name_lower and fund.get("category") != "investment_provident":
                print(f"🔧 [FLOW] Override: '{fund.get('track_name')}' category forced → 'investment_provident'")
                fund["category"] = "investment_provident"
            # ---------------------------------------------------
        
        # Use detected owner (from auth ID) to pick the correct portfolio slot
        target_key = self.owner_key  # 'user' or 'spouse'
        
        if target_key not in existing_doc["portfolios"]:
            existing_doc["portfolios"][target_key] = {"funds": []}
        
        prev_count = len(existing_doc["portfolios"][target_key].get("funds", []))
        # A pension report is a complete snapshot — replace all existing funds for this owner
        existing_doc["portfolios"][target_key]["funds"] = final_data
        print(f"💾 [FLOW] Replaced {prev_count} old funds → {len(final_data)} new funds for portfolios.{target_key}")
        
        # Replace (rather than append) pension action items to avoid duplicates
        existing_items = existing_doc.get("action_items", [])
        # Filter out any old items starting with 'pension_'
        filtered_items = [item for item in existing_items if not str(item.get("id", "")).startswith("pension_")]
        filtered_items.extend(action_items)
        existing_doc["action_items"] = filtered_items
        
        db_manager.save_processed_portfolio(uid, existing_doc)
        # Invalidate cache so next fetch returns fresh data
        db_manager.clear_cache_for_uid(uid)
        
        # Layer 3: Validate extracted data vs PDF summary
        self._validation_warnings = _validate_extraction(final_data, self.expected_summary)


class InsuranceFlow(BaseDocumentFlow):
    
    def __init__(self, filename: str, is_spreadsheet: bool, f_profile: dict = None, target_policy_id: str = None):
        super().__init__(f_profile)
        self.filename = filename
        self.is_spreadsheet = is_spreadsheet
        self.target_policy_id = target_policy_id
        print(f"📄 [INSURANCE-FLOW] Initialized: filename={filename}, is_spreadsheet={is_spreadsheet}, target_policy_id={target_policy_id}")

    async def extract_data(self, file_bytes: bytes, filename: str, uid: str) -> Any:
        # If it's har bituach (Excel/CSV)
        if self.is_spreadsheet:
            from routers.documents import _extract_har_bituach_data # local import to reuse existing pandas logic
            return _extract_har_bituach_data(file_bytes, filename)
            
        # If it's a specific PDF policy
        else:
            print(f"📥 [INSURANCE-FLOW] Processing PDF policy: {filename} ({len(file_bytes)} bytes)")
            # 1. Upload the physical document for preservation (best-effort — same as PensionFlow)
            source_url = None
            try:
                from routers.documents import upload_to_firebase_storage
                source_url = upload_to_firebase_storage(file_bytes, uid, filename)
                print(f"☁️ [INSURANCE-FLOW] Document uploaded to storage: {source_url}")
            except Exception as storage_err:
                print(f"⚠️ [INSURANCE-FLOW] Storage upload skipped (non-fatal): {storage_err}")
            
            # 2. Extract core metadata via Claude
            print(f"🤖 [INSURANCE-FLOW] Starting Claude Vision extraction...")
            from flow_utils import prepare_pdf_for_vision
            doc, _, _ = prepare_pdf_for_vision(file_bytes, self.f_profile)
            images_b64 = []
            for page in doc[:3]: 
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                images_b64.append(base64.b64encode(pix.tobytes("png")).decode("utf-8"))
            doc.close()
            
            parsed_json = call_claude_vision(
                api_key=self.anthropic_api_key,
                images_b64=images_b64,
                prompt=prompts.POLICY_CORE_EXTRACTION_PROMPT
            )
            print(f"✅ [INSURANCE-FLOW] Claude extraction complete. Extracted data for policy.")
            parsed_json["source_document_url"] = source_url
            return parsed_json

    async def enrich_data(self, extracted_data: Any) -> Any:
        if not self.is_spreadsheet:
            return extracted_data
            
        from routers.documents import normalize_id
        
        # Group flat list from Har Bituach into user/spouse buckets
        enriched = {"user": {"funds": []}, "spouse": {"funds": []}}
        
        f_pii = self.f_profile.get("pii_data", {})
        m1_id = normalize_id(f_pii.get("member1", {}).get("idNumber", ""))
        m2_id = normalize_id(f_pii.get("member2", {}).get("idNumber", ""))
        
        m1_name = f_pii.get("member1", {}).get("name", "לא צוין שם")
        m2_name = f_pii.get("member2", {}).get("name", "לא צוין שם בן/בת זוג")
        
        for fund in extracted_data:
            fund_id = normalize_id(fund.get("owner_id", ""))
            
            # Attribute name
            if fund_id == m2_id and m2_id:
                fund["owner_name"] = m2_name
            else:
                fund["owner_name"] = m1_name
            
            # 1. Strip the actual ID number from the data before it goes to Gemini
            if "owner_id" in fund:
                del fund["owner_id"]
                
            # 2. Attribute to the correct family member
            if fund_id == m2_id and m2_id:
                enriched["spouse"]["funds"].append(fund)
            else:
                enriched["user"]["funds"].append(fund)
                
        return enriched

    async def analyze_and_advise(self, enriched_data: Any) -> list[dict]:
        # specific_policy does not generate advice directly
        if not self.is_spreadsheet or not self.gemini_api_key:
            return []
            
        # Har bituach gets analyzed
        user_prompt = f"Insurance Portfolio: {json.dumps(enriched_data, ensure_ascii=False)}"
        
        try:
            res = call_gemini_json(self.gemini_api_key, prompts.INSURANCE_HAR_BITUACH_ADVISORY_PROMPT, user_prompt)
        except RuntimeError as e:
            print(f"💥 [FLOW] Gemini insurance advisory failed after all retries: {e}")
            raise
        
        items_list = res.get("action_items", [])
        for item in items_list:
             item["is_completed"] = False
             if "id" not in item:
                 item["id"] = f"ins_{uuid.uuid4().hex[:6]}"
                 
        return items_list

    async def save_to_db(self, uid: str, final_data: Any, action_items: list[dict]):
        print(f"💾 [INSURANCE-FLOW] Saving to DB for UID: {uid}")
        existing_doc = db_manager.get_processed_portfolio(uid) or {
            "portfolios": {"user": {"funds": []}, "spouse": {"funds": []}}, 
            "action_items": []
        }
        
        if self.is_spreadsheet:
            # It's returning data mapped by owner e.g. {"user": {"funds": [...]}}
            for o_key in ["user", "spouse"]:
                new_funds = final_data.get(o_key, {}).get("funds", [])
                existing_funds = existing_doc["portfolios"].get(o_key, {}).get("funds", [])
                
                # Har Bituach files are per-citizen. Only wipe and replace if the file contains data for this person.
                if len(new_funds) > 0:
                    # Retain policies that were NOT uploaded via Har Bituach (e.g., manual or individual PDFs)
                    retained_funds = [f for f in existing_funds if f.get("source") != "har_bituach_upload"]
                    existing_doc["portfolios"][o_key]["funds"] = retained_funds + new_funds
                
            # Filter out old insurance action items so we don't duplicate alerts each Har Bituach upload
            existing_items = existing_doc.get("action_items", [])
            filtered_items = [item for item in existing_items if not str(item.get("id", "")).startswith("ins_")]
            filtered_items.extend(action_items)
            existing_doc["action_items"] = filtered_items
            
        else:
            # It's a specific policy JSON from Claude extraction
            # Robustness: Claude might return a list e.g. [{...}] if it's confused
            if isinstance(final_data, list) and len(final_data) > 0:
                final_data = final_data[0]
            
            if not isinstance(final_data, dict):
                 print(f"⚠️ [FLOW] Expected dict for specific policy, got {type(final_data)}")
                 return

            # Map Claude fields to our internal schema
            if "provider" in final_data:
                final_data["provider_name"] = final_data.pop("provider")
            if "policy_type" in final_data:
                final_data["track_name"] = final_data.pop("policy_type")
            if "monthly_premium" in final_data:
                final_data["monthly_deposit"] = final_data.pop("monthly_premium")
            
            provider = final_data.get("provider_name", "")
            found = False
            
            # 1. Try precise matching by target_policy_id if provided
            if self.target_policy_id:
                for o_key in ["user", "spouse"]:
                    for fund in existing_doc["portfolios"][o_key]["funds"]:
                        if fund.get("id") == self.target_policy_id:
                            fund["source_document_url"] = final_data.get("source_document_url")
                            # Update existing record with new metadata (preserving the ID)
                            target_id = fund.get("id")
                            fund.update(final_data)
                            fund["id"] = target_id
                            found = True
                            print(f"🎯 [FLOW] Matched specific document to policy ID: {self.target_policy_id}")
                            break
                    if found: break

            # 2. Fallback to provider name matching
            if not found:
                for o_key in ["user", "spouse"]:
                    for fund in existing_doc["portfolios"][o_key]["funds"]:
                        if fund.get("category") == "insurance" and (provider and provider in fund.get("provider_name", "")):
                            fund["source_document_url"] = final_data.get("source_document_url")
                            fund.update(final_data)
                            found = True
                            print(f"🔍 [FLOW] Matched specific document to policy via provider name: {provider}")
                            break
                    if found: break
            
            if not found:
                 print(f"⚠️ [INSURANCE-FLOW] No matching policy found for '{provider}'. Creating new record.")
                 # If no existing record matched, attach a new one
                 final_data["category"] = "insurance"
                 existing_doc["portfolios"]["user"]["funds"].append(final_data)
                 
        db_manager.save_processed_portfolio(uid, existing_doc)
        db_manager.clear_cache_for_uid(uid)
        print(f"🏁 [INSURANCE-FLOW] DB update complete.")


class AlternativeInvestmentFlow(BaseDocumentFlow):

    async def extract_data(self, file_bytes: bytes, filename: str, uid: str) -> dict:
        from routers.documents import upload_to_firebase_storage
        source_url = upload_to_firebase_storage(file_bytes, uid, filename)
        
        from flow_utils import prepare_pdf_for_vision
        doc, _, _ = prepare_pdf_for_vision(file_bytes, self.f_profile)
        images_b64 = []
        for page in doc[:10]: # Read up to 10 page business plan
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            images_b64.append(base64.b64encode(pix.tobytes("png")).decode("utf-8"))
        doc.close()
        
        parsed_json = call_claude_vision(
            api_key=self.anthropic_api_key,
            images_b64=images_b64,
            prompt=prompts.ALTERNATIVE_INVESTMENT_EXTRACTION_PROMPT
        )
        parsed_json["source_document_url"] = source_url
        return parsed_json

    async def analyze_and_advise(self, enriched_data: dict) -> list[dict]:
        return [] # No AI advisor action items for alt investments directly

    async def save_to_db(self, uid: str, final_data: dict, action_items: list[dict]):
        existing_doc = db_manager.get_processed_portfolio(uid) or {
            "portfolios": {"user": {"funds": []}, "spouse": {"funds": []}}, 
            "action_items": []
        }
        
        # Add 'alternative_investments' list if missing
        if "alternative_investments" not in existing_doc["portfolios"]["user"]:
            existing_doc["portfolios"]["user"]["alternative_investments"] = []
            
        existing_doc["portfolios"]["user"]["alternative_investments"].append(final_data)
        db_manager.save_processed_portfolio(uid, existing_doc)
        
class StocksFlow(BaseDocumentFlow):
    async def extract_data(self, file_bytes: bytes, filename: str, uid: str) -> list[dict]:
        from routers.documents import _extract_stocks
        return _extract_stocks(file_bytes, filename)

    async def analyze_and_advise(self, enriched_data: Any) -> list[dict]:
        return []

    async def save_to_db(self, uid: str, final_data: list[dict], action_items: list[dict]):
        existing_doc = db_manager.get_processed_portfolio(uid) or {
            "portfolios": {"user": {"funds": []}, "spouse": {"funds": []}}, 
            "action_items": []
        }
        
        # We wipe out any existing stocks marked as 'file_upload' and add the new ones
        existing_stocks = existing_doc.get("stocks", [])
        retained_stocks = [s for s in existing_stocks if s.get("source") != "file_upload"]
        
        existing_doc["stocks"] = retained_stocks + final_data
        
        db_manager.save_processed_portfolio(uid, existing_doc)
        db_manager.clear_cache_for_uid(uid)

        # Also sync to 'holdings' subcollection for cron job and dashboard refresh
        import datetime
        
        # Calculate aggregate totals for the Dashboard Summary
        fx_rate_dict = db_manager.get_fx_rate()
        rate = fx_rate_dict.get("rate", 3.70) if fx_rate_dict else 3.70
        
        total_value_ils = 0.0
        total_daily_pnl_ils = 0.0
        total_pnl_ils = 0.0
        total_invested_ils = 0.0

        for stock in final_data:
            symbol = stock.get("symbol")
            if not symbol: continue
            
            currency = stock.get("currency", "USD")
            r = rate if currency == "USD" else 1.0
            
            v_orig = stock.get("totalValueOriginal", 0.0)
            dp_orig = stock.get("dailyPnlOriginal", 0.0)
            tp_orig = stock.get("totalPnlOriginal", 0.0)
            
            val = v_orig * r
            total_value_ils += val
            total_daily_pnl_ils += dp_orig * r
            total_pnl_ils += tp_orig * r
            total_invested_ils += (val - (tp_orig * r))

            # Sync individual holding
            updates = {
                "current_price": stock.get("lastPrice", 0.0),
                "shares": stock.get("qty", 0.0),
                "average_cost": stock.get("avgCostPrice", 0.0),
                "last_updated": stock.get("uploaded_at", datetime.datetime.now().isoformat()),
                "name": stock.get("name", ""),
                "currency": currency
            }
            db_manager.update_family_holding(uid, symbol, updates)

        # Update the main family-level summary for the dashboard
        daily_base = total_value_ils - total_daily_pnl_ils
        daily_return_pct = (total_daily_pnl_ils / daily_base * 100) if daily_base > 0 else 0.0
        total_return_pct = (total_pnl_ils / total_invested_ils * 100) if total_invested_ils > 0 else 0.0
        
        db_manager.update_portfolio_summary(uid, total_value_ils, daily_return_pct, total_return_pct)

