# AI Family Pension & Wealth Monitor - Developer Progress Log

This document tracks development history, architectural decisions, and current project context. It is intended to help AI agents and human developers quickly get oriented.

## 📅 Project History & Decisions

### 2026-03-13 (Phase 1: Frontend Architecture & Foundation)
- **Goal:** Set up the Vite React frontend with Tailwind CSS, Google Auth, and build the core dashboard UI with mock data.
- **Decision:** Use hardcoded `mockData.ts` representing the backend schema to immediately prototype the frontend UI independently of the backend API.
- **Decision:** Incorporate an `Onboarding` flow per user request to manage allowed Google accounts and family members.
- **Decision:** Implement E2E automation testing via Playwright to ensure core flows (Login -> Onboarding -> Dashboard tabs -> Action items) stay robust through development.
- **Fix:** Substituted initialized Firebase API values with dummy strings for local development, as undefined values caused React to crash to a white screen.
- **Fix:** Extracted `User` type from Firebase auth as `import type { User }` to prevent Vite from throwing a module export error.

## 📋 Current Implementation Steps (See `task.md` for full breakdown)
- [x] Initialize Vite React project with Tailwind CSS
- [x] Create `PROGRESS.md`
- [x] Set up Firebase and `.env` for Authentication
- [x] Create mock data file from provided JSON
- [x] Create Authentication UI and Route Guard
- [x] Create Onboarding Page
- [x] Design and build main Dashboard Layout
- [x] Implement Navigation & Portfolio Views
- [x] Implement Action Items
- [x] Final UI Polish
- [x] Set up end-to-end automation testing (Playwright)

## 🐛 Known Issues & Blockers
- Awaiting real Firebase configuration map from the deployment environment.

---

### 2026-03-13 (Phase 2: Hebrew UI, Onboarding & Design Reference)
- **Decision:** All UI text translated to Hebrew. Full RTL support via `<html dir="rtl" lang="he">`.
- **Decision:** Numbers, currency (₪), and percentage columns use `dir="ltr"` to render correctly inside RTL layout.
- **Decision:** Created `UI_DESIGN.md` at root — a comprehensive design reference for future agents covering routes, color palette, component spec, and RTL notes.
- **Fix:** Onboarding page was not showing. Fixed routing in `App.tsx` to check `localStorage.getItem('wealth_monitor_onboarding_done')` — if missing, the Dashboard route redirects to `/onboarding` first. Login also routes to `/onboarding` on first sign-in.
- **Fix:** Playwright test failed due to Hebrew geresh quotation mark (״) vs straight double quote (") mismatch in the `סה״כ` string. Replaced assertion with `עושר משפחתי מאוחד` which is unambiguous.

### 2026-03-13 (Phase 3: Firestore Integration & Family Management)
- **Goal:** Add cloud persistence so the user and spouse can view data concurrently across devices.
- **Decision:** Implemented a new `familyService` to handle Firestore reads/writes (`createFamily`, `getUserFamily`, `deleteFamily`). It degrades gracefully to `localStorage` if real Firebase credentials are not supplied in `.env`.
- **Decision:** Enforced single-family constraint. A user cannot join multiple families.
- **Security:** Family deletion requires the user to be the 'owner' and to explicitly type the household name.
- **Feature:** Created the Settings page (`/settings`) to manage authorized emails, view joint members, and handle the Danger Zone delete modal. Added capability to dynamically insert new authorized emails directly from the Settings page.

### 2026-03-13 (Phase 4: Advanced Portfolio Views & Component Refactor)
- **Goal:** Provide detailed asset breakdown per the user's reference screenshots.
- **Decision:** Removed hardcoded StatCards and built a dynamic `PortfolioSummaryCard` that renders a pure SVG donut chart (no external chart library) and a detailed breakdown table.
- **Decision:** The Dashboard now shows two summary cards per tab: one for `Accumulated Balance` (Solid Donut) and one for `Monthly Deposits` (Dashed Donut).
- **Data Model:** Restructured `mockData.ts` and `portfolio.ts` to use a unified `funds` array with a strict `Category` property (`pension`, `managers`, `study`, `provident`, `investment_provident`, `stocks`, `alternative`) populated with exact realistic numbers and monthly deposits.
- **Feature:** Remade the `AlternativeInvestmentsCard` into a full `AlternativeInvestmentsTable` featuring Start and End Date columns, and a rich inline modal for adding new manual assets. 

### 2026-03-13 (Phase 5: Playwright Automation Coverage Expansion)
- **Goal:** Protect new features from regressions.
- **Action:** Added E2E tests for the Settings page (`kid@gmail.com` authorization and delete modal validation) and the Alternative Investments form (`רכב להשכרה` submission loop). Test suite now at 7 passing cases.

### 2026-06-03 (Phase 6: Weekly GCP Log Monitor)
- **Goal:** Enable weekly log monitoring with simultaneous notifications to Telegram and Gmail.
- **Decision:** Implement a weekly GCP Cloud Run log scanner. It normalises and groups errors/warnings from the last 7 days by error signature.
- **Decision:** Use Gemini Flash to write a short Telegram notification and a detailed HTML **AI Investigation Brief** email. The email includes repository file hints and raw log context, designed to be pasted directly into an AI coding assistant.
- **Decision:** Expose cron endpoint secured by `X-Cron-Secret` and manual run endpoint secured by Firebase user auth.
- **Decision:** Pause the Cloud Scheduler job in the GCP Console to disable the scan (avoiding settings page complexity).
- **Action:** Added `google-cloud-logging` dependency, implemented `routers/log_monitor.py`, registered the router in `app.py`, and added unit tests in `tests/test_log_monitor.py`.
- **Deployment:** Deployed the updated backend service containing the weekly log monitor routes to Google Cloud Run (`finance-family-backend` in `me-west1`).
- **Cloud Scheduler:** Created and enabled the Cloud Scheduler job `log-monitor-weekly` in `us-central1` (Schedule: `0 8 * * 1` Asia/Jerusalem), verified with a successful force-run triggering HTTP 200 and generating an AI investigation brief email.
