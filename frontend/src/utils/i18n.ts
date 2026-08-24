/**
 * Internationalization & Demo Mode Localization Utilities
 */

export const isDemoMode = (): boolean => {
  if (typeof window === 'undefined') return false;
  return (
    localStorage.getItem('is_demo') === 'true' ||
    window.location.search.includes('demo=true') ||
    localStorage.getItem('demo_uid') === 'demo-user-12345'
  );
};

export const isEnglishDemoMode = (): boolean => {
  if (typeof window === 'undefined') return false;
  if (!isDemoMode()) return false;

  // 1. URL Query Parameter overrides
  const urlParams = new URLSearchParams(window.location.search);
  const urlLang = urlParams.get('lang') || urlParams.get('demo_lang');
  if (urlLang === 'en' || urlParams.get('english_demo') === 'true') return true;
  if (urlLang === 'he' || urlParams.get('english_demo') === 'false') return false;

  // 2. LocalStorage user preference
  const storedLang = localStorage.getItem('demo_language');
  if (storedLang === 'en') return true;
  if (storedLang === 'he') return false;

  // 3. Environment Feature Flag
  return import.meta.env?.VITE_ENABLE_ENGLISH_DEMO === 'true';
};

export const TRANSLATIONS = {
  he: {
    nav: {
      dashboard: 'דשבורד',
      pension: 'פנסיה',
      stocks: 'בורסה',
      alternative: 'אלטרנטיבי',
      insurance: 'ביטוח',
      settings: 'הגדרות',
      logout: 'התנתק',
      refresh: 'רענן',
    },
    dashboard: {
      title: 'דשבורד משפחתי',
      subtitle: 'מרכז הבקרה הפיננסי המאוחד שלכם',
      netWorth: 'סך שווי נקי',
      pensionBalance: 'יתרת פנסיה',
      stocksPortfolio: 'תיק בורסה',
      altInvestments: 'השקעות אלטרנטיביות',
      insuranceMonthly: 'ביטוחים (חודשי)',
      assetAllocation: 'חלוקת נכסים',
      geoAllocation: 'פיזור גיאוגרפי',
      noData: 'אין נתונים',
      loading: 'טוען נתונים פיננסיים...',
      errorTitle: 'אופס, משהו השתבש',
      retry: 'נסה שנית',
    },
    actionItems: {
      title: 'פעולות נדרשות לשיפור התיק',
      shared: 'משותף',
      problemExplanation: 'הסבר בעיה',
      actionRequired: 'מה צריך לעשות',
      close: 'סגור',
    },
    stocks: {
      title: 'תיק מניות',
      subtitle: 'ניהול ומעקב תיק ניירות הערך המשפחתי',
      totalValue: 'שווי פדיון',
      dailyPnl: 'שינוי יומי',
      totalReturn: 'סך"כ רווח',
      symbol: 'סימול',
      name: 'שם נייר',
      shares: 'כמות',
      avgCost: 'מחיר ממוצע',
      currentPrice: 'מחיר נוכחי',
      sector: 'סקטור',
    },
    pension: {
      title: 'סקירת תיק פנסיוני',
      subtitle: 'עקוב, נתח ומטב את עתיד משפחתך.',
      totalPension: 'סך צבירה פנסיונית',
      monthlyDeposit: 'הפקדה חודשית',
      avgFeeAccumulation: 'דמי ניהול מצבירה',
      avgFeeDeposit: 'דמי ניהול מהפקדה',
      retirementForecast: 'תחזית קצבה חודשית',
    },
    insurance: {
      title: 'ביטוחים',
      subtitle: 'ניהול פוליסות, מניעת כפל ביטוחי והעלאת מסמכים',
      totalCost: 'עלות חודשית כוללת',
      auto: 'רכב',
      health: 'בריאות',
      life: 'חיים',
      property: 'מבנה ותכולה',
      policyNumber: 'מספר פוליסה',
      provider: 'חברה מבטחת',
      insured: 'מבוטח',
      monthlyPremium: 'פרמיה חודשית',
      activeStatus: 'פעיל',
      analyzeCopilot: 'שאל את הקופיילוט',
    },
    copilot: {
      title: 'קופיילוט פיננסי',
      initialMessage: 'שלום! אני הקופיילוט הפיננסי שלך. איך אוכל לעזור לך היום?',
      contexts: {
        all: 'כללי',
        pension: 'פנסיה',
        stocks: 'בורסה',
        insurance: 'ביטוח',
      },
      placeholder: 'שאל כל שאלה על התיק או הפוליסות שלך...',
      send: 'שלח',
      newChat: 'שיחה חדשה',
    },
    advisorChat: {
      title: 'יועץ השקעות AI',
      subtitle: 'מחובר לתיק המסחר שלך',
      initialMessage: 'שלום! אני היועץ הפיננסי שלך (מופעל ע"י AI). פירשתי את היסטוריית תיק המניות שלך ואני מוכן לענות על כל שאלה בנוגע להרכב מניות, פיזור סיכונים או הצעות השקעה לטווח ארוך. \nאיך אוכל לעזור לך היום?',
      placeholder: 'שאל משהו על תיק המניות שלך...',
      copyPrompt: 'העתק פרומפט',
      copied: 'הועתק!',
    }
  },
  en: {
    nav: {
      dashboard: 'Dashboard',
      pension: 'Retirement',
      stocks: 'Stocks',
      alternative: 'Alternatives',
      insurance: 'Insurance',
      settings: 'Settings',
      logout: 'Sign Out',
      refresh: 'Refresh',
    },
    dashboard: {
      title: 'Executive Family Wealth Dashboard',
      subtitle: 'Consolidated overview of global multi-asset portfolio and insurance policies',
      netWorth: 'Total Net Worth',
      pensionBalance: 'Retirement & Long-Term',
      stocksPortfolio: 'Public Stocks Portfolio',
      altInvestments: 'Private Equity & Real Estate',
      insuranceMonthly: 'Insurance Premiums',
      assetAllocation: 'Global Asset Allocation',
      geoAllocation: 'Geographic Exposure',
      noData: 'No Data Available',
      loading: 'Loading portfolio intelligence...',
      errorTitle: 'Unable to Load Portfolio',
      retry: 'Retry Connection',
    },
    actionItems: {
      title: 'AI Portfolio Optimization & Action Items',
      shared: 'Joint Household',
      problemExplanation: 'Diagnostic Analysis',
      actionRequired: 'Recommended Action',
      close: 'Close',
    },
    stocks: {
      title: 'Active Stocks Portfolio',
      subtitle: 'Real-time market valuation and performance metrics',
      totalValue: 'Total Portfolio Value',
      dailyPnl: 'Daily Change',
      totalReturn: 'Total Return / P&L',
      symbol: 'Ticker',
      name: 'Security Name',
      shares: 'Shares',
      avgCost: 'Avg Price',
      currentPrice: 'Market Price',
      sector: 'Sector',
    },
    pension: {
      title: 'Retirement & Pension Accounts',
      subtitle: 'Track 401(k), IRAs, fee structures, and projected retirement income',
      totalPension: 'Total Retirement Assets',
      monthlyDeposit: 'Monthly Contributions',
      avgFeeAccumulation: 'Avg Asset Fee',
      avgFeeDeposit: 'Avg Contribution Fee',
      retirementForecast: 'Projected Monthly Payout',
    },
    insurance: {
      title: 'Insurance Portfolio & Policy RAG',
      subtitle: 'Coverage intelligence, policy verification, and automated rate negotiation',
      totalCost: 'Total Monthly Premium',
      auto: 'Vehicle Insurance',
      health: 'Global Health',
      life: 'Life Insurance',
      property: 'Home & Umbrella',
      policyNumber: 'Policy ID',
      provider: 'Carrier',
      insured: 'Covered Person',
      monthlyPremium: 'Monthly Premium',
      activeStatus: 'Active',
      analyzeCopilot: 'Query Policy RAG',
    },
    copilot: {
      title: 'AI Wealth Copilot',
      initialMessage: "Hello David! I am your AI Wealth Copilot. I've analyzed your family's $1.45M portfolio, asset allocation across Vanguard & BlackRock, and indexed your Aetna Premier Health policy. How can I assist you today?",
      contexts: {
        all: 'General',
        pension: 'Retirement',
        stocks: 'Equities',
        insurance: 'Insurance & RAG',
      },
      placeholder: 'Ask any question about your assets or insurance clauses...',
      send: 'Send',
      newChat: 'New Chat',
    },
    advisorChat: {
      title: 'AI Investment Advisor',
      subtitle: 'Live connection to your investment portfolio',
      initialMessage: "Hello David! I am your AI Investment Advisor. I've analyzed your family's $181,010 active stock portfolio across NVIDIA, Apple, Microsoft, Alphabet, and cash reserves. How can I assist you with your equity allocations today?",
      placeholder: 'Ask anything about your equity portfolio or sector weightings...',
      copyPrompt: 'Copy Prompt',
      copied: 'Copied!',
    }
  }
};

export const getTranslation = (isEnglish: boolean = isEnglishDemoMode()) => {
  return isEnglish ? TRANSLATIONS.en : TRANSLATIONS.he;
};
