# פרומפט אינטגרציה — RAG לפוליסות ביטוח לתוך ai-wealth-monitor

> קובץ זה הוא פרומפט עצמאי לחלון Claude חדש. כל ההחלטות הארכיטקטוניות כבר הוכרעו אחרי דיון מעמיק. העתק את כל התוכן שמתחת לקו לחלון החדש.

---

אני מוסיף יכולת שאלות-תשובות על פוליסות ביטוח (RAG) לאפליקציית ניהול ההון המשפחתית שלי, ai-wealth-monitor. כל ההחלטות הארכיטקטוניות כבר הוכרעו (אחרי דיון מעמיק) — אל תשנה אותן ואל תציע אלטרנטיבות כבדות. תפקידך ליישם.

═══════════════════════════════════════
הקשר קריטי
═══════════════════════════════════════
- אפליקציה אישית למשפחה שלי, לא מסחרית. אין scale. מעט משתמשים, מעט פוליסות.
- קריטריונים, בסדר הזה: הזול ביותר → המהיר ביותר → המדויק ביותר.
- רוב הטקסט בעברית (RTL, מעורב עם מספרים: ₪, אחוזים, תאריכים). זה השפיע על ההכרעות למטה.

═══════════════════════════════════════
שני הפרויקטים
═══════════════════════════════════════
- ai-wealth-monitor: D:\AICode\ai-wealth-monitor — האפליקציה. כל היישום כאן. backend = FastAPI רזה על Cloud Run, frontend = React על Vercel, אחסון = Firebase (Firestore + Storage).
- insurance-rag: D:\AICode\insurance-rag — פרויקט אקדמי שהושלם ופרוס. משמש רק (א) כמקור לוגיקה להעתקה, (ב) להרצת ה-eval בשלב 0. אל תיגע ב-deployment/דמו שלו — הוא קפוא להגשה אקדמית.

═══════════════════════════════════════
הארכיטקטורה (מוכרעת — אל תשנה)
═══════════════════════════════════════
הכל רץ בתוך ה-backend הקיים. בלי שירות נפרד, בלי torch, בלי sentence-transformers, בלי ChromaDB, בלי Docling.
- Embeddings: gemini-embedding-001 דרך Google API (קריאה, לא מודל מקומי). לא text-embedding-004 (חלש בעברית), לא e5-large (כבד). השתמש ב-output_dimensionality=768 כדי לשמור על אחסון/חישוב רזה.
- אחסון וקטורים: Firestore (כבר בשימוש). מסמך לכל chunk ב-subcollection תחת המשפחה/פוליסה (מסמך Firestore מוגבל ל-1MB). שדות כל מסמך: { text, anchor (80 תווים ראשונים), embedding: [floats], policy_id, source_doc }.
- חיפוש דמיון: numpy cosine בתהליך (מאות וקטורים = מיידי).
- Generation: Gemini Flash (כבר בשימוש).

═══════════════════════════════════════
חילוץ טקסט (מוכרע — מותאם לעברית)
═══════════════════════════════════════
- העדף Gemini native-PDF (קורא את ה-PDF ישירות) — עוקף בעיות bidi/RTL של עברית, מטפל בסרוקים, מבין טבלאות, וזול.
- PyMuPDF רק עם ולידציה שהעברית יצאה נקייה (לא הפוכה/מבולגנת).
- אל תשתמש ב-Claude Vision בנתיב החדש (יקר).
- קריאת Gemini אחת מחזירה גם מטא-דאטה וגם Markdown מובנה עם כותרות "## " (שמזין את ה-chunking) — שתי ציפורים במכה אחת.

═══════════════════════════════════════
Chunking (העתק מהפרויקט האקדמי — עם תיקונים)
═══════════════════════════════════════
- העתק את הלוגיקה של chunk_section_aware מ-D:\AICode\insurance-rag\src\chunking.py:99. זו התובנה המוכחת (section_aware ניצח את fixed פי 2.5 ב-MRR).
- section_aware מפצל על כותרות "## " — לכן Gemini מפיק Markdown מובנה (ראה חילוץ טקסט).
- אל תעתיק את תחיליות e5 ("passage: " / "query: "). הן ספציפיות ל-e5. עם gemini-embedding-001 משתמשים ב-task_type: RETRIEVAL_DOCUMENT לקטעים, RETRIEVAL_QUERY לשאלות.
- שמור את מושג ה-anchor (80 תווים ראשונים של הטקסט הגולמי כמפתח ציטוט).

