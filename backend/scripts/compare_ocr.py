import os
import sys
import time
import json
import base64
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Reconfigure stdout/stderr to UTF-8 for Windows terminals
if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr:
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add backend directory to sys.path so we can import project modules
BACKEND_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

import config
import report_utils

# Pricing per million tokens (approx. August 2026 rates)
PRICING = {
    "claude-3-7-sonnet": {
        "input_per_m": 3.00,
        "output_per_m": 15.00,
    },
    "gemini-3.7-flash": {
        "input_per_m": 0.15,
        "output_per_m": 0.60,
    }
}

def parse_args():
    parser = argparse.ArgumentParser(description="A/B Benchmark: Claude 3.7 Sonnet vs Gemini 3.7 Flash OCR Extraction")
    parser.add_argument("pdf_path", nargs="?", default="", help="Path to input PDF report")
    parser.add_argument("--names", default="", help="Comma-separated PII names to redact (e.g. 'ישראל,ישראלי')")
    parser.add_argument("--ids", default="", help="Comma-separated PII ID numbers to redact")
    parser.add_argument("--emails", default="", help="Comma-separated PII emails to redact")
    return parser.parse_args()

def run_claude_ocr(redacted_images_b64: list[str], api_key: str) -> dict:
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    
    content_blocks = []
    for b64 in redacted_images_b64[:10]:
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })
    content_blocks.append({"type": "text", "text": "חלץ את כל המוצרים הפיננסיים מהדפים האלה. החזר JSON תקני בלבד."})
    
    claude_model = getattr(config, "CLAUDE_MODEL_NAME", "claude-sonnet-4-6")
    start_time = time.time()
    response = client.messages.create(
        model=claude_model,
        max_tokens=4096,
        system=report_utils.EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content_blocks}],
    )
    duration = time.time() - start_time
    
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    
    cost = (input_tokens / 1_000_000 * PRICING["claude-3-7-sonnet"]["input_per_m"]) + \
           (output_tokens / 1_000_000 * PRICING["claude-3-7-sonnet"]["output_per_m"])
           
    raw_text = response.content[0].text.strip()
    # Strip markdown fences if present
    clean_text = raw_text.replace("```json", "").replace("```", "").strip()
    
    try:
        data = json.loads(clean_text)
    except Exception as e:
        data = {"error": f"JSON parse error: {e}", "raw": raw_text[:500]}
        
    return {
        "model": "Claude 3.7 Sonnet",
        "duration_sec": round(duration, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": round(cost, 5),
        "data": data,
        "raw_text": raw_text
    }

def run_gemini_ocr(redacted_images_b64: list[str], api_key: str, max_retries: int = 3) -> dict:
    import httpx
    from google import genai
    from google.genai import types
    
    # Configure custom httpx client with explicit 180s connect/read/write timeouts
    custom_timeout = httpx.Timeout(180.0, connect=60.0, read=180.0, write=180.0)
    custom_client = httpx.Client(timeout=custom_timeout)
    
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(httpxClient=custom_client)
    )
    
    contents = []
    for b64 in redacted_images_b64[:10]:
        img_bytes = base64.b64decode(b64)
        contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        
    contents.append("חלץ את כל המוצרים הפיננסיים מהדפים האלה. החזר JSON תקני בלבד.")
    
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"🤖 Calling Gemini 3.7 Flash with identical PNG images (Attempt {attempt}/{max_retries})...")
            start_time = time.time()
            response = client.models.generate_content(
                model="gemini-3.7-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=report_utils.EXTRACTION_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
            duration = time.time() - start_time
            
            usage = getattr(response, "usage_metadata", None)
            input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
            output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
            
            cost = (input_tokens / 1_000_000 * PRICING["gemini-3.7-flash"]["input_per_m"]) + \
                   (output_tokens / 1_000_000 * PRICING["gemini-3.7-flash"]["output_per_m"])
                   
            raw_text = response.text.strip() if response.text else ""
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(clean_text)
            except Exception as e:
                data = {"error": f"JSON parse error: {e}", "raw": raw_text[:500]}
                
            return {
                "model": "Gemini 3.7 Flash",
                "duration_sec": round(duration, 2),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": round(cost, 5),
                "data": data,
                "raw_text": raw_text
            }
        except Exception as e:
            last_err = e
            print(f"⚠️ Gemini attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
                
    raise RuntimeError(f"Gemini failed after {max_retries} attempts: {last_err}")

def print_comparison_summary(claude_res: dict, gemini_res: dict):
    print("\n" + "="*80)
    print(" 🏆 A/B OCR BENCHMARK RESULTS")
    print("="*80)
    
    c_data = claude_res.get("data", {})
    g_data = gemini_res.get("data", {})
    c_prods = c_data.get("products", []) if isinstance(c_data, dict) else []
    g_prods = g_data.get("products", []) if isinstance(g_data, dict) else []
    
    print(f"{'Metric':<30} | {'Claude 3.7 Sonnet':<22} | {'Gemini 3.7 Flash':<22}")
    print("-" * 80)
    print(f"{'Duration (seconds)':<30} | {claude_res['duration_sec']:<22} | {gemini_res['duration_sec']:<22}")
    print(f"{'Input Tokens':<30} | {claude_res['input_tokens']:<22} | {gemini_res['input_tokens']:<22}")
    print(f"{'Output Tokens':<30} | {claude_res['output_tokens']:<22} | {gemini_res['output_tokens']:<22}")
    print(f"{'Estimated Cost ($)':<30} | ${claude_res['estimated_cost_usd']:<21} | ${gemini_res['estimated_cost_usd']:<21}")
    print(f"{'Products Extracted':<30} | {len(c_prods):<22} | {len(g_prods):<22}")
    print("-" * 80)
    
    print("\n📦 PRODUCTS COMPARISON:")
    max_len = max(len(c_prods), len(g_prods))
    for i in range(max_len):
        print(f"\n--- Product #{i+1} ---")
        c_p = c_prods[i] if i < len(c_prods) else {}
        g_p = g_prods[i] if i < len(g_prods) else {}
        
        fields = [
            ("Provider", "provider_name"),
            ("Type", "product_type"),
            ("Track Name", "track_name"),
            ("Policy #", "policy_number"),
            ("Balance (₪)", "balance"),
            ("Monthly Deposit (₪)", "monthly_deposit"),
            ("Fee Accum (%)", "management_fee_accumulation"),
            ("Fee Deposit (%)", "management_fee_deposit"),
            ("Yield 1Y (%)", "yield_1yr"),
            ("Yield 3Y Cum (%)", "yield_3yr_cumulative"),
            ("Yield 5Y Cum (%)", "yield_5yr_cumulative"),
        ]
        
        for label, key in fields:
            c_val = c_p.get(key, "N/A")
            g_val = g_p.get(key, "N/A")
            match_flag = "✅" if str(c_val) == str(g_val) else "⚠️ DIFF"
            print(f"  {label:<22} | Claude: {str(c_val):<20} | Gemini: {str(g_val):<20} | {match_flag}")
            
    print("\n" + "="*80)

def main():
    # Load environment files (first benchmark_config.env if exists, then .env)
    benchmark_env_path = BACKEND_DIR / "benchmark_config.env"
    if benchmark_env_path.exists():
        load_dotenv(benchmark_env_path, override=True)
    load_dotenv(BACKEND_DIR / ".env")

    args = parse_args()
    
    # Resolve PDF path from CLI or ENV
    raw_pdf_path = args.pdf_path or os.environ.get("PDF_FILE_PATH", "")
    if not raw_pdf_path:
        print("❌ Error: No PDF path provided via CLI or PDF_FILE_PATH in benchmark_config.env.")
        print("Usage: python backend/scripts/compare_ocr.py <path_to_pdf> [--names 'name1,name2'] [--ids 'id1,id2']")
        sys.exit(1)
        
    pdf_path = Path(raw_pdf_path)
    if not pdf_path.is_absolute():
        if (WORKSPACE_DIR / pdf_path).exists():
            pdf_path = (WORKSPACE_DIR / pdf_path).resolve()
        elif (BACKEND_DIR / pdf_path).exists():
            pdf_path = (BACKEND_DIR / pdf_path).resolve()
        else:
            pdf_path = (BACKEND_DIR / pdf_path).resolve()
        
    if not pdf_path.exists():
        print(f"❌ Error: File not found at '{pdf_path}'")
        sys.exit(1)
        
    claude_key = os.environ.get("ANTHROPIC_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    if not claude_key or not gemini_key:
        print("⚠️ Warning: Missing API keys in environment.")
        if not claude_key: print("  - ANTHROPIC_API_KEY is missing")
        if not gemini_key: print("  - GEMINI_API_KEY is missing")
        sys.exit(1)
        
    # Build PII target list from CLI args or ENV
    names_str = args.names or os.environ.get("PII_NAMES", "")
    ids_str = args.ids or os.environ.get("PII_IDS", "")
    emails_str = args.emails or os.environ.get("PII_EMAILS", "")
    
    pii_targets = []
    id_list = []
    if names_str:
        pii_targets.extend([n.strip() for n in names_str.split(",") if len(n.strip()) > 1])
    if ids_str:
        for i_str in ids_str.split(","):
            clean_id = i_str.strip()
            if len(clean_id) > 1:
                id_list.append(clean_id)
                pii_targets.append(clean_id)
                if clean_id.startswith("0"):
                    pii_targets.append(clean_id[1:])
    if emails_str:
        pii_targets.extend([e.strip() for e in emails_str.split(",") if len(e.strip()) > 1])
        
    print(f"\n📄 Loading PDF: {pdf_path.name}")
    import fitz
    doc = fitz.open(pdf_path)
    
    if doc.is_encrypted:
        print("🔒 PDF is password-protected. Attempting to unlock with ID numbers...")
        authenticated = False
        for raw_id in id_list:
            candidates = [raw_id]
            if raw_id.startswith("0"):
                candidates.append(raw_id[1:])
            for cand in candidates:
                if doc.authenticate(cand):
                    authenticated = True
                    print(f"✅ Successfully unlocked PDF with ID password ({len(cand)} digits).")
                    break
            if authenticated:
                break
        if not authenticated:
            print("❌ Error: Could not unlock encrypted PDF with the provided ID numbers.")
            sys.exit(1)
            
    total_pages = len(doc)
    print(f"📑 Total pages: {total_pages}")
    
    # Render images for Claude
    print(f"🔒 Redacting PII ({len(pii_targets)} target strings) and rendering to PNG images for Claude...")
    # Reopen a fresh copy of the decrypted doc for redaction
    doc_bytes = doc.tobytes()
    
    # Redact native PDF bytes for Gemini
    redacted_pdf_doc = fitz.open(stream=doc_bytes, filetype="pdf")
    for page in redacted_pdf_doc:
        for target in pii_targets:
            if not target or len(target.strip()) < 2:
                continue
            for rect in page.search_for(target):
                page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()
    redacted_pdf_bytes = redacted_pdf_doc.tobytes(garbage=4, deflate=True)
    redacted_pdf_doc.close()
    
    # Redact and render images for Claude
    render_doc = fitz.open(stream=doc_bytes, filetype="pdf")
    redacted_images_b64 = report_utils._redact_and_render_pdf(render_doc, pii_targets)
    print(f"✅ Prepared {len(redacted_images_b64)} redacted pages / {len(redacted_pdf_bytes):,} bytes PDF.")
    
    # Check cache for Claude to avoid unnecessary re-billing
    claude_cache_file = BACKEND_DIR / "scripts" / f".cache_claude_{pdf_path.stem}.json"
    if claude_cache_file.exists():
        print("\n🚀 [1/2] Loading cached extraction from Claude...")
        with open(claude_cache_file, "r", encoding="utf-8") as f:
            claude_res = json.load(f)
        print(f"✅ Loaded Claude cache ({claude_res['duration_sec']}s, Est. Cost: ${claude_res['estimated_cost_usd']})")
    else:
        print("\n🚀 [1/2] Running extraction with Claude...")
        claude_res = run_claude_ocr(redacted_images_b64, claude_key)
        print(f"✅ Claude completed in {claude_res['duration_sec']}s (Est. Cost: ${claude_res['estimated_cost_usd']})")
        with open(claude_cache_file, "w", encoding="utf-8") as f:
            json.dump(claude_res, f, ensure_ascii=False, indent=2)
    
    print("\n🚀 [2/2] Running extraction with Gemini 3.7 Flash (Identical PNG images)...")
    gemini_res = run_gemini_ocr(redacted_images_b64, gemini_key)
    print(f"✅ Gemini completed in {gemini_res['duration_sec']}s (Est. Cost: ${gemini_res['estimated_cost_usd']})")
    
    print_comparison_summary(claude_res, gemini_res)
    
    # Save detailed JSON output
    out_file = BACKEND_DIR / "scripts" / f"ocr_benchmark_{pdf_path.stem}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"claude": claude_res, "gemini": gemini_res}, f, ensure_ascii=False, indent=2)
    print(f"💾 Full results saved to: {out_file}\n")

if __name__ == "__main__":
    main()
