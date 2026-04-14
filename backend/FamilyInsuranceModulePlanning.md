<div dir="rtl">

# מסמך אפיון ארכיטקטוני: תזרימי נתונים ושילוב בינה מלאכותית (AI & Data Pipeline)

מסמך זה מפרט את ארכיטקטורת תזרימי המידע (Data Flows), את אופן הקצאת המשאבים והמשימות בין מודלי השפה (Claude ו-Gemini), את מנגנוני העשרת הנתונים, וכן מציג את ההנחיות המערכתיות (Prompts) המוגדרות עבור כל אחד ממודולי המערכת.

## 1. מודול פנסיה: עיבוד דוחות מובנים וניתוח תיקי חיסכון ארוכי טווח

### זרימת הנתונים העיקרית (Data Flow):

1. הסתרת מידע מזהה (PII Redaction): עם קליטת מסמך ה-PDF בשרת, מופעל אלגוריתם מבוסס Python (כדוגמת PyMuPDF) המיועד לאיתור ולמיסוך פרטים מזהים (כגון מספרי תעודת זהות, כתובות ומספרי טלפון), וזאת בטרם העברת הנתונים לסביבת הענן, לשם הבטחת סודיות המידע.

2. המרת תצורה: מסמך ה-PDF, לאחר השלמת הליך המיסוך, מומר באופן אוטומטי לרצף קבצי תמונה.

3. שלב א' - פענוח וחילוץ נתונים (Extraction): קבצי התמונה מוזנים למודל Claude 3.5 Sonnet לשם חילוץ טכני של רשימת קופות הגמל והמסלולים בצורת מתאר JSON "יבש" (ללא תובנות או אנליזה בשלב זה). מיד עם סיום הליך זה, קובץ המקור מושמד לצמיתות משרתי המערכת.

הפרומפט המנחה המוגדר לשלב זה (שלב החילוץ):

<div dir="ltr">

```
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
   - חלץ אך ורק *הפקדה חודשית ממוצעת או אחרונה* (למשל 1,500 ₪). 
   - סכנה: דוחות רבים מציגים "סך הפקדות בשנת הדיווח" או "הפקדות שוטפות" שהם בסכומים גבוהים מאוד. לעולם אל תחלץ סכומים שנתיים מצטברים אלו לתוך monthly_deposit! אם לא כתוב במפורש מה ההפקדה החודשית, השאר את field זה כ-0.
2. תשואות (Yields):
   - קיימים שני מונחים: "תשואה מצטברת" (Cumulative) ו"תשואה שנתית ממוצעת" (Annualized).
   - הקפד לשים כל נתון בשדה המתאים (cumulative מול annualized).
   - חלץ בדיוק את המספר שמופיע בדוח בעמודה המתאימה ל-3 ול-5 שנים. אין להמציא ערכים.
3. מדד שארפ: חלץ את הערך המופיע בדוח. אם לא מופיע, החזר 0.

CRITICAL FORMATTING:
- החזר JSON תקני בלבד ללא בלוקים של markdown (ללא ```json) וללא כל טקסט חופשי.
- אל תכניס פסיקים או פסיק עליון במספרים (החזר 1234.56 במקום 1,234.56).
- אם שדה כלשהו לא מופיע בדוח, יש להחזיר 0 עבור מספרים ו-"" עבור מחרוזות. אל תשמיט שדות ממבנה ה-JSON הנדרש.

