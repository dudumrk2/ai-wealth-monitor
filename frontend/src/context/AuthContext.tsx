import React, { createContext, useState, useEffect, useContext } from 'react';
import { onAuthStateChanged, signInWithPopup, signOut } from 'firebase/auth';
import type { User } from 'firebase/auth';
import { auth, googleProvider } from '../lib/firebase';
import { getUserFamily } from '../lib/familyService';
import type { FamilyConfig } from '../types/portfolio';
import { STORAGE_KEYS } from '../lib/storageKeys';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  familyId: string | null;
  familyConfig: (FamilyConfig & { familyId: string }) | null;
  refreshFamily: () => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [familyConfig, setFamilyConfig] = useState<(FamilyConfig & { familyId: string }) | null>(null);

  const loadFamily = async (currentUser: User) => {
    const config = await getUserFamily(currentUser.uid, currentUser.email || '');
    setFamilyConfig(config);
    return config;
  };

  /** Re-fetch family config from Firestore (call after createFamily or deleteFamily) */
  const refreshFamily = async () => {
    if (user) await loadFamily(user);
  };

  useEffect(() => {
    // Demo bypass for Playwright tests — simulates a logged-in user with no family
    if (window.location.search.includes('demo=true')) {
      const demoUser = {
        uid: 'demo-user',
        email: 'demo@example.com',
        displayName: 'Demo Family',
      } as User;
      setUser(demoUser);

      // Load family config from localStorage if available
      const raw = localStorage.getItem(STORAGE_KEYS.FAMILY_CONFIG);
      if (raw) {
        try {
          setFamilyConfig({ ...JSON.parse(raw), familyId: 'local-demo' });
        } catch { /* ignore */ }
      }
      setLoading(false);
      return;
    }

    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      if (firebaseUser) {
        await loadFamily(firebaseUser);
      } else {
        setFamilyConfig(null);
      }
      setLoading(false);
    });

    return unsubscribe;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const signInWithGoogle = async () => {
    try {
      await signInWithPopup(auth, googleProvider);
      // onAuthStateChanged will fire and call loadFamily automatically
    } catch (error) {
      console.error('Error signing in with Google', error);
      throw error;
    }
  };

  const logout = async () => {
    try {
      await signOut(auth);
      setFamilyConfig(null);
    } catch (error) {
      console.error('Error signing out', error);
      throw error;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
          <p className="text-slate-400 text-sm">טוען...</p>
        </div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      familyId: familyConfig?.familyId ?? null,
      familyConfig,
      refreshFamily,
      signInWithGoogle,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
