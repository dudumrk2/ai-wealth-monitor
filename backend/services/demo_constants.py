import os

# ─────────────────────────────────────────────────────────────────────────────
# Feature Flag Helper
# ─────────────────────────────────────────────────────────────────────────────
def is_english_demo_enabled() -> bool:
    """Check if the English Demo mode is enabled via environment variable."""
    return os.getenv("ENABLE_ENGLISH_DEMO", "false").strip().lower() in ("true", "1", "yes")

# ─────────────────────────────────────────────────────────────────────────────
# 1. HEBREW DEMO CONSTANTS (Default / Israeli Market)
# ─────────────────────────────────────────────────────────────────────────────
DEMO_FAMILY_PROFILE_HE = {
    "pii_data": {
        "householdName": "משפחת ישראלי (דמו)",
        "member1": {
            "name": "אבי ישראלי",
            "email": "avi.israeli@example.com",
            "idNumber": "123456789"
        },
        "member2": {
            "name": "דנה ישראלי",
            "email": "dana.israeli@example.com",
            "idNumber": "987654321"
        },
        "extraAuthorizedEmails": [],
    },
    "authorizedEmails": ["avi.israeli@example.com", "dana.israeli@example.com"],
    "onboarding_completed": True
}

DEMO_PORTFOLIO_DATA_HE = {
    "summary": {
        "total_value": 1050000,
        "monthly_change": 1.2,
        "yearly_return": 8.4
    },
    "portfolios": {
        "user": {
            "name": "אבי",
            "ownerName": "אבי ישראלי",
            "funds": [
                {
                    "id": "demo-pension-1",
                    "name": "הראל פנסיה מקיפה",
                    "category": "pension",
                    "balance": 450000,
                    "monthly_deposit": 2200,
                    "management_fee_accumulation": 0.22,
                    "management_fee_deposit": 1.5,
                    "yield_1yr": 9.8,
                    "yield_3yr": 22.4,
                    "yield_5yr": 45.1,
                    "provider_name": "הראל",
                    "track_name": "מסלול כללי"
                },
                {
                    "id": "demo-study-1",
                    "name": "אלטשולר שחם השתלמות",
                    "category": "study",
                    "balance": 185000,
                    "monthly_deposit": 1500,
                    "management_fee_accumulation": 0.65,
                    "management_fee_deposit": 0,
                    "yield_1yr": 11.2,
                    "yield_3yr": 28.1,
                    "yield_5yr": 58.4,
                    "provider_name": "אלטשולר שחם",
                    "track_name": "מסלול מניות"
                },
                {
                    "id": "demo-car-ins",
                    "policy_number": "POL-8849201",
                    "name": "ביטוח רכב - טסלה מודל 3",
                    "category": "insurance",
                    "provider_name": "הפניקס",
                    "track_name": "מקיף + חובה",
                    "monthly_deposit": 450,
                    "balance": 5400,
                    "status": "פעיל",
                    "owner_name": "אבי ישראלי"
                },
                {
                    "id": "demo-health-ins",
                    "policy_number": "POL-773019",
                    "name": "ביטוח בריאות פרטי - משלים שב\"ן",
                    "category": "insurance",
                    "provider_name": "הראל",
                    "track_name": "בריאות מקיף כולל ניתוחים והשתלות",
                    "monthly_deposit": 280,
                    "balance": 3360,
                    "status": "פעיל",
                    "owner_name": "אבי ודנה ישראלי"
                }
            ]
        },
        "spouse": {
            "name": "דנה",
            "ownerName": "דנה ישראלי",
            "funds": [
                {
                    "id": "demo-provident-1",
                    "name": "מגדל קופת גמל",
                    "category": "provident",
                    "balance": 120000,
                    "monthly_deposit": 500,
                    "management_fee_accumulation": 0.45,
                    "management_fee_deposit": 0,
                    "yield_1yr": 4.2,
                    "yield_3yr": 11.5,
                    "yield_5yr": 21.8,
                    "provider_name": "מגדל",
                    "track_name": "מסלול אג\"ח"
                },
                {
                    "id": "demo-savings-1",
                    "name": "כלל פוליסת חיסכון",
                    "category": "investment_provident",
                    "balance": 210000,
                    "monthly_deposit": 2000,
                    "management_fee_accumulation": 0.8,
                    "management_fee_deposit": 0,
                    "yield_1yr": 8.1,
                    "yield_3yr": 19.5,
                    "yield_5yr": 34.2,
                    "provider_name": "כלל",
                    "track_name": "מסלול משולב"
                },
                {
                    "id": "demo-life-ins",
                    "policy_number": "POL-332901",
                    "name": "ביטוח חיים - משכנתא",
                    "category": "insurance",
                    "provider_name": "הראל",
                    "track_name": "ריסק מוות ואובדן כושר עבודה",
                    "monthly_deposit": 120,
                    "balance": 1440,
                    "status": "פעיל",
                    "owner_name": "דנה ישראלי"
                },
                {
                    "id": "demo-home-ins",
                    "policy_number": "POL-119203",
                    "name": "ביטוח מבנה ותכולה",
                    "category": "insurance",
                    "provider_name": "איילון",
                    "track_name": "דירה מקיף",
                    "monthly_deposit": 85,
                    "balance": 1020,
                    "status": "פעיל",
                    "owner_name": "אבי ודנה ישראלי"
                }
            ]
        },
        "joint": {
            "total_family_wealth": 1050000,
            "asset_allocation_percentages": {
                "stocks": 52.5,
                "bonds": 35.0,
                "cash_equivalents": 12.5
            },
            "provider_exposure": {
                "הראל": 450000,
                "אלטשולר שחם": 185000,
                "כלל": 210000,
                "מגדל": 120000,
                "הפניקס": 85000
            }
        }
    },
    "stocks": [
        {
            "id": "stock-1",
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "qty": 30,
            "avgCostPrice": 165.0,
            "lastPrice": 192.5,
            "totalValueOriginal": 5775,
            "currency": "USD",
            "dailyChangePercent": 1.4,
            "dailyPnlOriginal": 79.5,
            "totalPnlOriginal": 825.0,
            "totalReturnPercent": 16.6,
            "sector": "technology",
            "source": "csv"
        },
        {
            "id": "stock-2",
            "symbol": "NVDA",
            "name": "NVIDIA Corporation",
            "qty": 40,
            "avgCostPrice": 95.0,
            "lastPrice": 128.5,
            "totalValueOriginal": 5140,
            "currency": "USD",
            "dailyChangePercent": 3.8,
            "dailyPnlOriginal": 188.0,
            "totalPnlOriginal": 1340.0,
            "totalReturnPercent": 35.2,
            "sector": "semiconductors",
            "source": "csv"
        },
        {
            "id": "stock-3",
            "symbol": "ICL.TA",
            "name": "איי.סי.אל",
            "qty": 1000,
            "avgCostPrice": 18.5,
            "lastPrice": 16.2,
            "totalValueOriginal": 16200,
            "currency": "ILS",
            "dailyChangePercent": -0.8,
            "dailyPnlOriginal": -130.0,
            "totalPnlOriginal": -2300.0,
            "totalReturnPercent": -12.4,
            "sector": "stocks",
            "source": "csv"
        },
        {
            "id": "stock-4",
            "symbol": "CASH",
            "name": "מזומן בשקלים",
            "qty": 1,
            "avgCostPrice": 25000,
            "lastPrice": 25000,
            "totalValueOriginal": 25000,
            "currency": "ILS",
            "dailyChangePercent": 0,
            "dailyPnlOriginal": 0,
            "totalPnlOriginal": 0,
            "totalReturnPercent": 0,
            "sector": "cash",
            "source": "manual"
        }
    ],
    "action_items": [
        {
            "id": "demo-ai-1",
            "priority": "high",
            "severity": "high",
            "title": "דמי ניהול גבוהים בקרן הפנסיה",
            "problem_explanation": "דמי הניהול של אבי בהראל (0.22% מהצבירה) גבוהים מהממוצע בשוק למעסיקים בגודל דומה.",
            "action_required": "מומלץ לפנות להראל בבקשה להפחתת דמי הניהול ל-0.15% או לבחון ניוד לקרן ברירת מחדל.",
            "category": "פנסיה",
            "is_completed": False
        },
        {
            "id": "demo-ai-2",
            "priority": "medium",
            "severity": "medium",
            "title": "כפל ביטוחי אפשרי בתאונות אישיות",
            "problem_explanation": "זוהה כיסוי מקביל לתאונות אישיות גם בביטוח הבריאות וגם בפוליסת המנהלים.",
            "action_required": "מומלץ לבדוק אפשרות לביטול הכיסוי הכפול ולחסוך כ-65 ש\"ח לחודש.",
            "category": "ביטוח",
            "is_completed": False
        }
    ]
}

