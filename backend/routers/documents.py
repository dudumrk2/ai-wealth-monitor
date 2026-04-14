from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
import datetime
import os
import uuid
import time
import json
import urllib.parse
from typing import List, Optional
import io
import pandas as pd

import fitz
import firebase_admin
from firebase_admin import storage

import db_manager
from auth import verify_token
import ai_advisor
import config

router = APIRouter(tags=["documents"])

def upload_to_firebase_storage(pdf_bytes: bytes, uid: str, filename: str) -> str:
    """Uploads bytes to Firebase Cloud Storage and returns a persistent download URL."""
    bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET")
    if not bucket_name:
         # Fallback inference if env var isn't explicitly set
         try:
             app = firebase_admin.get_app()
             # Use the modern .firebasestorage.app suffix provided by user
             bucket_name = f"{app.project_id}.firebasestorage.app"
         except Exception:
             bucket_name = "ai-wealth-monitor.firebasestorage.app" # fallback standard
             
    print(f"☁️ [STORAGE] Attempting upload to bucket: {bucket_name}")
    
    bucket = storage.bucket(bucket_name)
    blob_name = f"policies/{uid}/{uuid.uuid4().hex}_{filename}"
    blob = bucket.blob(blob_name)
    
    # Construct an access token matching the Web SDK's style
    token = str(uuid.uuid4())
    blob.metadata = {"firebaseStorageDownloadTokens": token}
    
    blob.upload_from_string(pdf_bytes, content_type="application/pdf")
    print(f"✅ [STORAGE] Uploaded {blob_name} to Firebase.")
    
    encoded_name = urllib.parse.quote(blob_name, safe='')
    return f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded_name}?alt=media&token={token}"

