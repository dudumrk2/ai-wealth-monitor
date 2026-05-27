import { describe, it, expect } from 'vitest';
import { formatCurrency, formatPercent } from './format';

describe('formatCurrency', () => {
  it('formats ILS amount with thousands separator', () => {
    const result = formatCurrency(1000);
    expect(result).toContain('1,000');
  });

  it('formats ILS amount with currency symbol', () => {
    const result = formatCurrency(1000);
    // ILS symbol is ₪ but ICU data may vary — check for currency indicator
    expect(result).toMatch(/₪|ILS/);
  });

  it('formats zero correctly', () => {
    expect(formatCurrency(0)).toContain('0');
  });

  it('rounds to 0 decimal places', () => {
    const result = formatCurrency(1500.75);
    expect(result).not.toMatch(/1,500\.75/);
  });

  it('formats USD when currency is specified', () => {
    const result = formatCurrency(100, 'USD');
    expect(result).toContain('100');
    // USD should produce some currency indicator
    expect(result).toMatch(/\$|USD/);
  });
});

describe('formatPercent', () => {
  it('defaults to 1 decimal place', () => {
    expect(formatPercent(5.678)).toBe('5.7%');
  });

  it('respects custom decimal count', () => {
    expect(formatPercent(5.678, 2)).toBe('5.68%');
  });

  it('formats zero', () => {
    expect(formatPercent(0)).toBe('0.0%');
  });

  it('formats negative values', () => {
    expect(formatPercent(-3.5)).toBe('-3.5%');
  });
});
