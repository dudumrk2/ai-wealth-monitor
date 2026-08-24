# English Demo Mode Feature Branch (`feat/english-demo-mode`)

## Overview
This branch contains the implementation of the **English Demo Mode** for the AI Wealth Monitor. It allows users to log in with a demo account and experience the dashboard, chat, and other features entirely in English with realistic demo data, without needing to connect real financial institutions or wait for data processing.

## Key Changes
1. **Frontend (`isEnglishDemo` & Localization)**:
   - Added support for tracking `demoLang` in the auth context.
   - Replaced hardcoded Hebrew strings with a simple `getTranslation` mechanism (`frontend/src/utils/translations.ts`) to serve both English and Hebrew strings based on `isEnglishDemo`.
   - Adapted the Copilot Chat logic to provide English fallback responses when in English demo mode.
   - Updated the login screen to allow selecting between "Enter as Demo" (Hebrew) and "Demo (English)".

2. **Backend (Demo Data Payload)**:
   - Added an English demo payload (`DEMO_PORTFOLIO_DATA_EN`) to simulate the user's financial portfolio.
   - The `/api/auth/demo` endpoint supports the `lang` parameter and returns the appropriate profile and portfolio payload.

3. **Cloud Run Fixes**:
   - Fixed an issue where `RotatingFileHandler` tried to write to the read-only `/app` directory by changing it to `/tmp`.
   - Added `ENV PYTHONIOENCODING=utf-8` to the Dockerfile to prevent crashes caused by emoji logging (`UnicodeEncodeError`) in the Cloud Run Linux environment.

## How to Deploy / Use
If you need to show the demo to investors or English speakers again:
1. Checkout this branch: `git checkout feat/english-demo-mode`
2. Deploy the backend to Cloud Run:
   ```bash
   gcloud builds submit --tag me-west1-docker.pkg.dev/finance-family-management/mcp-cloud-run-deployments/finance-family-backend:latest --project finance-family-management
   gcloud run deploy finance-family-backend --image me-west1-docker.pkg.dev/finance-family-management/mcp-cloud-run-deployments/finance-family-backend:latest --region me-west1 --project finance-family-management --allow-unauthenticated
   ```
   *(Note: The standard `gcloud run deploy --source` might fail with `Container import failed` due to Artifact Registry permissions, so the `builds submit` workaround is recommended).*
3. Deploy the frontend to Vercel:
   ```bash
   vercel --prod
   ```
4. Access the site and use the English Demo login option.

## DO NOT DELETE
Keep this branch alive as long as English investor demos are required. Do not merge to `main` until full localization (i18n) is planned for the entire product.