def _extract_har_bituach_data(file_bytes: bytes, filename: str) -> List[dict]:
    """
    Deterministic extraction from Israeli 'Har Bituach' CSV/Excel.
    Expects headers at row 4 (skiprows=3).
    """
    try:
        is_csv = filename.lower().endswith('.csv')
        
        # Load raw data without headers
        if is_csv:
            try:
                df_raw = pd.read_csv(io.BytesIO(file_bytes), header=None, encoding='utf-8-sig', dtype=str)
            except:
                df_raw = pd.read_csv(io.BytesIO(file_bytes), header=None, encoding='cp1255', dtype=str)
        else:
            df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=str)
            
        # Find the header row by searching for known Har Bituach keywords
        keywords = ['מבטח', 'חברה', 'מוצר', 'ענף', 'סטטוס', 'פרמיה', 'פוליסה']
        best_row_idx = 0
        max_matches = 0
        
        for idx, row in df_raw.head(20).iterrows():
            # Join all cells in the row into a single string to search for our keywords
            row_str = " ".join([str(x) for x in row.values if pd.notna(x)])
            matches = sum(1 for kw in keywords if kw in row_str)
            if matches > max_matches:
                max_matches = matches
                best_row_idx = idx
                
        # Set headers if found
        if max_matches >= 2:
            df = df_raw.copy()
            df.columns = df.iloc[best_row_idx]
            df = df.iloc[best_row_idx + 1:].reset_index(drop=True)
        else:
            # Fallback to defaults
            df = df_raw
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)

        print(f"📊 [HAR_BITUACH] Loaded {len(df)} rows from {filename}. Header found at row {best_row_idx}.")
        
        # 1. Standardize columns (fuzzy Hebrew match)
        col_map = {
            'מבטח': 'provider_name',
            'חברה': 'provider_name',
            'ענף משני': 'track_name_secondary',
            'ענף (משני)': 'track_name_secondary',
            'ענף ראשי': 'track_name_primary',
            'ענף': 'track_name_primary',
            'מוצר': 'track_name_primary',
            'תעודת זהות': 'owner_id',
            'סטטוס': 'status',
            'מצב': 'status',
            'סוג פרמיה': 'premium_type',
            'פרמיה': 'premium',
            'פוליסה': 'policy_number',
            'תקופת': 'expiration_date',
            'תאריך תום': 'expiration_date',
            'תאריך חידוש': 'expiration_date'
        }
        
        # Rename based on existing columns in priority
        assigned_destinations = set()
        found_cols = {}
        for k, v in col_map.items():
            if v in assigned_destinations: continue
            for c in df.columns:
                if c in found_cols: continue
                c_str = str(c).replace('\n', ' ').strip()
                if k in c_str:
                    found_cols[c] = v
                    assigned_destinations.add(v)
                    break
        
        df = df.rename(columns=found_cols)
        
        # 2. Filter for Active policies
        if 'status' in df.columns:
            # Handle duplicate status columns safely by accessing iloc fallback if dataframe
            col = df['status']
            if isinstance(col, pd.DataFrame):
                col = col.iloc[:, 0]
                
            s_col = col.astype(str)
            # Include active keywords, but exclude explicitly inactive statuses that might share substrings
            is_active = s_col.str.contains('פעיל|פעילה|תקפ|בתוקף', na=False)
            is_inactive = s_col.str.contains('לא פעיל|סולק|מבוטל|פדה|נפדה', na=False)
            
            df = df[is_active & ~is_inactive]
        
        # Helper to safely extract scalar values
        def safe_val(r, key, default):
            v = r.get(key, default)
            if isinstance(v, pd.Series):
                v = v.dropna().iloc[0] if not v.dropna().empty else default
            if pd.isna(v) or str(v).strip().lower() == 'nan':
                return default
            return v

        policy_aggregator = {}
        
        # Drop merged category rows or empty spacer rows before iterating
        df = df.dropna(thresh=4)
        
        for _, row in df.iterrows():
            # Get values safely
            provider = str(safe_val(row, 'provider_name', 'לא ידוע')).strip()
            
            # Prioritize secondary track for the visual title
            t_sec = safe_val(row, 'track_name_secondary', None)
            t_pri = safe_val(row, 'track_name_primary', 'ביטוח')
            track = str(t_sec if t_sec else t_pri).strip()
            
            # Normalize premium
            monthly_val = 0.0
            raw_v = 0.0
            p_month = safe_val(row, 'premium_monthly', None)
            p_year = safe_val(row, 'premium_yearly', None)
            p_gen = safe_val(row, 'premium', None)
            p_type = str(safe_val(row, 'premium_type', '')).strip()
            owner_id = str(safe_val(row, 'owner_id', '')).strip()
            
            if p_month is not None:
                try: 
                    raw_v = float(str(p_month).replace(',', ''))
                    monthly_val = raw_v
                    p_type = 'חודשית'
                except: pass
            elif p_year is not None:
                try: 
                    raw_v = float(str(p_year).replace(',', ''))
                    monthly_val = raw_v / 12.0
                    p_type = 'שנתית'
                except: pass
            elif p_gen is not None:
                try:
                    raw_v = float(str(p_gen).replace(',', ''))
                    if p_type == 'שנתית':
                        monthly_val = raw_v / 12.0
                    elif p_type == 'חודשית':
                        monthly_val = raw_v
                    else:
                        monthly_val = raw_v if raw_v < 10000 else raw_v / 12.0
                        p_type = 'חודשית' if raw_v < 10000 else 'שנתית'
                except: pass

            exp_date_raw = str(safe_val(row, 'expiration_date', '')).strip()
            exp_date = exp_date_raw
            if ' - ' in exp_date_raw:
                exp_date = exp_date_raw.split(' - ')[-1].strip()
            elif '-' in exp_date_raw and len(exp_date_raw) > 12:
                exp_date = exp_date_raw.split('-')[-1].strip()
            pol_num = str(safe_val(row, 'policy_number', '')).strip()
            
            # Create the data payload
            new_val = round(monthly_val, 2)
            
            p_key = pol_num if pol_num and pol_num != 'nan' else str(uuid.uuid4().hex)
            
            if p_key in policy_aggregator:
                # Merge into existing product (Sum the premiums)
                policy_aggregator[p_key]["monthly_deposit"] = round(policy_aggregator[p_key]["monthly_deposit"] + new_val, 2)
                policy_aggregator[p_key]["balance"] = round(policy_aggregator[p_key]["monthly_deposit"] * 12, 2)
                policy_aggregator[p_key]["original_premium"] = round(policy_aggregator[p_key].get("original_premium", 0) + raw_v, 2)
                
                # If current track was generic 'ביטוח' but new one has real text, enrich it
                if policy_aggregator[p_key]["track_name"] == 'ביטוח' and track != 'ביטוח':
                    policy_aggregator[p_key]["track_name"] = track
            else:
                # First time seeing this policy
                policy_aggregator[p_key] = {
                    "id": str(uuid.uuid4().hex),
                    "provider_name": provider,
                    "track_name": track,
                    "category": "insurance",
                    "owner_id": owner_id,
                    "policy_number": pol_num,
                    "balance": round(new_val * 12, 2),
                    "monthly_deposit": new_val,
                    "original_premium": round(raw_v, 2),
                    "premium_type": p_type,
                    "is_active": True,
                    "expiration_date": exp_date,
                    "source": "har_bituach_upload"
                }
            
        extracted = list(policy_aggregator.values())
            
        print(f"✅ [HAR_BITUACH] Extracted {len(extracted)} active aggregated products.")
        return extracted
    except Exception as e:
        print(f"💥 [HAR_BITUACH] Failed to parse: {e}")
        return []