DEMO_CHAT_RESPONSES_HE = {
    "default": "בסביבת הדמו, הצ'אט מציע המלצות המבוססות על התיק המשפחתי, דמי הניהול, הביטוחים והתשואות של משפחת ישראלי.",
    "pension": "ניתוח הפנסיה והחיסכון של משפחת ישראלי מציג סך צבירה של כ-965,000 ש\"ח עם תשואה שנתית ממוצעת של כ-9.2%. מומלץ לבצע הפחתת דמי ניהול בקרן הפנסיה של אבי.",
    "stocks": "תיק המניות כולל אחזקות ב-Apple, NVIDIA, ICL ומזומן בשווי כולל של כ-75,000 ש\"ח עם תשואה מצטברת של +14.8%.",
    "insurance": "למשפחה 4 פוליסות פעילות (רכב, בריאות מקיף, חיים ומבנה) בעלות חודשית כוללת של 935 ש\"ח. זוהה כפל ביטוחי קל שניתן לבטל.",
    "treatment": "על פי פוליסת הבריאות המקיפה של הראל (פוליסה POL-773019), קיים כיסוי מלא לניתוחים והשתלות בחו\"ל עם תקרה של עד 5,000,000 ש\"ח בכפוף לאישור רפואי מראש."
}

DEMO_INSURANCE_CHUNKS_HE = [
    {
        "id": "demo-chunk-he-1",
        "policy_id": "demo-health-ins",
        "policy_name": "הראל ביטוח בריאות מקיף",
        "section_title": "פרק א': ניתוחים וטיפולים מיוחדים בחו\"ל",
        "content": "פרק א' - ניתוחים והשתלות בחו\"ל: הפוליסה מעניקה כיסוי מלא לטיפולים רפואיים, ניתוחים מורכבים והשתלות איברים מחוץ לישראל עד לתקרה מקסימלית של 5,000,000 ₪ למקרה ביטוח. נדרש אישור רפואי מוקדם של 10 ימי עסקים טרם הנסיעה.",
        "page_number": 4
    },
    {
        "id": "demo-chunk-he-2",
        "policy_id": "demo-health-ins",
        "policy_name": "הראל ביטוח בריאות מקיף",
        "section_title": "פרק ב': תרופות מחוץ לסל",
        "content": "פרק ב' - תרופות מיוחדות שאינן כלולות בסל הבריאות הממלכתי: כיסוי מלא עד תקרה חודשית של 1,500,000 ₪ בהשתתפות עצמית של 300 ₪ למרשם.",
        "page_number": 8
    }
]