═══════════════════════════════════════
שלב 0 — ולידציה לפני הכל (חובה)
═══════════════════════════════════════
לפני שמקבעים את gemini-embedding-001, הרץ ablation מלא על כל 50 שאלות הזהב דרך D:\AICode\insurance-rag\eval\run_eval.py:
- הוסף את gemini-embedding-001 כקונפיגורציה חמישית: אותם 447 קטעי section_aware בדיוק, החלף רק את ה-embedder (קריאת Google API במקום e5), בנה collection זמני (_build_ephemeral_collection כבר עושה דבר דומה ל-fixed_300/700), והרץ את אותו _eval_run.
- השווה מול ה-baseline המוכח: section_aware (e5) = Hit@5 0.720 / MRR 0.534.
- כלל הכרעה: ≈ או > e5 → לך עליו. ירידה קלה → נסה output_dimensionality גבוה יותר או קבל את הפער. ירידה משמעותית → עצור ודווח לי לפני המשך.
- זה רץ מקומית מול הקוד של insurance-rag. אל תשנה את ה-deployment/דמו.

═══════════════════════════════════════
היישום באפליקציה — שני אתרים
═══════════════════════════════════════
אתר 1 — אינדוקס בהעלאה (חדש):
  InsuranceFlow.extract_data() ב-backend/document_flows.py:331. היום: מעלה PDF ל-Storage + מחלץ מטא-דאטה (Claude Vision) + שומר source_document_url.
  הוסף אחרי החילוץ: חלץ טקסט (Gemini native-PDF → Markdown מובנה) → chunk_section_aware → הטמע כל קטע (gemini-embedding-001, RETRIEVAL_DOCUMENT) → שמור ב-Firestore subcollection.
  חשוב: רידוד PII כבר קורה בזרימת ההעלאה — אנדקס את הגרסה המרודדת בלבד.

אתר 2 — שליפה בצ'אט (החלפה):
  copilot_chat_ask ב-backend/routers/dashboard_chat.py:91. יש tool read_full_policy (שורה ~157) שמוריד PDF שלם ודוחף עד 35,000 תווים — גס, יקר, בלי ציטוטים.
  החלף אותו ב-tool חדש (query_insurance_policy): הטמע את השאלה (RETRIEVAL_QUERY) → טען את וקטורי המשפחה מ-Firestore (לפי uid = user.get("uid")) → numpy cosine top-5 → החזר קטעים + anchors ל-Gemini כך שהתשובה כוללת ציטוטים מדויקים.

═══════════════════════════════════════
פרטים טכניים
═══════════════════════════════════════
- ה-backend כבר משתמש ב-google-genai>=1.0.0. הטמעה: client.models.embed_content(model="gemini-embedding-001", contents=..., config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768)). ודא את שם המודל המדויק/זמינות בזמן היישום (שמות מודלים משתנים).
- numpy לא ב-backend/requirements.txt — הוסף אותו.
- config.GEMINI_MODEL_NAME="gemini-2.5-flash"; config.DEMO_UID="demo-user-12345" (יש bypass לדמו — שמור עליו); GEMINI_API_KEY מ-env.
- DB דרך db_manager (Firestore); funds מזוהים ב-id / policy_number, ויש להם source_document_url.

═══════════════════════════════════════
שלבים (מוכרע)
═══════════════════════════════════════
- שלב 0: ולידציית gemini-embedding-001 על 50 שאלות הזהב (מקומי, ב-insurance-rag).
- שלב 1: אינטגרציית RAG (אדיטיבי — אתר 1 + אתר 2). השתמש ב-Gemini לחילוץ ה-Markdown המובנה בנתיב האינדוקס החדש בלבד.
- שלב 2 (אופציונלי, נפרד): החלפת חילוץ המטא-דאטה הקיים מ-Claude Vision ל-Gemini (אופטימיזציית עלות, blast radius גדול יותר — אל תעשה יחד עם שלב 1).

═══════════════════════════════════════
אילוצי אבטחה (קריטי)
═══════════════════════════════════════
- לעולם אל תפתח קבצי .env.
- לעולם אל תקרא D:\AICode\insurance-rag\data\known_pii.json או D:\AICode\insurance-rag\data\raw\ — PII אמיתי.
- לעולם אל תעשה commit ל-main/master — feature branch + PR בלבד, ואל תמזג PR בלי אישור מפורש שלי.

═══════════════════════════════════════
תהליך
═══════════════════════════════════════
1. חקור קודם: backend/document_flows.py (InsuranceFlow), backend/routers/dashboard_chat.py (copilot_chat_ask + read_full_policy), backend/db_manager.py (שמירה ב-Firestore), backend/flow_utils.py + report_utils.py (חילוץ PDF + רידוד), ובצד השני D:\AICode\insurance-rag\src\chunking.py + eval/run_eval.py.
2. הרץ שלב 0 ודווח לי את תוצאות ה-ablation לפני שממשיכים.
3. הצג design לפני קוד — במיוחד: איך Gemini מחזיר Markdown מובנה, מבנה ה-Firestore, ותוצאת הולידציה.
4. TDD, commits תכופים, הרץ בדיקות וודא build לפני שמסיימים.
