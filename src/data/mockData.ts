import type { Fund, AlternativeInvestment, ActionItem } from '../types/portfolio';

/**
 * Mock data reflecting exact numbers from the UI reference screenshots.
 *
 * User 1 (דוד) accumulated breakdown:
 *  פנסיה        ₪1,524,380  32%  → ₪5,460/mo
 *  מנהלים       ₪  865,728  18%  → ₪4,476/mo
 *  השתלמות      ₪1,196,549  25%  → ₪4,770/mo
 *  גמל          ₪   83,236   2%  → ₪0/mo
 *  גמל להשקעה   ₪  132,945   3%  → ₪0/mo
 *  Total monthly: ₪14,706
 */

export const MOCK_DATA = {
  last_updated: '2026-03-13T10:00:00Z',
  portfolios: {
    user: {
      funds: [
        // ─── פנסיה ────────────────────────────────────────────────────────
        {
          id: 'pen_u1',
          category: 'pension',
          provider_name: 'הראל',
          track_name: 'פנסיה מקיפה - מסלול מניות',
          status: 'active',
          balance: 1_524_380,
          monthly_deposit: 5_460,
          management_fee_deposit: 1.5,
          management_fee_accumulation: 0.15,
          yield_1yr: 12.4,
          yield_3yr: 25.1,
          yield_5yr: 42.3,
          top_competitors: [
            {
              provider_name: 'אלטשולר שחם',
              track_name: 'מקיפה מנייתי',
              yield_1yr: 14.2,
              yield_3yr: 22.1,
              yield_5yr: 40.5,
              management_fee_accumulation_avg: 0.18,
              fund_size_billions: 32.5,
              product_link: 'https://www.altshuler-shaham.co.il/pension',
            },
          ],
        },
        // ─── ביטוח מנהלים ────────────────────────────────────────────────
        {
          id: 'mgr_u1',
          category: 'managers',
          provider_name: 'מנורה מבטחים',
          track_name: 'ביטוח מנהלים - מסלול כללי',
          status: 'active',
          balance: 865_728,
          monthly_deposit: 4_476,
          management_fee_deposit: 2.0,
          management_fee_accumulation: 0.25,
          yield_1yr: 9.8,
          yield_3yr: 20.3,
          yield_5yr: 37.1,
          top_competitors: [],
        },
        // ─── קרן השתלמות ─────────────────────────────────────────────────
        {
          id: 'stu_u1',
          category: 'study',
          provider_name: 'ילין לפידות',
          track_name: 'השתלמות מסלול כללי',
          status: 'active',
          balance: 1_196_549,
          monthly_deposit: 4_770,
          management_fee_deposit: 0.0,
          management_fee_accumulation: 0.6,
          yield_1yr: 8.5,
          yield_3yr: 15.2,
          yield_5yr: 30.1,
          top_competitors: [],
        },
        // ─── גמל ────────────────────────────────────────────────────────
        {
          id: 'prov_u1',
          category: 'provident',
          provider_name: 'אנליסט',
          track_name: 'קופת גמל - מסלול שמרני',
          status: 'active',
          balance: 83_236,
          monthly_deposit: 0,
          management_fee_deposit: 0.0,
          management_fee_accumulation: 0.5,
          yield_1yr: 5.2,
          yield_3yr: 10.1,
          yield_5yr: 18.5,
          top_competitors: [],
        },
        // ─── גמל להשקעה ─────────────────────────────────────────────────
        {
          id: 'invprov_u1',
          category: 'investment_provident',
          provider_name: 'מיטב',
          track_name: 'גמל להשקעה - מסלול מניות',
          status: 'active',
          balance: 132_945,
          monthly_deposit: 0,
          management_fee_deposit: 0.0,
          management_fee_accumulation: 0.45,
          yield_1yr: 14.2,
          yield_3yr: 30.5,
          yield_5yr: 52.3,
          top_competitors: [],
        },
      ] satisfies Fund[],
      alternative_investments: [
        {
          id: 'alt_u1',
          name: 'קרן כספית שקלית',
          description: 'השקעה נזילה בקרן כספית המהווה תחליף לפיקדון בנקאי',
          balance: 85_000,
          monthly_deposit: 0,
          expected_yearly_yield: 4.2,
          start_date: '2023-06-01',
          end_date: 'נזיל יומי',
        },
        {
          id: 'alt_u2',
          name: 'נדל"ן מניב - דירה להשכרה',
          description: 'דירת 3 חדרים בתל אביב, שכירות חודשית ₪5,200',
          balance: 1_850_000,
          monthly_deposit: 5_200,
          expected_yearly_yield: 3.4,
          start_date: '2018-03-15',
          end_date: 'ללא הגבלה',
        },
      ] satisfies AlternativeInvestment[],
    },

    spouse: {
      funds: [
        // ─── פנסיה ────────────────────────────────────────────────────────
        {
          id: 'pen_s1',
          category: 'pension',
          provider_name: 'מנורה מבטחים',
          track_name: 'פנסיה מקיפה - תלוי גיל',
          status: 'active',
          balance: 380_000,
          monthly_deposit: 3_800,
          management_fee_deposit: 2.0,
          management_fee_accumulation: 0.2,
          yield_1yr: 9.2,
          yield_3yr: 18.5,
          yield_5yr: 35.0,
          top_competitors: [],
        },
        // ─── קרן השתלמות ─────────────────────────────────────────────────
        {
          id: 'stu_s1',
          category: 'study',
          provider_name: 'הראל',
          track_name: 'השתלמות מסלול מניות',
          status: 'active',
          balance: 148_000,
          monthly_deposit: 2_100,
          management_fee_deposit: 0.0,
          management_fee_accumulation: 0.55,
          yield_1yr: 9.1,
          yield_3yr: 17.8,
          yield_5yr: 32.0,
          top_competitors: [],
        },
      ] satisfies Fund[],
      alternative_investments: [] as AlternativeInvestment[],
    },

    joint: {
      total_family_wealth: 4_721_838,
      asset_allocation_percentages: {
        stocks: 55,
        bonds: 30,
        cash_equivalents: 15,
      },
      provider_exposure: {
        'הראל': 38,
        'מנורה מבטחים': 32,
        'ילין לפידות': 15,
        'מיטב': 8,
        'אחר': 7,
      },
      // Stock portfolio — joint only
      stock_investments: [
        {
          id: 'stk_1',
          category: 'stocks',
          provider_name: 'אינטראקטיב ברוקרס',
          track_name: 'תיק מניות עצמאי - S&P 500',
          balance: 210_000,
          monthly_deposit: 3_000,
          management_fee_deposit: 0.0,
          management_fee_accumulation: 0.03,
          yield_1yr: 22.1,
          yield_3yr: 48.5,
          yield_5yr: 89.2,
          top_competitors: [],
        },
        {
          id: 'stk_2',
          category: 'stocks',
          provider_name: 'מיטב',
          track_name: 'קרן מחקה ת״א 125',
          balance: 95_000,
          monthly_deposit: 1_000,
          management_fee_deposit: 0.0,
          management_fee_accumulation: 0.1,
          yield_1yr: 15.3,
          yield_3yr: 31.0,
          yield_5yr: 55.5,
          top_competitors: [],
        },
      ] satisfies Fund[],
    },
  },

  action_items: [
    {
      id: 'task_1',
      type: 'insurance_optimization',
      title: 'עדכון סטטוס ביטוחי - פנסיית שאירים',
      description: 'הבן הבכור כיום בן 18. בעוד פחות מ-3 שנים הוא יגיע לגיל 21 וייצא מתחולת פנסיית השאירים לפי התקנון. מומלץ להגדיר תזכורת לעדכון המסלול הביטוחי בקרן הפנסיה במועד זה, כדי להקטין את עלויות הביטוח ולהפנות יותר כספים לחיסכון.',
      is_completed: false,
      severity: 'medium',
    },
    {
      id: 'task_2',
      type: 'fee_negotiation',
      title: 'הוזלת דמי ניהול בקרן הפנסיה של אשתך',
      description: "דמי הניהול מצבירה ב'מנורה מבטחים' (0.2%) גבוהים ביחס לצבירה וביחס לדמי הניהול שלך ב'הראל' (0.15%). יש ליצור קשר עם הסוכן ולבקש השוואת תנאים.",
      is_completed: false,
      severity: 'high',
    },
    {
      id: 'task_3',
      type: 'investment_strategy',
      title: 'בחינת כפילות מדדים',
      description: 'זוהתה חפיפה גבוהה בין מסלול המניות בפנסיה לבין החזקות בתיק ההשקעות העצמאי. מומלץ לבחון את פיזור הסיכונים הכולל.',
      is_completed: true,
      severity: 'low',
    },
  ] satisfies ActionItem[],
};
