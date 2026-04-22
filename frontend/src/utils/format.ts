export const formatCurrency = (amount: number, currency = 'ILS') =>
  new Intl.NumberFormat('he-IL', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(amount);

export const formatPercent = (value: number, decimals = 1) =>
  `${value.toFixed(decimals)}%`;
