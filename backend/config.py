# AI Model Definitions
CLAUDE_MODEL_NAME = "claude-sonnet-4-6"
GEMINI_MODEL_NAME = "gemini-2.5-flash"

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
