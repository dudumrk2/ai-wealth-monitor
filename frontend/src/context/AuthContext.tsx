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
  signInWithDemo: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [familyConfig, setFamilyConfig] = useState<(FamilyConfig & { familyId: string }) | null>(null);

  const loadFamily = async (currentUser: User) => {
    const config = await getUserFamily(currentUser.uid, currentUser.email || '');
    
    // Flatten pii_data if present to match the expected interface
    const pii = (config as any).pii_data;
    const flattenedConfig = pii ? { 
      ...config, 
      ...pii
    } : config;
    
    setFamilyConfig(flattenedConfig);
    return flattenedConfig;
  };

  /** Re-fetch family config from Firestore (call after createFamily or deleteFamily) */
  const refreshFamily = async () => {
    if (user) await loadFamily(user);
  };

  useEffect(() => {
    // Check for existing demo session
    const isDemo = localStorage.getItem('is_demo') === 'true';
    if (isDemo) {
      const demoToken = localStorage.getItem('demo_token');
      const demoUid = localStorage.getItem('demo_uid');
      if (demoToken && demoUid) {
        const demoUser = {
          uid: demoUid,
          email: 'demo@example.com',
          displayName: 'Demo Family',
          getIdToken: async () => demoToken,
        } as any;
        setUser(demoUser);
        
        // Load family config from localStorage cache
        const raw = localStorage.getItem(STORAGE_KEYS.FAMILY_CONFIG);
        if (raw) {
          try {
            setFamilyConfig(JSON.parse(raw));
          } catch (e) {
            console.error('Error parsing demo family config', e);
          }
        }
        setLoading(false);
        return;
      }
    }

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
      setLoading(true);
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
      localStorage.removeItem('is_demo');
      const result = await signInWithPopup(auth, googleProvider);
      if (result.user) {
        await loadFamily(result.user);
      }
      // onAuthStateChanged will also fire, but loadFamily is idempotent/cached
    } catch (error) {
      console.error('Error signing in with Google', error);
      throw error;
    }
  };

  const signInWithDemo = async () => {
    try {
      setLoading(true);
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await fetch(`${API_URL}/api/auth/demo`, { method: 'POST' });
      const data = await res.json();
      
      const demoUser = {
        uid: data.uid,
        email: 'demo@example.com',
        displayName: 'Demo Family',
        getIdToken: async () => data.token,
      } as any;

      localStorage.setItem('is_demo', 'true');
      localStorage.setItem('demo_token', data.token);
      localStorage.setItem('demo_uid', data.uid);
      localStorage.setItem(STORAGE_KEYS.ONBOARDING_DONE, 'true');
      
      if (data.family_config) {
        // Flatten pii_data if present to match the FamilyConfig interface
        const pii = data.family_config.pii_data;
        const fullConfig = pii ? { 
          ...data.family_config, 
          ...pii,
          familyId: data.uid 
        } : { ...data.family_config, familyId: data.uid };
        
        localStorage.setItem(STORAGE_KEYS.FAMILY_CONFIG, JSON.stringify(fullConfig));
        setFamilyConfig(fullConfig as any);
      }

      setUser(demoUser);
      setLoading(false);
    } catch (error) {
      console.error('Error signing in with Demo', error);
      setLoading(false);
      throw error;
    }
  };

  const logout = async () => {
    try {
      localStorage.removeItem('is_demo');
      localStorage.removeItem('demo_token');
      localStorage.removeItem('demo_uid');
      localStorage.removeItem(STORAGE_KEYS.ONBOARDING_DONE);
      localStorage.removeItem(STORAGE_KEYS.FAMILY_CONFIG);
      
      await signOut(auth);
      setUser(null);
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
      signInWithDemo,
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