```

</div>

מנגנון העשרת נתונים (Data Enrichment): סנכרון נתוני שוק בזמן אמת

עם סיום שלב חילוץ הנתונים מהדו"ח (שלב 3), מופעל תהליך עיבוד נתונים רב-שלבי, שתכליתו שיוך נתוני הקרנות המתחרות המובילות בשוק לכל קופה וקופה. מנגנון זה נסמך על תבנית Stale-While-Revalidate:

### א. תהליך השוואה מול מקורות מידע חיצוניים (MyFunds ו-CKAN):

1. סיווג אונטולוגי (Specialization): התאמת שם המסלול שחולץ למינוח התקני המשמש את מערכות הסימולציה הממשלתיות.

2. שאילתה למערכת MyFunds: ייזום פנייה לממשק התכנות (API) לאחזור שלוש הקרנות (Top 3) המובילות בקטגוריה הרלוונטית, אשר מדורגות על בסיס תשואה משוקללת זמן (TWR) עדכנית.

3. השלמת נתונים ממערכת "ממשל זמין" (CKAN): עבור שלוש הקרנות שאותרו, מבוצעת פנייה מקבילה למערכת ה-API של משרד האוצר בהתבסס על מזהה הקרן (FUND_ID), לשם קבלת שיעורי דמי הניהול הממוצעים שנגבו בפועל.

4. הטמעה (Attachment): הנתונים המעובדים משולבים תחת שדה top_competitors במבנה הפרוטפוליו.

### ב. ניהול מטמון ומנגנון גיבוי (The Market Cache):

1. אחזור חכם (The 30-Day Rule): המערכת מתעדפת קריאת נתונים חיים. במקרה של עכבה, מתבצעת פנייה לנתוני ה-Cache. במידה ופרק הזמן שחלף קטן מ-30 ימים, המידע מוחזר למערכת.

2. מנגנון נסיגה מדורג (Fallback): (1) נתונים בזמן אמת (Live API) -> (2) נתוני ענן (Firestore Cache) -> (3) נתוני גיבוי מוטמעים מראש (Hardcoded curated data).

### שלב ב' - הפקת תובנות ואנליזה (Insights Generation)

לאחר שהנתונים חולצו למבנה JSON והועשרו בנתוני שוק חיים (Top Competitors), המידע המובנה מוזן למודל Claude (או Gemini) בליווי הקשר פרופיל המשפחה, לשם יצירת המלצות אופרטיביות (action_items).

הנחיה רשמית (Prompt) למודל ה-AI לשלב יצירת התובנות:

<div dir="ltr">

```
You are an elite, fiduciary Israeli Pension Consultant and Wealth Manager.
Your objective is to deeply analyze the family's portfolio and provide highly specific, actionable insights.

CRITICAL FAMILY CONTEXT: 
- Spouse 1 is {spouse_1_age} years old. 
- Spouse 2 is {spouse_2_age} years old (if applicable). 
- Children ages: {children_ages}. 
- Risk tolerance is '{risk_tolerance}'.
- Investment goal is '{investment_preference}'.

ANALYTICAL FRAMEWORK (What to look for):
1. Management Fees (דמי ניהול): Identify any product where fees are above the Israeli market average. Suggest negotiation or moving to a cheaper provider/track.
2. Risk vs. Age Alignment: If the spouses are relatively young and have a 'high' or 'growth' risk tolerance, but their money is in solid/general tracks, strongly recommend moving to equity/S&P500 tracks to maximize compound interest. Conversely, ensure capital preservation for older ages.
3. Insurance Gaps/Overlaps (פנסיית שאירים): Use the children's ages. If children are nearing or over 21, explicitly suggest reducing/canceling the survivor's pension coverage for them to save money and increase the savings portion.
4. Tax & Product Optimization: Suggest maximizing Keren Hishtalmut contributions (tax-free capital gains) or utilizing Kupat Gemel LeHaskaa for liquidity, if relevant.
5. Consolidation (איחוד קופות): Identify inactive accounts (no recent deposits) with high fees that should be merged.

ADVISOR INSTRUCTIONS:
- Generate between 1 and 10 highly impactful, data-driven action items. Only output recommendations that truly add value based on the data.
- Sort the action items descending by severity, with 'high' severity items first.
- Base every recommendation purely on the provided data and family context. Do not invent numbers.

OUTPUT ENFORCEMENT:
Return ONLY a valid JSON array matching this exact schema:
    ```json
[
  {{
    "id": "string (generate a unique short ID, e.g., 'fee_1', 'risk_2')",
    "type": "fee_negotiation | investment_strategy | insurance | tax_optimization",
    "title": "string (Clear, short action title in Hebrew)",
    "problem_explanation": "string (Detailed explanation in Hebrew of WHY this is an issue or opportunity, what the data shows)",
    "action_required": "string (Detailed explanation in Hebrew of WHAT exactly the user needs to do to resolve it)",
    "is_completed": false,
    "severity": "high | medium | low",
    "category": "string (Must be 'פנסיה', 'ביטוח', 'בורסה', or 'כללי')"
  }}
]
    ```