def normalize_id(oid) -> str:
    """Normalize an Israeli ID number by stripping floats and leading zeros for consistent comparison."""
    if not oid: return ""
    s = str(oid).strip().split('.')[0]  # Remove .0 from Excel float strings
    return s.lstrip('0')  # Canonical form: no leading zeros

def _get_fund_unique_key(fund: dict) -> str:
    """Generate a stable unique key for deduplication."""
    category = fund.get("category", "general")
    provider = str(fund.get("provider_name", fund.get("provider", ""))).strip().lower()
    
    # Insurance: Provider + Policy Number is the best key
    if category == "insurance":
        p_num = str(fund.get("policy_number", "")).strip()
        if p_num and p_num != "nan":
            return f"ins_{provider}_{p_num}"
        # Fallback to provider + track if no policy number (manual entry)
        track = str(fund.get("track_name", "")).strip().lower()
        return f"ins_{provider}_{track}"
    
    # Pension: fund_id is the unique Israeli identifier
    f_id = str(fund.get("fund_id", "")).strip()
    if f_id and f_id != "nan":
        return f"pen_{f_id}"
    
    # Absolute fallback: full name hash
    track = str(fund.get("track_name", "")).strip().lower()
    return f"gen_{provider}_{track}"

def _merge_portfolios(existing_funds: list, new_funds: list) -> list:
    """Merges two portfolios, updating existing entries and adding new ones."""
    fund_map = { _get_fund_unique_key(f): f for f in existing_funds }
    
    for nf in new_funds:
        key = _get_fund_unique_key(nf)
        # If exists, update metadata but keep historical IDs if relevant
        if key in fund_map:
            # Preserve the original Firestore ID if it exists
            if "id" in fund_map[key] and "id" not in nf:
                nf["id"] = fund_map[key]["id"]
            fund_map[key].update(nf)
        else:
            fund_map[key] = nf
            
    return list(fund_map.values())

