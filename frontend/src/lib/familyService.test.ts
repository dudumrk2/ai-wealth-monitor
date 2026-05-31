import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { STORAGE_KEYS } from './storageKeys';

// Avoid initializing a real Firebase app — familyService only imports `db`.
vi.mock('./firebase', () => ({ db: {} }));

import {
  createFamily,
  getUserFamily,
  deleteFamily,
  addAuthorizedEmail,
} from './familyService';

// Force the local/demo branch: isRealFirebase() returns false when the
// project id is the dummy placeholder. (A real .env may otherwise set it.)
const baseConfig = {
  householdName: 'Test Household',
  member1: { name: 'Alice', email: 'alice@example.com', lastName: 'A', idNumber: '1' },
  member2: { name: 'Bob', email: 'bob@example.com', lastName: 'B', idNumber: '2' },
  extraAuthorizedEmails: [] as string[],
} as any;

beforeEach(() => {
  localStorage.clear();
  vi.stubEnv('VITE_FIREBASE_PROJECT_ID', 'dummy-project-id');
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('familyService (demo / local mode)', () => {
  describe('createFamily', () => {
    it('persists config to localStorage and returns local-demo id', async () => {
      const id = await createFamily('uid-1', baseConfig);
      expect(id).toBe('local-demo');
      expect(localStorage.getItem(STORAGE_KEYS.ONBOARDING_DONE)).toBe('true');
      expect(JSON.parse(localStorage.getItem(STORAGE_KEYS.FAMILY_CONFIG)!)).toMatchObject({
        householdName: 'Test Household',
      });
    });
  });

  describe('getUserFamily', () => {
    it('returns the cached config with a local-demo familyId', async () => {
      localStorage.setItem(STORAGE_KEYS.FAMILY_CONFIG, JSON.stringify(baseConfig));
      const result = await getUserFamily('uid-1', 'alice@example.com');
      expect(result).not.toBeNull();
      expect(result!.familyId).toBe('local-demo');
      expect(result!.householdName).toBe('Test Household');
    });

    it('returns null when there is no cached config', async () => {
      const result = await getUserFamily('uid-1', 'alice@example.com');
      expect(result).toBeNull();
    });

    it('returns null when the cached config is corrupt JSON', async () => {
      localStorage.setItem(STORAGE_KEYS.FAMILY_CONFIG, '{not-valid-json');
      const result = await getUserFamily('uid-1', 'alice@example.com');
      expect(result).toBeNull();
    });
  });

  describe('deleteFamily', () => {
    it('clears the local cache for the local-demo family', async () => {
      localStorage.setItem(STORAGE_KEYS.ONBOARDING_DONE, 'true');
      localStorage.setItem(STORAGE_KEYS.FAMILY_CONFIG, JSON.stringify(baseConfig));
      await deleteFamily('local-demo', 'uid-1');
      expect(localStorage.getItem(STORAGE_KEYS.ONBOARDING_DONE)).toBeNull();
      expect(localStorage.getItem(STORAGE_KEYS.FAMILY_CONFIG)).toBeNull();
    });
  });

  describe('addAuthorizedEmail', () => {
    it('appends a new email to the cached extraAuthorizedEmails list', async () => {
      localStorage.setItem(STORAGE_KEYS.FAMILY_CONFIG, JSON.stringify(baseConfig));
      await addAuthorizedEmail('local-demo', 'uid-1', 'carol@example.com');
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.FAMILY_CONFIG)!);
      expect(stored.extraAuthorizedEmails).toContain('carol@example.com');
    });

    it('does not duplicate an already-authorized email', async () => {
      const cfg = { ...baseConfig, extraAuthorizedEmails: ['carol@example.com'] };
      localStorage.setItem(STORAGE_KEYS.FAMILY_CONFIG, JSON.stringify(cfg));
      await addAuthorizedEmail('local-demo', 'uid-1', 'carol@example.com');
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.FAMILY_CONFIG)!);
      const count = stored.extraAuthorizedEmails.filter((e: string) => e === 'carol@example.com').length;
      expect(count).toBe(1);
    });
  });
});