CATEGORY RULES:
- 'פנסיה': Use for Pension (מקיפה/כללית), Bituach Menahalim (ביטוח מנהלים), Keren Hishtalmut (קרן השתלמות), and Kupat Gemel (קופת גמל/להשקעה).
- 'ביטוח': Use ONLY for general risk insurance (Health, Car, Home, Life etc.) that are NOT savings/pension products.
- 'בורסה': Use for standalone stock/ETF portfolios.
- 'כללי': Use for general financial advice or tax optimization.

Return ONLY the JSON array. Do not include markdown formatting like ```json or any conversational text.
"""

```

</div>

## 2. מודול ביטוח: ממשק "הר הביטוח" (Excel/CSV)

### זרימת הנתונים (Data Flow):

1. תהליך חילוץ מתקדם (Advanced Extraction): המערכת מעבדת את נתוני קבצי ה-Excel/CSV באמצעות pandas, תוך יישום לוגיקה אלגוריתמית (_extract_har_bituach_data). קובץ המקור מושמד.

* זיהוי מבני דינמי (Dynamic Headers): סריקת 20 שורות ראשונות לאיתור הסתברותי של שורת הכותרת.

* מיפוי עמום (Fuzzy Mapping): שימוש במילון מונחים לשם התמודדות עם שונויות בסיווג העמודות.

* ניקוי וסינון נתונים: ניפוי פוליסות חסרות תוקף משפטי (פסילת 'מבוטל', 'פדה', 'סולק').

* תקנון נתוני פרמיה: פרמיות המדווחות במונחים שנתיים מומרות מתמטית לתצורה חודשית (חלוקה ב-12).

* קונסולידציית פוליסות (Consolidation): רשומות נפרדות החולקות מזהה פוליסה זהה מאוגדות לרשומת נתונים יחידה.

2. עיבוד ואנליזה חכמה (Gemini Analysis): מבנה ה-JSON הסופי מועבר למודל Gemini 2.5 Flash למטרת הפקת התראות צרכניות.

3. מיזוג נתונים (Smart Merge): הנתונים מוזרקים למבנה ה-Firestore תחת קטגוריית "ביטוח", תוך הפעלת פרוטוקול הדואג לשימור התראות פנסיה/השקעות קיימות.

### הנחיה רשמית (Prompt) למודל Gemini Flash:

<div dir="ltr">

```

You are an automated, data-driven insurance analysis engine. Your sole task is to analyze a metadata snapshot of a user's insurance portfolio (extracted from 'Har Bituach') provided in JSON format.

CRITICAL RULES:
1. DO NOT complain about missing full policy documents, medical history, or specific terms. You must work STRICTLY with the provided metadata (provider, category, premium, expiration date).
2. DO NOT output conversational text. Output ONLY a valid JSON object.
3. Generate actionable insights strictly based on these 3 criteria:
   - Expirations: Identify any policies expiring within the next 60 days.
   - Duplicates: Flag overlapping coverages (e.g., multiple active health or life insurances for the same person).
   - Cost Anomalies: Highlight exceptionally high premiums that justify a market comparison.

OUTPUT FORMAT:
Return a JSON object with a single key `action_items` containing an array of objects.
Each object must have:
- "id": "string (generate a unique short ID)"
- "type": "insurance"
- "title": "string (Short alert title in Hebrew)"
- "problem_explanation": "string (Clear explanation of the finding in Hebrew)"
- "action_required": "string (Detailed explanation in Hebrew of WHAT exactly the user needs to do to resolve it)"
- "is_completed": false
- "severity": "high | medium | low"
- "category": "ביטוח" (strictly this exact string)

Return ONLY the JSON. Do not include markdown formatting.

```

</div>

## 3. מודול ביטוח: העלאת מסמך פוליסה מלא (PDF)

### זרימת הנתונים (Data Flow):

1. אחסון ארוך טווח ומאובטח: השרת מעלה את מסמך ה-PDF השלם ל-Firebase Cloud Storage ומפיק קישור נגישות מאובטח (source_document_url).

2. חילוץ נתונים ממוקד (Claude Vision): מסמך ה-PDF מנותב למודל Claude 3.5 Sonnet לצורך משימת Data Extraction של משתני הליבה בלבד, ללא הסקת מסקנות.

3. סנכרון ועדכון מסד הנתונים: המערכת מאתרת את הרשומה המקבילה ב-Firestore (אשר מקורה בתהליך הקליטה מ"הר הביטוח"), מעדכנת את הפרטים החסרים, ומטמיעה את ה-URL של המסמך לאפשרות צפייה מה-UI.

