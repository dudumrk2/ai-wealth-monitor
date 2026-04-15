/** Types for the Stock Market Portfolio (Phase 2) */

export type StockCurrency = 'USD' | 'ILS';

export type StockSector =
  | 'us_tech'    // US Technology stocks
  | 'us_etf'     // US ETFs
  | 'il_stocks'  // Israeli equities
  | 'il_bonds';  // Israeli bonds / bond-like instruments

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
  /** Total market value in original currency */
  totalValueOriginal: number;
  sector: StockSector;
}

export interface ExchangeRate {
  rate: number;        // USD → ILS conversion rate
  date: string;        // ISO date when rate was fetched
  source: string;      // e.g. 'frankfurter.app'
  isFallback: boolean; // true if live fetch failed
}

export const SECTOR_LABELS: Record<StockSector, string> = {
  us_tech:   'מניות טכנולוגיה ארה"ב',
  us_etf:    'תעודות סל ארה"ב',
  il_stocks: 'ניירות ערך ישראליים',
  il_bonds:  'אגרות חוב ישראליות',
};

export const SECTOR_COLORS: Record<StockSector, string> = {
  us_tech:   '#3b82f6', // blue
  us_etf:    '#10b981', // emerald
  il_stocks: '#8b5cf6', // violet
  il_bonds:  '#f59e0b', // amber
};
