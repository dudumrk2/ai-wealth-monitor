import { isEnglishDemoMode } from './i18n';

export const formatCurrency = (amount: number, currency?: string) => {
  const isEn = isEnglishDemoMode();
  const effectiveCurrency = currency || (isEn ? 'USD' : 'ILS');
  const locale = effectiveCurrency === 'USD' ? 'en-US' : 'he-IL';
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: effectiveCurrency,
    maximumFractionDigits: 0,
  }).format(amount);
};

export const formatPercent = (value: number, decimals = 1) =>
  `${value.toFixed(decimals)}%`;
