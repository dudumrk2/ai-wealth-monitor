# AI Family Pension & Wealth Monitor — UI Design Reference

> **For AI Agents:** This document is the single source of truth for UI design decisions. Read this before modifying any component.

---

## 🌐 Language & Direction

- **All text is in Hebrew (עברית)**
- **RTL layout** — the root `<html>` tag has `dir="rtl"` and `lang="he"`
- Numbers, currency (₪), and percentages remain **left-to-right** (standard rendering)
- Font: System default — Hebrew characters render natively

---

## 🎨 Design System

### Color Palette
| Token | Value | Usage |
|---|---|---|
| `slate-900` | `#0f172a` | Login background, dark cards |
| `slate-800` | `#1e293b` | Login card background |
| `slate-50` | `#f8fafc` | Dashboard page background |
| `blue-600` | `#2563eb` | Primary brand color, active nav |
| `emerald-500` | `#10b981` | Positive yield, success states |
| `amber-500` | `#f59e0b` | Medium severity warnings |
| `red-500` | `#ef4444` | High severity action items |

### Typography
- **Page titles:** `text-3xl font-bold text-slate-900`
- **Card headings:** `text-lg font-bold text-slate-800`
- **Body text:** `text-sm text-slate-600`
- **Muted text:** `text-sm text-slate-500`
- **Financial numbers:** `text-2xl font-bold text-slate-900`

### Border Radius
- Cards: `rounded-2xl` or `rounded-3xl`
- Buttons: `rounded-xl`
- Tags / badges: `rounded-full`

### Shadows
- Cards: `shadow-sm`
- Modals / login card: `shadow-2xl`

---

## 🗺️ Application Routes

| Route | Access | Page |
|---|---|---|
| `/login` | Public | Login splash screen |
| `/onboarding` | Authenticated — **first login only** | Family & account setup |
| `/dashboard` | Authenticated — after onboarding | Main app |

**Routing logic:**
1. Unauthenticated user → `/login`
2. Authenticated + no onboarding completed → `/onboarding`
3. Authenticated + onboarding done → `/dashboard`

Completion state is stored in `localStorage` under the key `wealth_monitor_onboarding_done`.

---

## 📄 Pages

### 1. Login (`/login`)
- **Full-screen dark theme** (`bg-slate-900`)
- Two large blurred gradient orbs as background decoration (blue top-left, emerald bottom-right)
- A glassmorphism card (`backdrop-blur-xl bg-slate-800/60 border border-slate-700/50`)
- App logo: gradient icon (`TrendingUp` from lucide-react)
- Title: **"ניטור עושר משפחתי - AI"**
- Subtitle: **"ניתוח אוטומטי של פנסיה ותיק השקעות"**
- Two feature pills (security + yield tracking)
- Google Sign-in button: white, full-width, with Google logo SVG

### 2. Onboarding (`/onboarding`)
- **Light background** (`bg-slate-50`)
- A centered card, max-width `2xl`
- Blue gradient header strip with `Users` icon
- Security disclaimer alert box (blue)
- Form fields: Household Name (text), Authorized Google accounts (email inputs with "Add" button)
- CTA: **"סיום הגדרה"** (Complete Setup) — dark button, right-aligned
- On submit: sets `localStorage.setItem('wealth_monitor_onboarding_done', 'true')` and navigates to `/dashboard`

### 3. Dashboard (`/dashboard`)
- Uses `DashboardLayout` wrapper
- Left sidebar (desktop): logo, nav links, user profile + logout
- Top header (desktop): search bar, notification bell
- **Three tab buttons** in a pill container:
  - **"התיק שלי"** (My Portfolio)
  - **"תיק בן/בת הזוג"** (Spouse Portfolio)
  - **"תצוגה משותפת"** (Joint View)
- Right-side sidebar: **Action Items** panel

---

## 🧩 Components

### `DashboardLayout`
- Persistent sidebar (`w-64`) on `md+` screens
- Sticky top header on `md+` screens
- Mobile: sticky top bar only
- Nav links: Dashboard, Family Members, All Assets, Settings

### `ActionItems`
- Right-side sticky panel (`xl:w-80`)
- Each item: icon (severity) + title + description
- Click → toggles `is_completed`, applies `line-through` class on title
- Severity colors: `red` = high, `amber` = medium, `blue` = low

### `AssetTable`
- Rendered inside each portfolio tab for each fund category
- Columns: ספק ומסלול | יתרה | תשואה 1Y | תשואה 3Y | תשואה 5Y | דמי ניהול
- Competitor fee badge: animated pulse dot if `top_competitors` array is non-empty

---

## 🔐 Auth & Onboarding State

| Mechanism | Key |
|---|---|
| Firebase Auth | Google Sign-In via popup |
| Onboarding flag | `localStorage: wealth_monitor_onboarding_done` |
| Test bypass | `?demo=true` URL param (sets mock user, skips Firebase) |

---

## ✅ Accessibility / RTL Notes

- All page containers have `dir="rtl"` inherited from `<html>`
- Table columns are still logically ordered (provider left, fee right) — the RTL flip handles the visual direction
- Buttons with icons: icons should be placed **after** text in RTL (e.g., `סיום הגדרה <ChevronLeft />`)