# ─────────────────────────────────────────────────────────────────────────────
# 2. ENGLISH DEMO CONSTANTS (International Demo Mode)
# ─────────────────────────────────────────────────────────────────────────────
DEMO_FAMILY_PROFILE_EN = {
    "pii_data": {
        "householdName": "Miller Family (Demo)",
        "member1": {
            "name": "David Miller",
            "email": "david.miller@example.com",
            "idNumber": "123456789"
        },
        "member2": {
            "name": "Sarah Miller",
            "email": "sarah.miller@example.com",
            "idNumber": "987654321"
        },
        "extraAuthorizedEmails": [],
    },
    "authorizedEmails": ["david.miller@example.com", "sarah.miller@example.com"],
    "onboarding_completed": True
}

DEMO_PORTFOLIO_DATA_EN = {
    "summary": {
        "total_value": 1450000,
        "monthly_change": 2.4,
        "yearly_return": 11.8
    },
    "portfolios": {
        "user": {
            "name": "David",
            "ownerName": "David Miller",
            "funds": [
                {
                    "id": "demo-pension-1",
                    "name": "Vanguard Target Retirement 2055",
                    "category": "pension",
                    "balance": 450000,
                    "monthly_deposit": 2400,
                    "management_fee_accumulation": 0.15,
                    "management_fee_deposit": 0.0,
                    "yield_1yr": 12.8,
                    "yield_3yr": 29.4,
                    "yield_5yr": 56.2,
                    "provider_name": "Vanguard",
                    "track_name": "Target Retirement 2055 Index Fund"
                },
                {
                    "id": "demo-study-1",
                    "name": "Fidelity Growth Opportunities Fund",
                    "category": "study",
                    "balance": 185000,
                    "monthly_deposit": 1200,
                    "management_fee_accumulation": 0.42,
                    "management_fee_deposit": 0.0,
                    "yield_1yr": 19.5,
                    "yield_3yr": 43.1,
                    "yield_5yr": 89.4,
                    "provider_name": "Fidelity",
                    "track_name": "US Large-Cap Growth"
                },
                {
                    "id": "demo-car-ins",
                    "policy_number": "GE-8849201",
                    "name": "Comprehensive Auto - Tesla Model Y",
                    "category": "insurance",
                    "provider_name": "GEICO",
                    "track_name": "Collision & Comprehensive",
                    "monthly_deposit": 165,
                    "balance": 1980,
                    "status": "Active",
                    "owner_name": "David Miller"
                },
                {
                    "id": "demo-health-ins",
                    "policy_number": "AET-773019",
                    "name": "Premier Global Health & Critical Illness",
                    "category": "insurance",
                    "provider_name": "Aetna",
                    "track_name": "Global Elite International Coverage",
                    "monthly_deposit": 420,
                    "balance": 5040,
                    "status": "Active",
                    "owner_name": "David & Sarah Miller"
                }
            ]
        },
        "spouse": {
            "name": "Sarah",
            "ownerName": "Sarah Miller",
            "funds": [
                {
                    "id": "demo-provident-1",
                    "name": "BlackRock Global Allocation 401(k)",
                    "category": "provident",
                    "balance": 280000,
                    "monthly_deposit": 1600,
                    "management_fee_accumulation": 0.22,
                    "management_fee_deposit": 0.0,
                    "yield_1yr": 9.4,
                    "yield_3yr": 23.8,
                    "yield_5yr": 48.6,
                    "provider_name": "BlackRock",
                    "track_name": "Global Allocation Index"
                },
                {
                    "id": "demo-savings-1",
                    "name": "Charles Schwab S&P 500 Index Fund",
                    "category": "investment_provident",
                    "balance": 210000,
                    "monthly_deposit": 1800,
                    "management_fee_accumulation": 0.08,
                    "management_fee_deposit": 0.0,
                    "yield_1yr": 24.2,
                    "yield_3yr": 58.9,
                    "yield_5yr": 112.5,
                    "provider_name": "Charles Schwab",
                    "track_name": "S&P 500 Index (SWPPX)"
                },
                {
                    "id": "demo-life-ins",
                    "policy_number": "PRU-332901",
                    "name": "Term Life & Mortgage Protection",
                    "category": "insurance",
                    "provider_name": "Prudential",
                    "track_name": "Level Term 30-Year Coverage",
                    "monthly_deposit": 145,
                    "balance": 1740,
                    "status": "Active",
                    "owner_name": "David & Sarah Miller"
                },
                {
                    "id": "demo-home-ins",
                    "policy_number": "SF-119203",
                    "name": "Homeowners & Umbrella Policy",
                    "category": "insurance",
                    "provider_name": "State Farm",
                    "track_name": "Premier Home & Liability ($2M)",
                    "monthly_deposit": 90,
                    "balance": 1080,
                    "status": "Active",
                    "owner_name": "David Miller"
                }
            ]
        },
        "joint": {
            "total_family_wealth": 1450000,
            "asset_allocation_percentages": {
                "stocks": 64.0,
                "bonds": 26.0,
                "cash_equivalents": 10.0
            },
            "provider_exposure": {
                "Vanguard": 450000,
                "BlackRock": 280000,
                "Charles Schwab": 210000,
                "Fidelity": 185000,
                "Equities & Cash": 325000
            }
        }
    },
    "stocks": [
        {
            "id": "stock-1",
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "qty": 150,
            "avgCostPrice": 172.5,
            "lastPrice": 224.2,
            "totalValueOriginal": 33630,
            "currency": "USD",
            "dailyChangePercent": 1.6,
            "dailyPnlOriginal": 525.0,
            "totalPnlOriginal": 7755.0,
            "totalReturnPercent": 29.9,
            "sector": "technology",
            "source": "csv"
        },
        {
            "id": "stock-2",
            "symbol": "MSFT",
            "name": "Microsoft Corporation",
            "qty": 80,
            "avgCostPrice": 340.0,
            "lastPrice": 448.5,
            "totalValueOriginal": 35880,
            "currency": "USD",
            "dailyChangePercent": 0.9,
            "dailyPnlOriginal": 320.0,
            "totalPnlOriginal": 8680.0,
            "totalReturnPercent": 31.9,
            "sector": "technology",
            "source": "csv"
        },
        {
            "id": "stock-3",
            "symbol": "NVDA",
            "name": "NVIDIA Corporation",
            "qty": 350,
            "avgCostPrice": 82.0,
            "lastPrice": 128.8,
            "totalValueOriginal": 45080,
            "currency": "USD",
            "dailyChangePercent": 3.4,
            "dailyPnlOriginal": 1470.0,
            "totalPnlOriginal": 16380.0,
            "totalReturnPercent": 57.1,
            "sector": "semiconductors",
            "source": "csv"
        },
        {
            "id": "stock-4",
            "symbol": "GOOGL",
            "name": "Alphabet Inc.",
            "qty": 120,
            "avgCostPrice": 142.0,
            "lastPrice": 178.5,
            "totalValueOriginal": 21420,
            "currency": "USD",
            "dailyChangePercent": -0.4,
            "dailyPnlOriginal": -85.0,
            "totalPnlOriginal": 4380.0,
            "totalReturnPercent": 25.7,
            "sector": "technology",
            "source": "csv"
        },
        {
            "id": "stock-5",
            "symbol": "CASH",
            "name": "USD High-Yield Cash Reserve",
            "qty": 1,
            "avgCostPrice": 45000,
            "lastPrice": 45000,
            "totalValueOriginal": 45000,
            "currency": "USD",
            "dailyChangePercent": 0,
            "dailyPnlOriginal": 0,
            "totalPnlOriginal": 0,
            "totalReturnPercent": 0,
            "sector": "cash",
            "source": "manual"
        }
    ],
    "action_items": [
        {
            "id": "demo-ai-1",
            "priority": "high",
            "severity": "high",
            "title": "401(k) Provider Fee Optimization",
            "problem_explanation": "David's 401(k) administrative fee (0.22%) is higher than standard institutional index baseline (0.08%). Annual potential saving: $1,450.",
            "action_required": "Request rollover or internal fund reallocation to Vanguard / Schwab Low-Expense Institutional Series.",
            "category": "pension",
            "is_completed": False
        },
        {
            "id": "demo-ai-2",
            "priority": "medium",
            "severity": "medium",
            "title": "Health & Critical Care Duplicate Coverage",
            "problem_explanation": "Aetna Global Health policy #AET-773019 includes specialized abroad care overlapping with supplemental travel rider.",
            "action_required": "Review rider terms to eliminate redundant premium and save $380 annually.",
            "category": "insurance",
            "is_completed": False
        }
    ]
}