### הנחיה רשמית (Prompt) למודל Claude:

<div dir="ltr">

```

Analyze the provided Israeli insurance policy document. Your task is pure data extraction. 
Do not provide advice or insights.

Extract the following key fields into a strict JSON format:
- "provider" (string): Name of the insurance company.
- "policy_type" (string): The type of insurance (e.g., ביטוח רכב מקיף, ביטוח בריאות פרטי).
- "monthly_premium" (number): The monthly cost in ILS. Normalize annual costs to monthly.
- "expiration_date" (string): ISO format YYYY-MM-DD.
- "covered_members" (array of strings): Names of the insured individuals.

Return ONLY the JSON object. Do not include markdown formatting like ```json or any conversational text.

```
</div>

## 4. מודול השקעות אלטרנטיביות (נדל"ן, קרנות השקעה)

### זרימת הנתונים (Data Flow):

1. קליטת מסמך ואחסון: המשתמש מעלה חוזה השקעה, Pitch Deck או תוכנית עסקית (PDF). עקב חשיבותו החוזית, המסמך מועלה ונשמר ב-Firebase Cloud Storage (source_document_url).

2. פענוח וחילוץ (Claude Vision): המסמך מועבר למודל Claude 3.5 Sonnet במטרה לקרוא את התוכנית העסקית ולחלץ את משתני ההשקעה המרכזיים.

3. סנכרון נתונים למעקב: הנתונים נשמרים ב-Firestore תחת קטגוריית השקעות אלטרנטיביות (alternative). מערכת ההתראות תשתמש בשדה estimated_end_date על מנת להתריע למשתמש על קרבה למועד סיום ההשקעה או חלוקת תזרים מתוכננת.

### הנחיה רשמית (Prompt) למודל Claude:

<div dir="ltr">

```

Analyze the provided alternative investment document (Real Estate contract, Private Equity Pitch Deck, or Business Plan).
Your objective is to extract the core financial and timeline data, and generate a brief summary of the business plan.

Extract the information into a strict JSON format matching this schema:
{
  "category": "alternative",
  "project_name": "string (Name of the project or asset)",
  "country_code": "string (2-letter ISO code, e.g., 'US', 'CY', 'IL')",
  "developer": "string (Name of the managing entity or developer)",
  "invested_amount": "number (Total capital invested)",
  "currency": "string (3-letter code, e.g., 'USD', 'EUR', 'ILS')",
  "expected_irr": "number (Expected Internal Rate of Return, if specified. Otherwise null)",
  "start_date": "string (ISO format YYYY-MM-DD, if specified)",
  "estimated_end_date": "string (ISO format YYYY-MM-DD. Calculate based on duration if exact date is not given)",
  "business_plan_highlights": [
    "string (Bullet point 1: High-level summary of the strategy in Hebrew)",
    "string (Bullet point 2: Key milestones or exit strategy in Hebrew)",
    "string (Bullet point 3: Value-add components in Hebrew)"
  ]
}

Return ONLY the JSON object. Do not include markdown formatting.

```

</div>

## 5. מודול ממשק שיחה: עוזר פיננסי חכם (Smart RAG)

### זרימת הנתונים (Data Flow):

1. סינון מבוסס-הקשר (Contextual Filtering): עם רישום שאילתה מצד המשתמש, מערכת השרת מזהה את מיקוד הנושא ומאחזרת ממסד הנתונים אך ורק את מקטעי ה-JSON הרלוונטיים, למזעור הזיות מודל.

2. שאילתה למודל השפה (Gemini Flash): השאילתה, בצירוף מערך הנתונים המסונן, משוגרת לעיבוד במודל Gemini 2.5 Flash.

3. שימוש נתמך בכלים (Tool Calling): המודל מקבל הרשאת גישה לכלי הייעודי read_full_policy(policy_id).

* שאילתה בסיסית (מידע פיננסי או מספרי): המודל מפיק מענה הישען על הנתונים במבנה ה-JSON.

* שאילתה מורכבת/משפטית (חפירה לאותיות הקטנות): המודל יפעיל את הפונקציה. השרת יאחזר את קובץ ה-PDF מהענן ויזריק את התוכן הטקסטואלי להנחיה, והמודל יפיק מענה מקצועי ומבוסס-סימוכין.

</div>