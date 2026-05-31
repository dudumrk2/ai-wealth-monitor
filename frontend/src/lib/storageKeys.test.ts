import { describe, it, expect } from 'vitest';
import { STORAGE_KEYS } from './storageKeys';

describe('STORAGE_KEYS', () => {
  it('exposes the expected namespaced localStorage keys', () => {
    expect(STORAGE_KEYS.ONBOARDING_DONE).toBe('wealth_monitor_onboarding_done');
    expect(STORAGE_KEYS.FAMILY_CONFIG).toBe('wealth_monitor_family_config');
    expect(STORAGE_KEYS.ONBOARDING_DRAFT).toBe('wealth_monitor_onboarding_draft');
  });

  it('namespaces every key with the wealth_monitor_ prefix', () => {
    for (const value of Object.values(STORAGE_KEYS)) {
      expect(value.startsWith('wealth_monitor_')).toBe(true);
    }
  });

  it('has no duplicate key values', () => {
    const values = Object.values(STORAGE_KEYS);
    expect(new Set(values).size).toBe(values.length);
  });
});
