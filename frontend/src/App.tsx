import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { STORAGE_KEYS } from './lib/storageKeys';
import Login from './pages/Login';
import Onboarding from './pages/Onboarding';
import DashboardPage from './pages/DashboardPage';
import Pension from './pages/Pension';
import InsurancePage from './pages/InsurancePage';
import Settings from './pages/Settings';

/**
 * Route Guard: only for authenticated users.
 * If not logged in → goes to /login.
 * If logged in but onboarding not done → goes to /onboarding.
 */
function ProtectedRoute({
  children,
  requireOnboarding = false,
}: {
  children: React.ReactNode;
  requireOnboarding?: boolean;
}) {
  const { user } = useAuth();

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // If this is the Dashboard or Settings, ensure onboarding has been completed first
  if (!requireOnboarding) {
    const onboardingDone = localStorage.getItem(STORAGE_KEYS.ONBOARDING_DONE);
    if (!onboardingDone) {
      return <Navigate to="/onboarding" replace />;
    }
  }

  return <>{children}</>;
}

function AppContent() {
  const { user } = useAuth();

  return (
    <Router>
      <Routes>
        {/* Public: Login */}
        <Route
          path="/login"
          element={user ? <Navigate to="/dashboard" replace /> : <Login />}
        />

        {/* Protected: Onboarding (requires auth, but NOT prior onboarding) */}
        <Route
          path="/onboarding"
          element={
            <ProtectedRoute requireOnboarding={true}>
              <Onboarding />
            </ProtectedRoute>
          }
        />

        {/* Protected: Dashboard (requires auth + onboarding) */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />

        {/* Protected: Pension (requires auth + onboarding) */}
        <Route
          path="/pension"
          element={
            <ProtectedRoute>
              <Pension />
            </ProtectedRoute>
          }
        />

        {/* Protected: Insurance (requires auth + onboarding) */}
        <Route
          path="/insurance"
          element={
            <ProtectedRoute>
              <InsurancePage />
            </ProtectedRoute>
          }
        />

        {/* Protected: Settings (requires auth + onboarding) */}
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Settings />
            </ProtectedRoute>
          }
        />

        {/* Default: redirect to dashboard (will cascade to /onboarding or /login as needed) */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Router>
  );
}

import { ThemeProvider } from './context/ThemeContext';

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