DEMO_CHAT_RESPONSES_EN = {
    "default": "Welcome! I am your AI Wealth Copilot. I have analyzed your $1.45M family portfolio across Vanguard, BlackRock, Schwab, active equities, and indexed insurance policies.",
    "pension": "Your family's retirement & long-term portfolio is valued at $1,125,000 across Vanguard 2055, BlackRock 401(k), Schwab S&P 500, and Fidelity Growth, generating an average 12.4% annualized return.",
    "stocks": "Your stock portfolio holds $181,010 across high-growth technology leaders (NVDA, AAPL, MSFT, GOOGL) and cash reserves with a total return of +36.2% ($37,195 unrealized profit).",
    "insurance": "Your family is protected under 4 active policies (Aetna Global Health, GEICO Auto, Prudential Life, State Farm Home) with total monthly premiums of $820.",
    "treatment": "According to Section 4 of your indexed **Aetna Premier Global Health Policy (#AET-773019)**:\n\n- **Coverage Limit:** Up to **$2,000,000 USD** lifetime maximum for approved experimental and advanced specialized therapies overseas.\n- **Co-insurance:** Policyholder pays **10%** of approved medical costs.\n- **Pre-Authorization Requirement:** Written medical pre-authorization from Aetna Global Medical Board is required at least **14 business days** prior to admission.\n- **Network:** Full direct billing at accredited centers in the US, EU, Switzerland, and Israel.",
    "aetna": "According to Section 4 of your indexed **Aetna Premier Global Health Policy (#AET-773019)**:\n\n- **Coverage Limit:** Up to **$2,000,000 USD** lifetime maximum for approved experimental and advanced specialized therapies overseas.\n- **Co-insurance:** Policyholder pays **10%** of approved medical costs.\n- **Pre-Authorization Requirement:** Written medical pre-authorization from Aetna Global Medical Board is required at least **14 business days** prior to admission.\n- **Network:** Full direct billing at accredited centers in the US, EU, Switzerland, and Israel."
}

