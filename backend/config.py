# AI Model Definitions
CLAUDE_MODEL_NAME = "claude-sonnet-4-6"
GEMINI_MODEL_NAME = "gemini-2.5-flash"
GEMINI_PRO_MODEL_NAME = "gemini-2.5-pro"

# Document Parsing Settings
PDF_SKIP_PAGES = 1

# Hebrew product_type -> Frontend category slug
PRODUCT_TYPE_TO_CATEGORY: dict[str, str] = {
    "פנסיה":            "pension",
    "ביטוח מנהלים":    "managers",
    "קרן השתלמות":     "study",
    "קופת גמל":         "provident",
    "גמל להשקעה":      "investment_provident",
    "תיק מניות":        "stocks",
}

# Demo Settings
import os
DEMO_UID = "demo-user-12345"
DEMO_TOKEN = os.environ.get("DEMO_TOKEN", "demo-token-12345")
