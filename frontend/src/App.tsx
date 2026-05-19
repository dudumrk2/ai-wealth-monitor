import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { Loader2 } from 'lucide-react';

// Lazy-load all pages so only the current route's chunk is downloaded on first visit
const Login                   = lazy(() => import('./pages/Login'));
const Onboarding              = lazy(() => import('./pages/Onboarding'));
const DashboardPage           = lazy(() => import('./pages/DashboardPage'));
const Pension                 = lazy(() => import('./pages/Pension'));
const InsurancePage           = lazy(() => import('./pages/InsurancePage'));
const Settings                = lazy(() => import('./pages/Settings'));
const StocksDashboard         = lazy(() => import('./pages/StocksDashboard'));
const AltInvestmentsDashboard = lazy(() => import('./pages/AltInvestmentsDashboard'));

/** Lightweight spinner shown while a lazy chunk is being fetched */
function PageLoader() {
  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
    </div>
  );
}

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
  const { user, familyConfig, loading } = useAuth();

  // While Firebase is still resolving auth state, don't redirect yet —
  // redirecting too early causes a flash to /login for returning users.
  if (loading && !user && !familyConfig) {
    return null;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // If this is the Dashboard or Settings, ensure onboarding has been completed first.
  // We use familyConfig as the source of truth (it's fetched from Firestore).
  if (!requireOnboarding) {
    // While familyConfig is still loading from Firestore (not from cache), hold off.
    if (!familyConfig && loading) {
      return null;
    }
    if (!familyConfig) {
      return <Navigate to="/onboarding" replace />;
    }
  }

  return <>{children}</>;
}

function AppContent() {
  const { user } = useAuth();

  return (
    <Router>
      <Suspense fallback={<PageLoader />}>
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

        {/* Protected: Stocks Portfolio (requires auth + onboarding) */}
        <Route
          path="/stocks"
          element={
            <ProtectedRoute>
              <StocksDashboard />
            </ProtectedRoute>
          }
        />

        {/* Protected: Alternative Investments (requires auth + onboarding) */}
        <Route
          path="/alternative"
          element={
            <ProtectedRoute>
              <AltInvestmentsDashboard />
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
      </Suspense>
    </Router>
  );
}

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
