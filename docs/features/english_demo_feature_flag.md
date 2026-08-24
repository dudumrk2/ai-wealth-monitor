# Feature Flag Guide: English Demo & Multi-Language Isolation

## 1. Overview & Purpose

The **English Demo Mode** feature flag allows the WealthPilot AI platform to dynamically switch between two distinct demo experiences:
1. **Hebrew Demo (Default / Israeli Market)**:
   - Currency: **₪ (ILS)**.
   - Profile: **משפחת ישראלי** (Avi & Dana Israeli).
   - Asset Allocations: Israeli institutional funds (Harel Comprehensive Pension, Altshuler Shaham Study Fund, Migdal Provident, Clal Savings Policy, Phoenix).
   - Layout: **RTL (Right-to-Left)** with Hebrew navigation, charts, and Copilot AI chat.
2. **English Demo (International Showcase)**:
   - Currency: **$ (USD)**.
   - Profile: **Miller Family** (David & Sarah Miller).
   - Asset Allocations: Global multi-asset funds (Vanguard Target 2055, BlackRock 401(k), Fidelity Growth, Charles Schwab S&P 500, US Tech Equities).
   - Live Policy RAG: Indexed **Aetna Premier Global Health Policy (#AET-773019)** with grounded citations for experimental overseas treatments.
   - Layout: **LTR (Left-to-Right)** with English navigation, metrics, and Copilot AI chat.

---

## 2. Feature Flag Precedence & Hierarchy

The active demo language is determined by a strict fallback cascade:

```
Is Demo User?
  │
  ├─► [No] ──────────► Regular Production Mode (Hebrew / RTL)
  │
  └─► [Yes]
        │
        ├─► URL Parameter: ?lang=en / ?english_demo=true ──► English Demo (USD / LTR)
        │
        ├─► URL Parameter: ?lang=he ─────────────────────────► Hebrew Demo (ILS / RTL)
        │
        ├─► LocalStorage: demo_language == 'en' ────────────► English Demo (USD / LTR)
        │
        ├─► LocalStorage: demo_language == 'he' ────────────► Hebrew Demo (ILS / RTL)
        │
        ├─► Environment: VITE_ENABLE_ENGLISH_DEMO == 'true' ─► English Demo (USD / LTR)
        │
        └─► Default Fallback ───────────────────────────────► Hebrew Demo (ILS / RTL)
```

1. **URL Query Parameter (Highest Priority)**:
   - `?lang=en` or `?demo_lang=en` or `?english_demo=true` -> Activates English Demo ($).
   - `?lang=he` or `?english_demo=false` -> Reverts to Hebrew Demo (₪).
2. **Interactive UI Switcher (LocalStorage)**:
   - In Demo mode, an interactive pill (`עב ₪ | EN $`) appears in the top navigation bar.
   - Clicking either option immediately sets `localStorage.setItem('demo_language', 'he' | 'en')` and updates state in real-time without reloading the page.
3. **Environment Variables (Default Configuration)**:
   - Frontend: `VITE_ENABLE_ENGLISH_DEMO=true` (in `.env` or CI build).
   - Backend: `ENABLE_ENGLISH_DEMO=true` (in environment / system config).
4. **Default State**:
   - When no overrides are set, the flag defaults to **`false` (Hebrew Demo)**.

---

## 3. Code Architecture & Implementation Details

### Backend (`backend/`)
- [demo_constants.py](file:///d:/AICode/ai-wealth-monitor/backend/services/demo_constants.py):
  - `DEMO_FAMILY_PROFILE_HE` vs `DEMO_FAMILY_PROFILE_EN`
  - `DEMO_PORTFOLIO_DATA_HE` vs `DEMO_PORTFOLIO_DATA_EN`
  - `DEMO_INSURANCE_CHUNKS_HE` vs `DEMO_INSURANCE_CHUNKS_EN`
  - `DEMO_CHAT_RESPONSES_HE` vs `DEMO_CHAT_RESPONSES_EN`
  - Resolver functions: `get_demo_family_profile()`, `get_demo_portfolio_data()`, `get_demo_chat_responses()`, `get_demo_insurance_chunks()`.
  - Feature flag check: `is_english_demo_enabled()`.
- [demo_seeder.py](file:///d:/AICode/ai-wealth-monitor/backend/services/demo_seeder.py):
  - Seeds both Hebrew and English policy chunks into Firestore (`families/demo-user-12345/insurance_chunks`) with live embeddings so that RAG queries in either language work out-of-the-box.
- [dashboard_chat.py](file:///d:/AICode/ai-wealth-monitor/backend/routers/dashboard_chat.py):
  - Automatically detects query language (Hebrew characters vs. English) and returns grounded answers corresponding to the active demo mode.

### Frontend (`frontend/`)
- [i18n.ts](file:///d:/AICode/ai-wealth-monitor/frontend/src/utils/i18n.ts):
  - `isDemoMode()`: Checks if the session is a demo account.
  - `isEnglishDemoMode()`: Resolves the multi-tiered feature flag (URL -> LocalStorage -> Env).
  - `getTranslation(isEnglish)`: Returns full localization dictionary (`he` or `en`).
- [format.ts](file:///d:/AICode/ai-wealth-monitor/frontend/src/utils/format.ts):
  - `formatCurrency()`: Formats amounts as `$XX,XXX` when `isEnglishDemoMode() === true` and `₪XX,XXX` when in Hebrew mode.
- [AuthContext.tsx](file:///d:/AICode/ai-wealth-monitor/frontend/src/context/AuthContext.tsx):
  - Exposes `isDemo`, `isEnglishDemo`, and `setDemoLanguage('he' | 'en')`.
  - Automatically synchronizes `<html dir="ltr" lang="en">` vs `<html dir="rtl" lang="he">`.
- [DashboardLayout.tsx](file:///d:/AICode/ai-wealth-monitor/frontend/src/components/layout/DashboardLayout.tsx):
  - Renders the interactive `עב ₪ | EN $` language toggle pill in the header.

---

## 4. How to Test & Verify

### Running the Automated Suites:
```bash
# Frontend Unit Tests (17 suites, 83 tests)
cd frontend
npm test -- --run

# Backend Unit Tests (193 pytest tests)
cd backend
pytest
```

### Manual Verification Flows:
1. **Default Mode**:
   - Navigate to `/dashboard?demo=true`.
   - Result: Israeli portfolio, ₪ currency, RTL layout, Hebrew Copilot greeting.
2. **Switch to English**:
   - Click the `EN $` button in the top navbar (or open `/dashboard?demo=true&lang=en`).
   - Result: Miller Family, $1.45M USD, LTR layout, English Action Items.
   - In Copilot Chat, click `🩺 Policy RAG: Experimental Abroad` to verify Aetna Section 4 citation.
3. **Switch Back to Hebrew**:
   - Click the `עב ₪` button in the top navbar.
   - Result: Instant smooth switch back to the Hebrew Israeli portfolio.
