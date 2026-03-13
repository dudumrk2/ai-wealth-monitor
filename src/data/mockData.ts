export const MOCK_DATA = {
  "last_updated": "2026-03-13T10:00:00Z",
  "portfolios": {
    "user": {
      "pension_funds": [
        {
          "id": "pen_u1",
          "provider_name": "הראל",
          "track_name": "פנסיה מקיפה - מסלול מניות",
          "status": "active",
          "balance": 450200,
          "monthly_deposit": 4500,
          "management_fee_deposit": 1.5,
          "management_fee_accumulation": 0.15,
          "yield_1yr": 12.4,
          "yield_3yr": 25.1,
          "yield_5yr": 42.3,
          "top_competitors": [
            {
              "provider_name": "אלטשולר שחם",
              "track_name": "מקיפה מנייתי",
              "yield_1yr": 14.2,
              "yield_3yr": 22.1,
              "yield_5yr": 40.5,
              "management_fee_accumulation_avg": 0.18,
              "fund_size_billions": 32.5,
              "product_link": "https://www.altshuler-shaham.co.il/pension"
            }
          ]
        }
      ],
      "study_funds": [
        {
          "id": "stu_u1",
          "provider_name": "ילין לפידות",
          "track_name": "השתלמות מסלול כללי",
          "status": "active",
          "balance": 125000,
          "monthly_deposit": 1500,
          "management_fee_deposit": 0.0,
          "management_fee_accumulation": 0.6,
          "yield_1yr": 8.5,
          "yield_3yr": 15.2,
          "yield_5yr": 30.1,
          "top_competitors": []
        }
      ],
      "alternative_investments": [
        {
          "id": "alt_u1",
          "name": "קרן כספית שקלית",
          "description": "השקעה נזילה בקרן כספית המהווה תחליף לפיקדון בנקאי",
          "balance": 85000,
          "expected_yearly_yield": 4.2,
          "maturity_date": "N/A - נזיל יומי"
        }
      ]
    },
    "spouse": {
      "pension_funds": [
        {
          "id": "pen_s1",
          "provider_name": "מנורה מבטחים",
          "track_name": "פנסיה מקיפה - תלוי גיל",
          "status": "active",
          "balance": 380000,
          "monthly_deposit": 3800,
          "management_fee_deposit": 2.0,
          "management_fee_accumulation": 0.2,
          "yield_1yr": 9.2,
          "yield_3yr": 18.5,
          "yield_5yr": 35.0,
          "top_competitors": []
        }
      ],
      "study_funds": [],
      "alternative_investments": []
    },
    "joint": {
      "total_family_wealth": 1040200,
      "asset_allocation_percentages": {
        "stocks": 55,
        "bonds": 30,
        "cash_equivalents": 15
      },
      "provider_exposure": {
        "הראל": 43,
        "מנורה מבטחים": 36,
        "ילין לפידות": 12,
        "אחר": 9
      }
    }
  },
  "action_items": [
    {
      "id": "task_1",
      "type": "insurance_optimization",
      "title": "עדכון סטטוס ביטוחי - פנסיית שאירים",
      "description": "הבן הבכור כיום בן 18. בעוד פחות מ-3 שנים הוא יגיע לגיל 21 וייצא מתחולת פנסיית השאירים לפי התקנון. מומלץ להגדיר תזכורת לעדכון המסלול הביטוחי בקרן הפנסיה במועד זה, כדי להקטין את עלויות הביטוח ולהפנות יותר כספים לחיסכון.",
      "is_completed": false,
      "severity": "medium"
    },
    {
      "id": "task_2",
      "type": "fee_negotiation",
      "title": "הוזלת דמי ניהול בקרן הפנסיה של אשתך",
      "description": "דמי הניהול מצבירה ב'מנורה מבטחים' (0.2%) גבוהים ביחס לצבירה וביחס לדמי הניהול שלך ב'הראל' (0.15%). יש ליצור קשר עם הסוכן ולבקש השוואת תנאים.",
      "is_completed": false,
      "severity": "high"
    },
    {
      "id": "task_3",
      "type": "investment_strategy",
      "title": "בחינת כפילות מדדים",
      "description": "זוהתה חפיפה גבוהה בין מסלול המניות בפנסיה לבין החזקות בתיק ההשקעות העצמאי. מומלץ לבחון את פיזור הסיכונים הכולל.",
      "is_completed": true,
      "severity": "low"
    }
  ]
};
