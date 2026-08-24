/** Types for the Stock Market Portfolio (Phase 2) */

export type StockCurrency = 'USD' | 'ILS';

export type StockSector =
  | 'mutual_funds'  // קרנות נאמנות
  | 'etf'           // קרנות סל
  | 'foreign_funds' // קרנות חוץ
  | 'stocks'        // מניות
  | 'bonds'         // אג"ח
  | 'makam'         // מק"מ
  | 'cash';         // מזומן

export interface StockHolding {
  id: string;
  /** Hebrew display name */
  name: string;
  /** English name (optional for Israeli securities) */
  nameEn?: string;
  symbol: string;
  lastPrice: number;
  currency: StockCurrency;
  dailyChangePercent: number;   // e.g. 1.23 means +1.23%
  dailyPnlOriginal: number;     // daily P&L in original currency
  totalPnlOriginal: number;     // total P&L in original currency
  totalReturnPercent: number;   // cumulative return %
  qty: number;
  /** Alias for qty — used in some broker CSV formats */
  shares?: number;
  /** Average cost price in original currency */
  avgCostPrice?: number;
  /** Total market value in original currency */
  totalValueOriginal: number;
  sector: StockSector;
  /** 'manual' for hand-entered holdings, 'csv' for uploaded broker data */
  source?: 'manual' | 'csv' | string;
}

export interface ExchangeRate {
  rate: number;        // USD → ILS conversion rate
  date: string;        // ISO date when rate was fetched
  source: string;      // e.g. 'frankfurter.app'
  isFallback: boolean; // true if live fetch failed
}

export const SECTOR_LABELS: Record<string, string> = {
  mutual_funds:  'קרנות נאמנות',
  etf:           'קרנות סל',
  foreign_funds: 'קרנות חוץ',
  stocks:        'מניות',
  bonds:         'אג"ח',
  makam:         'מק"מ',
  cash:          'מזומן',
  technology:    'טכנולוגיה',
  semiconductors:'שבבים ומוליכים למחצה',
};

export const SECTOR_LABELS_EN: Record<string, string> = {
  mutual_funds:  'Mutual Funds',
  etf:           'ETFs',
  foreign_funds: 'Foreign Funds',
  stocks:        'Equities / Stocks',
  bonds:         'Fixed Income / Bonds',
  makam:         'T-Bills / Short-term',
  cash:          'Cash & Equivalents',
  technology:    'Technology',
  semiconductors:'Semiconductors',
};

export const SECTOR_COLORS: Record<string, string> = {
  mutual_funds:  '#a855f7', // Purple
  etf:           '#3b82f6', // Blue
  foreign_funds: '#f97316', // Orange
  stocks:        '#2dd4bf', // Teal/Cyan
  bonds:         '#22c55e', // Green
  makam:         '#1e3a8a', // Dark blue
  cash:          '#fdba74', // Light orange
  technology:    '#3b82f6', // Blue
  semiconductors:'#6366f1', // Indigo
};
