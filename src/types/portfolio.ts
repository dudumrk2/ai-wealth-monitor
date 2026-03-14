/** Shared types for portfolio funds across the application. */

/** Fund types as they appear in Israeli financial products */
export type FundCategory =
  | 'pension'              // קרן פנסיה
  | 'managers'             // ביטוח מנהלים
  | 'study'                // קרן השתלמות
  | 'provident'            // קופת גמל
  | 'investment_provident' // גמל להשקעה
  | 'stocks'               // תיק מניות
  | 'alternative';         // השקעות אלטרנטיביות

export interface Fund {
  id: string;
  category: FundCategory;
  provider_name: string;
  track_name: string;
  balance: number;
  monthly_deposit: number;  // 0 if no regular deposit
  management_fee_deposit: number;
  management_fee_accumulation: number;
  yield_1yr: number;
  yield_3yr: number;
  yield_5yr: number;
  status?: string;
  top_competitors?: Competitor[];
  /** Used internally when aggregating joint view — not in raw data. */
  _owner?: string;
}

export interface Competitor {
  provider_name: string;
  track_name: string;
  yield_1yr: number;
  yield_3yr: number;
  yield_5yr: number;
  management_fee_accumulation_avg: number;
  fund_size_billions: number;
  product_link: string;
}

export interface AlternativeInvestment {
  id: string;
  name: string;
  description: string;
  balance: number;
  monthly_deposit: number;
  expected_yearly_yield: number;
  start_date: string;    // ISO date or free text, e.g. '2024-01-01'
  end_date: string;      // ISO date or 'N/A - נזיל יומי'
}

export interface FamilyConfig {
  householdName: string;
  member1: { name: string; email: string; lastName?: string; idNumber?: string };
  member2: { name: string; email: string; lastName?: string; idNumber?: string };
  extraAuthorizedEmails: string[];
  completedAt: string;
}

export type Severity = 'high' | 'medium' | 'low';

export interface ActionItem {
  id: string;
  type: string;
  title: string;
  description: string;
  is_completed: boolean;
  severity: Severity;
}

/** Human-readable Hebrew label for each fund category */
export const CATEGORY_LABELS: Record<FundCategory, string> = {
  pension:              'פנסיה',
  managers:             'ביטוח מנהלים',
  study:                'קרן השתלמות',
  provident:            'גמל',
  investment_provident: 'גמל להשקעה',
  stocks:               'תיק מניות',
  alternative:          'השקעות אלטרנטיביות',
};