DEMO_INSURANCE_CHUNKS_EN = [
    {
        "id": "demo-chunk-en-1",
        "policy_id": "demo-health-ins",
        "policy_name": "Aetna Premier Global Health & Critical Illness",
        "section_title": "Section 4: Experimental Treatments & Specialized Care Abroad",
        "content": "Section 4 - Experimental Treatments, Clinical Trials and Specialized Overseas Care: This policy provides comprehensive coverage for innovative and experimental therapies, clinical trials (Phase II-IV), and advanced oncological/neurological specialized treatments administered at recognized international centers of excellence outside the policyholder's primary country of residence. The maximum lifetime benefit under this section is $2,000,000 USD per insured individual. Co-insurance: 10% co-pay applies to all approved hospital and specialist fees. Pre-authorization: Written approval from Aetna Global Medical Review Board is mandatory at least 14 business days prior to scheduled hospital admission or treatment commencement.",
        "page_number": 12
    },
    {
        "id": "demo-chunk-en-2",
        "policy_id": "demo-health-ins",
        "policy_name": "Aetna Premier Global Health & Critical Illness",
        "section_title": "Section 1: Inpatient Hospitalization & Surgical Benefits",
        "content": "Section 1 - Inpatient Hospitalization & Direct Billing: 100% covered for private hospital room, operating theatre fees, intensive care unit, physician and surgeon fees across Aetna International Worldwide Direct-Billing Provider Network. Lifetime maximum per policy: $5,000,000 USD.",
        "page_number": 3
    }
]

