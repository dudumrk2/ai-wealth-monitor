import { describe, it, expect } from 'vitest';
import { getMonthsElapsed } from './date';

describe('getMonthsElapsed', () => {
  it('returns 0 for empty string', () => {
    expect(getMonthsElapsed('')).toBe(0);
  });

  it('returns 0 for invalid date string', () => {
    expect(getMonthsElapsed('not-a-date')).toBe(0);
  });

  it('returns 0 for a future date', () => {
    const future = new Date();
    future.setFullYear(future.getFullYear() + 2);
    expect(getMonthsElapsed(future.toISOString())).toBe(0);
  });

  it('returns approximately 12 for a date 12 months ago', () => {
    const twelveMonthsAgo = new Date();
    twelveMonthsAgo.setFullYear(twelveMonthsAgo.getFullYear() - 1);
    const result = getMonthsElapsed(twelveMonthsAgo.toISOString());
    expect(result).toBeGreaterThanOrEqual(11);
    expect(result).toBeLessThanOrEqual(13);
  });

  it('returns 0 for today', () => {
    const today = new Date().toISOString();
    expect(getMonthsElapsed(today)).toBe(0);
  });
});
