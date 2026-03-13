/**
 * Family Service — all Firestore read/write operations for family management.
 *
 * Firestore schema:
 *  /families/{familyId}
 *    householdName: string
 *    createdAt: Timestamp
 *    members: { [uid]: { name: string; email: string; role: 'owner' | 'member' } }
 *    authorizedEmails: string[]
 *
 *  /users/{uid}
 *    familyId: string | null
 *    email: string
 *    joinedAt: Timestamp
 */

import {
  doc,
  getDoc,
  setDoc,
  updateDoc,
  deleteDoc,
  collection,
  query,
  where,
  getDocs,
  serverTimestamp,
} from 'firebase/firestore';
import { db } from './firebase';
import { STORAGE_KEYS } from './storageKeys';
import type { FamilyConfig } from '../types/portfolio';

// ─── Firestore helpers ────────────────────────────────────────────────────────

/** Check whether the Firebase project is real (not dummy or demo). */
const isRealFirebase = (): boolean => {
  // Playwright/demo bypass
  if (typeof window !== 'undefined' && window.location.search.includes('demo=true')) return false;
  const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID;
  return Boolean(projectId && projectId !== 'dummy-project-id');
};

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Creates a new family document and links the owner user to it.
 * Returns the new familyId.
 * Throws if the user already belongs to a family.
 */
export async function createFamily(
  uid: string,
  config: FamilyConfig
): Promise<string> {
  if (!isRealFirebase()) {
    // In demo/dev mode just use localStorage
    localStorage.setItem(STORAGE_KEYS.ONBOARDING_DONE, 'true');
    localStorage.setItem(STORAGE_KEYS.FAMILY_CONFIG, JSON.stringify(config));
    return 'local-demo';
  }

  // Check if the user already has a family
  const userRef = doc(db, 'users', uid);
  const userSnap = await getDoc(userRef);
  if (userSnap.exists() && userSnap.data().familyId) {
    throw new Error('USER_ALREADY_IN_FAMILY');
  }

  // Also check that no existing family has this email in authorizedEmails
  const email = config.member1.email;
  if (email) {
    const familiesRef = collection(db, 'families');
    const q = query(familiesRef, where('authorizedEmails', 'array-contains', email));
    const existing = await getDocs(q);
    if (!existing.empty) {
      throw new Error('EMAIL_ALREADY_IN_FAMILY');
    }
  }

  // Create the family document
  const familyRef = doc(collection(db, 'families'));
  const familyId = familyRef.id;

  await setDoc(familyRef, {
    householdName: config.householdName,
    createdAt: serverTimestamp(),
    members: {
      [uid]: {
        name: config.member1.name,
        email: config.member1.email,
        role: 'owner',
      },
    },
    authorizedEmails: [
      config.member1.email,
      config.member2.email,
      ...config.extraAuthorizedEmails,
    ].filter(Boolean),
    member1: config.member1,
    member2: config.member2,
    extraAuthorizedEmails: config.extraAuthorizedEmails,
  });

  // Link user to family
  await setDoc(userRef, {
    familyId,
    email: config.member1.email,
    joinedAt: serverTimestamp(),
  });

  // Cache locally
  localStorage.setItem(STORAGE_KEYS.ONBOARDING_DONE, 'true');
  localStorage.setItem(STORAGE_KEYS.FAMILY_CONFIG, JSON.stringify({ ...config, familyId }));

  return familyId;
}

/**
 * Looks up the family for a given user UID.
 * Returns the FamilyConfig (from Firestore + local cache), or null if none.
 */
