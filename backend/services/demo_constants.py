# Mock data constants for the Demo User flow

DEMO_FAMILY_PROFILE = {
    "pii_data": {
        "householdName": "משפחת ישראלי (דמו)",
        "member1": {
            "name": "אבי ישראלי",
            "email": "demo-avi@example.com",
            "idNumber": "123456789"
        },
        "member2": {
            "name": "דנה ישראלי",
            "email": "demo-dana@example.com",
            "idNumber": "987654321"
        },
        "extraAuthorizedEmails": [],
    },
    "authorizedEmails": ["demo-avi@example.com", "demo-dana@example.com"],
    "onboarding_completed": True
}

DEMO_PORTFOLIO_DATA = {
    "summary": {
        "total_value": 1450000,
        "monthly_change": 1.8,
        "yearly_return": 9.2
    },
    "portfolios": {
        "user": {
            "name": "אבי",
            "funds": [
                {
                    "id": "demo-pension-1",
                    "name": "הראל פנסיה מקיפה",
                    "category": "pension",
                    "balance": 450000,
                    "monthly_deposit": 2800,
                    "management_fee_accumulation": 0.22,
                    "management_fee_deposit": 1.45,
                    "yield_1yr": 7.8,
                    "yield_3yr": 22.4,
                    "yield_5yr": 41.2,
                    "provider_name": "הראל",
                    "track_name": "מסלול לבני 50 ומטה"
                },
                {
                    "id": "demo-study-1",
                    "name": "אלטשולר שחם השתלמות",
                    "category": "study",
                    "balance": 185000,
                    "monthly_deposit": 1500,
                    "management_fee_accumulation": 0.65,
                    "management_fee_deposit": 0,
                    "yield_1yr": 14.5,
                    "yield_3yr": 32.1,
                    "yield_5yr": 58.4,
                    "provider_name": "אלטשולר שחם",
                    "track_name": "מניות"
                },
                {
                    "id": "demo-car-ins",
                    "name": "ביטוח רכב - טסלה מודל 3",
                    "category": "insurance",
                    "provider_name": "הפניקס",
                    "track_name": "מקיף + חובה",
                    "monthly_deposit": 450,
                    "status": "פעיל"
                },
                {
                    "id": "demo-health-ins",
                    "name": "ביטוח בריאות פרטי - משלים שב\"ן",
                    "category": "insurance",
                    "provider_name": "הראל",
                    "track_name": "בריאות מקיף",
                    "monthly_deposit": 280,
                    "status": "פעיל"
                }
            ]
        },
        "spouse": {
            "name": "דנה",
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
                    "track_name": "אג\"ח"
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
                    "track_name": "משולב"
                },
                {
                    "id": "demo-savings-2",
                    "name": "הפניקס מסלול S&P 500",
                    "category": "investment_provident",
                    "balance": 85000,
                    "monthly_deposit": 1000,
                    "management_fee_accumulation": 0.75,
                    "management_fee_deposit": 0,
                    "yield_1yr": 18.2,
                    "yield_3yr": 44.1,
                    "yield_5yr": 82.5,
                    "provider_name": "הפניקס",
                    "track_name": "S&P 500"
                },
                {
                    "id": "demo-life-ins",
                    "name": "ביטוח חיים - משכנתא",
                    "category": "insurance",
                    "provider_name": "הראל",
                    "track_name": "ריסק",
                    "monthly_deposit": 120,
                    "status": "פעיל"
                },
                {
                    "id": "demo-home-ins",
                    "name": "ביטוח מבנה ותכולה",
                    "category": "insurance",
                    "provider_name": "איילון",
                    "track_name": "דירה",
                    "monthly_deposit": 85,
                    "status": "פעיל"
                }
            ]
        },
        "joint": {
            "total_family_wealth": 1050000, 
            "asset_allocation_percentages": {
                "pension": 42.8,
                "study": 17.6,
                "provident": 11.4,
                "investment_provident": 28.1
            },
            "provider_exposure": {
                "הראל": 450000,
                "אלטשולר שחם": 185000,
                "מגדל": 120000,
                "כלל": 210000,
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
            "sector": "stocks",
            "source": "csv"
        },
        {
            "id": "stock-2",
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
            "id": "stock-3",
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
            "problem_explanation": "דמי הניהול של אבי (0.22% מהצבירה) גבוהים מהממוצע בשוק לבעלי שכר דומה. ניתן לחסוך כ-1,200 ש\"ח בשנה.",
            "action_required": "מומלץ לפנות להראל או לבצע השוואה מול קרנות נבחרות.",
            "category": "פנסיה",
            "is_completed": False
        },
        {
            "id": "demo-ai-2",
            "priority": "medium",
            "severity": "medium",
            "title": "חשיפה נמוכה למניות",
            "problem_explanation": "בהתחשב בגילכם, תיק ההשקעות של דנה מוטה מדי לאג\"ח, מה שעלול לפגוע בתשואה לטווח ארוך.",
            "action_required": "שקלו להגדיל את החשיפה למניות בקופת הגמל.",
            "category": "כללי",
            "is_completed": False
        }
    ]
}

DEMO_ALT_INVESTMENT = {
    "id": "demo-alt-1",
    "name": "נדל\"ן מניב בגרמניה",
    "developer": "Eagle Invest",
    "originalAmount": 350000,
    "currency": "ILS",
    "startDate": "2022-06-01",
    "durationMonths": 48,
    "expectedReturn": 7.5,
    "status": "Active"
}

DEMO_CHAT_RESPONSES = {
    "default": "בסביבת הדמו, הצ'אט מוגבל לתשובות מוכנות מראש. המערכת מזהה את התיק שלך ומציעה המלצות המבוססות על דמי ניהול, ביטוחים וביצועי פוליסות החיסכון שלך.",
    "pension": "ניתוח הפנסיה והחיסכון מראה שיש לכם פוליסת S&P 500 עם ביצועים מצוינים (18.2% בשנה האחרונה). כדאי לשקול איחוד של קופת הגמל הקטנה של דנה.",
    "stocks": "תיק המניות שלכם כולל חשיפה ל-Apple וגם ל-ICL. השווי הכולל הוא כ-110,000 ש\"ח (כולל מזומן).",
    "insurance": "יש לכם 4 פוליסות ביטוח פעילות: רכב (טסלה), בריאות פרטית, חיים ומבנה. העלות החודשית הכוללת היא 935 ש\"ח."
}