# ─────────────────────────────────────────────────────────────────────────────
# 3. RESOLVER FUNCTIONS (Multi-Language & Feature Flag Aware)
# ─────────────────────────────────────────────────────────────────────────────
def get_demo_family_profile(lang: str | None = None) -> dict:
    is_en = (lang == "en") or (lang is None and is_english_demo_enabled())
    return DEMO_FAMILY_PROFILE_EN if is_en else DEMO_FAMILY_PROFILE_HE

def get_demo_portfolio_data(lang: str | None = None) -> dict:
    is_en = (lang == "en") or (lang is None and is_english_demo_enabled())
    return DEMO_PORTFOLIO_DATA_EN if is_en else DEMO_PORTFOLIO_DATA_HE

def get_demo_chat_responses(lang: str | None = None) -> dict:
    is_en = (lang == "en") or (lang is None and is_english_demo_enabled())
    return DEMO_CHAT_RESPONSES_EN if is_en else DEMO_CHAT_RESPONSES_HE

def get_demo_insurance_chunks(lang: str | None = None) -> list:
    is_en = (lang == "en") or (lang is None and is_english_demo_enabled())
    return DEMO_INSURANCE_CHUNKS_EN if is_en else DEMO_INSURANCE_CHUNKS_HE

# Backward-compatible dynamic aliases (defaults to English if flag set, else Hebrew)
DEMO_ALT_INVESTMENT = {
    "id": "demo-alt-1",
    "name": "Eagle Real Estate Income Fund",
    "developer": "Eagle Invest",
    "originalAmount": 85000,
    "currency": "USD",
    "startDate": "2023-01-15",
    "durationMonths": 36,
    "expectedReturn": 8.5,
    "status": "Active"
}
DEMO_FAMILY_PROFILE = get_demo_family_profile()
DEMO_PORTFOLIO_DATA = get_demo_portfolio_data()
DEMO_CHAT_RESPONSES = get_demo_chat_responses()
DEMO_INSURANCE_CHUNKS = get_demo_insurance_chunks()