@router.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    uid: str = Form(...),
    document_type: str = Form(...),
    policy_id: Optional[str] = Form(None),
    user: dict = Depends(verify_token)
):
    """
    Smart Ingestion Pipeline.
    If document_type == 'specific_policy': extracts generic metadata via AI + Uploads to Cloud Storage.
    If document_type == 'har_bituach' / 'pension_report': extracts comprehensive data, updates DB, discards file.
    """
    if user.get("uid") != uid and uid != "CURRENT_UID":
         uid = user.get("uid")
         
    print(f"\n🚀 [DOCUMENTS] INCOMING REQUEST: /api/documents/upload for uid={uid}, type={document_type}, policy_id={policy_id}")
    
    from report_utils import (
        _redact_and_render_pdf,
        _extract_funds_via_ai,
        _collect_market_data_async,
        _attach_competitors_to_funds
    )

    filename_lower = (file.filename or "").lower()
    
    # === NEW MODULAR FLOW ROUTING ===
    # For now, we route matching types directly to the new classes and return early.
    # The old code is kept below as a fallback until testing is complete.
    try:
        if document_type in ("pension_report", "har_bituach", "specific_policy", "alternative_investment"):
            print(f"🔀 [DOCUMENTS] Routing {document_type} to new Flow Classes...")
            file_bytes = await file.read()
            family_profile = db_manager.get_family_profile(uid) or {}
            
            if document_type == "pension_report":
                from document_flows import PensionFlow
                flow = PensionFlow(f_profile=family_profile)
                return await flow.process(file_bytes, file.filename, uid)
                
            elif document_type in ("har_bituach", "specific_policy"):
                from document_flows import InsuranceFlow
                is_spreadsheet = filename_lower.endswith('.csv') or filename_lower.endswith('.xlsx') or filename_lower.endswith('.xls')
                flow = InsuranceFlow(filename=file.filename, is_spreadsheet=is_spreadsheet, f_profile=family_profile, target_policy_id=policy_id)
                return await flow.process(file_bytes, file.filename, uid)
                
            elif document_type == "alternative_investment":
                from document_flows import AlternativeInvestmentFlow
                flow = AlternativeInvestmentFlow(f_profile=family_profile)
                return await flow.process(file_bytes, file.filename, uid)
                
    except Exception as e:
        print(f"💥 [DOCUMENTS] Error in modular flow routing: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    # === END NEW MODULAR FLOW ROUTING ===

    # Note: PDF type is only enforced for non-har_bituach document types later in the pipeline

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Server config missing ANTHROPIC_API_KEY")

    # Fetch family profile for dynamic PII redaction & Owner Detection
    family_profile = db_manager.get_family_profile(uid)
    f_profile = family_profile.get("financial_profile", {}) if family_profile else {}
    f_pii = family_profile.get("pii_data", {}) if family_profile else {}
    
    all_target_strings = []
    
    for m_key in ["member1", "member2"]:
        m_data = f_pii.get(m_key)
        if m_data:
            name   = m_data.get("name", "")
            last   = m_data.get("lastName", "")
            id_num = m_data.get("idNumber", "")
            email  = m_data.get("email", "")
            all_target_strings.extend([name, last, id_num, email])
            if id_num and id_num.startswith("0"):
                all_target_strings.append(id_num[1:])
                
    all_target_strings = list(set([s for s in all_target_strings if s and len(s.strip()) > 2]))
    
    # Portfolio accumulation logic (same logic as existing process-reports)
    accumulated_portfolios = { "user": {"funds": []}, "spouse": {"funds": []} }
    
    id_to_member = {}
    if f_pii:
        for m_key, m_data in f_pii.items():
            if not isinstance(m_data, dict):
                continue
            id_num = normalize_id(m_data.get("idNumber"))
            if id_num:
                id_to_member[id_num] = {
                    "name": m_data.get("name", "בן משפחה"),
                    "key": "user" if m_key == "member1" else "spouse"
                }
    
    try:
        pdf_bytes = await file.read()
        
        is_spreadsheet = filename_lower.endswith('.csv') or filename_lower.endswith('.xlsx') or filename_lower.endswith('.xls')
        if is_spreadsheet:
             print(f"📊 [DOCUMENTS] Using Pandas for spreadsheet extraction...")
             raw_extracted = _extract_har_bituach_data(pdf_bytes, file.filename)
             
             # Smart Per-Row Owner & Joint Policy Recognition
             policy_groups = {}  # policy_number -> List of funds
             for fund in raw_extracted:
                 p_num = fund.get("policy_number", str(uuid.uuid4().hex))
                 if p_num not in policy_groups:
                     policy_groups[p_num] = []
                 policy_groups[p_num].append(fund)
             
             final_funds_to_distribute = []
             for p_num, group in policy_groups.items():
                 # Resolve owners for this group
                 unique_owner_names = []
                 merged_owner_keys = []
                 
                 for f in group:
                     o_id = normalize_id(f.get("owner_id"))
                     m_info = id_to_member.get(o_id)
                     if m_info:
                         if m_info["name"] not in unique_owner_names:
                             unique_owner_names.append(m_info["name"])
                         if m_info["key"] not in merged_owner_keys:
                             merged_owner_keys.append(m_info["key"])
                     else:
                        print(f"⚠️ [DOCUMENTS] No family match for ID: {o_id}")
                        # If no match, use a generic placeholder instead of forcing David
                        u_name = f"מבוטח (*{o_id[-4:]})" if o_id else "מבוטח לא ידוע"
                        if u_name not in unique_owner_names:
                             unique_owner_names.append(u_name)
                        if "user" not in merged_owner_keys:
                             merged_owner_keys.append("user")
                 
                 # Merge the group into one card
                 base_fund = group[0]
                 base_fund["owner_name"] = ", ".join(unique_owner_names)
                 
                 # Sum up premiums/balances if multiple rows (common for joint)
                 if len(group) > 1:
                     base_fund["monthly_deposit"] = sum(f.get("monthly_deposit", 0) for f in group)
                     base_fund["balance"] = sum(f.get("balance", 0) for f in group)
                 
                 # Assign to a specific key (User is priority)
                 target_key = "user" if "user" in merged_owner_keys else "spouse"
                 base_fund["_target_key"] = target_key
                 final_funds_to_distribute.append(base_fund)
             
             # Distribute to accumulation lists
             for fund in final_funds_to_distribute:
                 t_key = fund.pop("_target_key", "user")
                 accumulated_portfolios[t_key]["funds"].append(fund)
                 
             # Since it's a spreadsheet, we skip PDF-specific owner detection
             detected_owner = "member_1" # Not meaningful now as we mapped row-by-row
        else:
            # Existing PDF/AI Pipeline
            detected_owner = "member_1"
            if not filename_lower.endswith(".pdf"):
                raise HTTPException(status_code=422, detail="מסמך זה חייב להיות מסוג PDF.")
                
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Determine Owner & Authenticate if encrypted
            detected_owner = "member_1"
            if doc.is_encrypted:
                print(f"🔒 [DOCUMENTS] Document is encrypted. Trying password authentication...")
                authenticated = False
                if family_profile:
                    for m_key in ["member1", "member2"]:
                        m_pii2 = family_profile.get("pii_data", {}).get(m_key, {})
                        id_num = m_pii2.get("idNumber")
                        if id_num and doc.authenticate(id_num):
                            authenticated = True
                            detected_owner = "member_1" if m_key == "member1" else "member_2"
                            print(f"✅ [DOCUMENTS] Authenticated using {m_key}'s ID.")
                            break
                
                if not authenticated:
                    print(f"❌ [DOCUMENTS] Could not authenticate encrypted PDF.")
                    raise HTTPException(status_code=403, detail="הקובץ מוגן בסיסמה ולא הצלחנו לפתוח אותו עם תעודות הזהות שלכם.")
            else:
                # Fallback: Count matches in text for owner detection
                match_counts = {"member_1": 0, "member_2": 0}
                if family_profile:
                    for page in doc:
                        try:
                            text = page.get_text().lower()
                            for m_key in ["member1", "member2"]:
                                m_k = "member_1" if m_key == "member1" else "member_2"
                                m_pii2  = f_pii.get(m_key, {})
                                if m_pii2.get("name") and m_pii2["name"].lower().strip() in text:
                                    match_counts[m_k] += 1
                                if m_pii2.get("idNumber") and m_pii2["idNumber"].strip() in text:
                                    match_counts[m_k] += 1
                        except:
                            continue
                if match_counts["member_2"] > match_counts["member_1"]:
                    detected_owner = "member_2"

            # ALWAYS execute REDACTION + AI extraction (per user correction)
            redacted_images_b64 = _redact_and_render_pdf(doc, all_target_strings)
            extracted_funds = _extract_funds_via_ai(redacted_images_b64, api_key, f"ai_{file.filename}")
            
        owner_key = "user" if detected_owner == "member_1" else "spouse"
        
        if not is_spreadsheet:
            # Decorate PDF funds with owner name (still uses global detected_owner for PDFs)
            owner_name_mapped = f_pii.get("member1" if detected_owner == "member_1" else "member2", {}).get("name", "לא ידוע")
            for f in extracted_funds:
                f["owner_name"] = owner_name_mapped
            
            accumulated_portfolios[owner_key]["funds"] = extracted_funds
            
        print(f"✅ [DOCUMENTS] Extraction complete for {file.filename}")
        
    except HTTPException:
        raise  # Preserve original status code (e.g. 403 for wrong password, 422 for bad file)
    except Exception as e:
        print(f"💥 [DOCUMENTS] Error processing {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    # 1. Merge newly extracted funds into existing portfolios
    existing_portfolio_doc = db_manager.get_processed_portfolio(uid) or {
        "portfolios": {"user": {"funds": []}, "spouse": {"funds": []}}, 
        "action_items": []
    }
    
    for o_key in ["user", "spouse"]:
        if "funds" not in existing_portfolio_doc["portfolios"][o_key]:
             existing_portfolio_doc["portfolios"][o_key]["funds"] = []
        
        # Use Smart Merge to prevent duplicates
        merged_funds = _merge_portfolios(
            existing_portfolio_doc["portfolios"][o_key]["funds"], 
            accumulated_portfolios[o_key]["funds"]
        )
        existing_portfolio_doc["portfolios"][o_key]["funds"] = merged_funds
        
    # 2. Context Identification & Smart Filtering (Pre-AI)
    is_spreadsheet = filename_lower.endswith('.csv') or filename_lower.endswith('.xlsx') or filename_lower.endswith('.xls')
    if is_spreadsheet or document_type == "specific_policy" or document_type == "har_bituach":
        current_category = "insurance"
    else:
        current_category = "pension"

    # 3. Re-run AI analysis ONLY on the relevant subset of the merged portfolio
    # This ensures fast API calls and prevents the AI treating an insurance upload as an excuse to re-evaluate pensions.
    merged_portfolios = existing_portfolio_doc["portfolios"]
    filtered_portfolios = {"user": {"funds": []}, "spouse": {"funds": []}}
    
    for o_key in ["user", "spouse"]:
        for fund in merged_portfolios[o_key]["funds"]:
            is_fund_insurance = fund.get("category") == "insurance"
            if current_category == "pension" and not is_fund_insurance:
                filtered_portfolios[o_key]["funds"].append(fund)
            elif current_category == "insurance" and is_fund_insurance:
                filtered_portfolios[o_key]["funds"].append(fund)
                
    total_filtered_funds = sum(len(filtered_portfolios[k]["funds"]) for k in ["user", "spouse"])
    
    new_action_items = []
    if total_filtered_funds > 0:
        live_market_data = {}
        if current_category == "pension":
            live_market_data = await _collect_market_data_async(filtered_portfolios)
            _attach_competitors_to_funds(filtered_portfolios, live_market_data)
        
        # The AI Call (Gemini 2.5 Flash)
        try:
            from google import genai
            from google.genai import types
            import json
            
            gemini_api_key = os.environ.get("GEMINI_API_KEY")
            if gemini_api_key:
                client = genai.Client(api_key=gemini_api_key)
                
                # Context domain mapping for prompt enforcement
                hebrew_domain = "ביטוח" if current_category == "insurance" else "פנסיה"
                
                sys_prompt = f"You are an objective, expert family wealth advisor. Review the provided list of active policies/funds specifically for the '{current_category}' domain. Identify: 1. Items expiring within 60 days. 2. Suspected duplicate coverages. 3. Cost optimization opportunities. Return a strict JSON object containing `action_items`. Each item must have: `title` (short, in Hebrew), `description` (Detailed explanation in Hebrew), `severity` ('high', 'medium', 'low'), and `category` (this must explicitly be '{hebrew_domain}'). MUST RESPOND ENTIRELY IN HEBREW."
                
                user_prompt = f"Market Data: {json.dumps(live_market_data, ensure_ascii=False)}\nPortfolio: {json.dumps(filtered_portfolios, ensure_ascii=False)}"
                
                print(f"🤖 [DOCS-AI] Calling Gemini 2.5 Flash for {current_category} analysis ({total_filtered_funds} funds)...")
                start_ai = time.time()
                response = client.models.generate_content(
                    model=config.GEMINI_MODEL_NAME,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=sys_prompt,
                        temperature=0.7,
                        response_mime_type="application/json",
                    ),
                )
                duration = time.time() - start_ai
                print(f"✅ [DOCS-AI] Gemini responded successfully in {duration:.2f}s")
                
                try:
                    res_text = response.text.replace("```json", "").replace("```", "").strip()
                    resp_data = json.loads(res_text)
                    new_action_items = resp_data.get("action_items", [])
                except Exception as e:
                    print(f"💥 [DOCS-AI] Failed to parse Gemini JSON: {e}. Raw: {response.text[:200]}")
                    new_action_items = []
                
                # Transform to our backend schema internally
                for item in new_action_items:
                    if "description" in item:
                        item["problem_explanation"] = item["description"]
                        item["action_required"] = "פעולה נדרשת מוסברת בתיאור"
                    if "id" not in item:
                        item["id"] = f"{current_category}_{uuid.uuid4().hex[:6]}"
                    item["is_completed"] = False
                    
                print(f"✅ [DOCUMENTS] Gemini generated {len(new_action_items)} domain-specific action items.")
                if new_action_items:
                    print("--- המלצות AI שהתקבלו (וולידציה) ---")
                    import pprint
                    for item in new_action_items:
                        title = item.get('title', 'ללא כותרת')
                        sev = item.get('severity', 'ללא רמה')
                        desc = item.get('problem_explanation', item.get('description', 'ללא תיאור'))
                        print(f"[{sev.upper()}] {title}\n    > {desc}")
                    print("------------------------------------")
            else:
                print("⚠️ [DOCUMENTS] GEMINI_API_KEY missing, using legacy Anthropic advisor instead.")
                new_action_items = ai_advisor.generate_action_items(
                    family_portfolio=filtered_portfolios,
                    market_data=live_market_data,
                    financial_profile=f_profile,
                )
        except Exception as ai_e:
            print(f"💥 [DOCUMENTS] AI Generation failed, but proceeding to save funds: {ai_e}")
            new_action_items = []

    # 4. Smart Merging (Database Update)
    # Filter out any existing action items where category == current_category equivalent
    refresh_category_hebrew = 'ביטוח' if current_category == "insurance" else 'פנסיה'
    
    old_items_to_keep = [
        item for item in existing_portfolio_doc.get("action_items", [])
        if item.get("category") != refresh_category_hebrew
    ]
    
    new_items_to_keep = [
        item for item in new_action_items
        if item.get("category") == refresh_category_hebrew
    ]
    
    existing_portfolio_doc["action_items"] = old_items_to_keep + new_items_to_keep
    existing_portfolio_doc["last_updated"] = datetime.datetime.now().isoformat()
    
    db_manager.save_processed_portfolio(uid, existing_portfolio_doc)
    
    return {
        "status": "success",
        "products_found_in_file": sum(len(accumulated_portfolios[k]["funds"]) for k in ["user", "spouse"]),
        "total_products_in_portfolio": sum(len(existing_portfolio_doc["portfolios"][k].get("funds", [])) for k in ["user", "spouse"]),
        "action_items_added_or_refreshed": len(new_items_to_keep),
        "owner_matched": owner_key,
        "data": existing_portfolio_doc
    }