export async function getUserFamily(uid: string, email: string): Promise<(FamilyConfig & { familyId: string }) | null> {
  if (!isRealFirebase()) {
    // Fall back to localStorage cache
    const raw = localStorage.getItem(STORAGE_KEYS.FAMILY_CONFIG);
    if (raw) {
      try {
        return { ...JSON.parse(raw), familyId: 'local-demo' };
      } catch { return null; }
    }
    return null;
  }

  try {
    // 1. Check user doc
    const userRef = doc(db, 'users', uid);
    const userSnap = await getDoc(userRef);

    let familyId: string | null = userSnap.exists() ? userSnap.data().familyId : null;

    // 2. If not found by uid, try finding by email in authorizedEmails
    if (!familyId && email) {
      const q = query(
        collection(db, 'families'),
        where('authorizedEmails', 'array-contains', email)
      );
      const snap = await getDocs(q);
      if (!snap.empty) {
        familyId = snap.docs[0].id;
        // Link user retroactively
        await setDoc(userRef, { familyId, email, joinedAt: serverTimestamp() }, { merge: true });
      }
    }

    if (!familyId) return null;

    // 3. Fetch the family doc
    const familySnap = await getDoc(doc(db, 'families', familyId));
    if (!familySnap.exists()) return null;

    const data = familySnap.data();
    const config: FamilyConfig & { familyId: string } = {
      familyId,
      householdName: data.householdName,
      member1: data.member1,
      member2: data.member2,
      extraAuthorizedEmails: data.extraAuthorizedEmails || [],
      completedAt: data.createdAt?.toDate?.()?.toISOString() || new Date().toISOString(),
    };

    // Cache locally for offline / fast reads
    localStorage.setItem(STORAGE_KEYS.ONBOARDING_DONE, 'true');
    localStorage.setItem(STORAGE_KEYS.FAMILY_CONFIG, JSON.stringify(config));

    return config;
  } catch (err) {
    console.error('getUserFamily error:', err);
    // Degrade gracefully to localStorage
    const raw = localStorage.getItem(STORAGE_KEYS.FAMILY_CONFIG);
    if (raw) {
      try { return { ...JSON.parse(raw), familyId: 'unknown' }; } catch { return null; }
    }
    return null;
  }
}

/**
 * Deletes a family. Only call if the current user is the owner.
 * Clears all member user docs and the family doc.
 */
export async function deleteFamily(familyId: string, uid: string): Promise<void> {
  if (!isRealFirebase() || familyId === 'local-demo') {
    localStorage.removeItem(STORAGE_KEYS.ONBOARDING_DONE);
    localStorage.removeItem(STORAGE_KEYS.FAMILY_CONFIG);
    return;
  }

  const familyRef = doc(db, 'families', familyId);
  const familySnap = await getDoc(familyRef);
  if (!familySnap.exists()) return;

  const data = familySnap.data();

  // Verify caller is owner
  if (!data.members?.[uid] || data.members[uid].role !== 'owner') {
    throw new Error('NOT_FAMILY_OWNER');
  }

  // Unlink all member users
  const memberUids = Object.keys(data.members || {});
  await Promise.all(
    memberUids.map(memberUid =>
      updateDoc(doc(db, 'users', memberUid), { familyId: null })
    )
  );

  // Delete the family document
  await deleteDoc(familyRef);

// Clear local cache
  localStorage.removeItem(STORAGE_KEYS.ONBOARDING_DONE);
  localStorage.removeItem(STORAGE_KEYS.FAMILY_CONFIG);
}

/**
 * Adds a new email to the extraAuthorizedEmails list.
 * Only call if the current user is the owner.
 */
export async function addAuthorizedEmail(familyId: string, uid: string, newEmail: string): Promise<void> {
  if (!isRealFirebase() || familyId === 'local-demo') {
    // Update local cache only
    const raw = localStorage.getItem(STORAGE_KEYS.FAMILY_CONFIG);
    if (raw) {
      const config = JSON.parse(raw);
      if (!config.extraAuthorizedEmails.includes(newEmail)) {
        config.extraAuthorizedEmails.push(newEmail);
        localStorage.setItem(STORAGE_KEYS.FAMILY_CONFIG, JSON.stringify(config));
      }
    }
    return;
  }

  const familyRef = doc(db, 'families', familyId);
  const familySnap = await getDoc(familyRef);
  if (!familySnap.exists()) return;

  const data = familySnap.data();

  // Verify caller is owner
  if (!data.members?.[uid] || data.members[uid].role !== 'owner') {
    throw new Error('NOT_FAMILY_OWNER');
  }

  const emailLower = newEmail.trim().toLowerCase();
  const currentExtra = data.extraAuthorizedEmails || [];
  const currentAll = data.authorizedEmails || [];

  if (!currentExtra.includes(emailLower)) {
    await updateDoc(familyRef, {
      extraAuthorizedEmails: [...currentExtra, emailLower],
      authorizedEmails: [...currentAll, emailLower],
    });

    // Update local cache
    const raw = localStorage.getItem(STORAGE_KEYS.FAMILY_CONFIG);
    if (raw) {
      const config = JSON.parse(raw);
      if (!config.extraAuthorizedEmails) config.extraAuthorizedEmails = [];
      config.extraAuthorizedEmails.push(emailLower);
      localStorage.setItem(STORAGE_KEYS.FAMILY_CONFIG, JSON.stringify(config));
    }
  }
}

