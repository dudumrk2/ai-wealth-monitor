import { useAuth } from '../../context/AuthContext';
import { LogOut, Settings, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import clsx from 'clsx';

interface DashboardLayoutProps {
  children: React.ReactNode;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export default function DashboardLayout({ children, onRefresh, isRefreshing }: DashboardLayoutProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900">

      {/* ─── Top Header (sticky, full-width) ─── */}
      <header className="bg-white border-b border-slate-200 h-16 flex items-center justify-between px-4 md:px-8 sticky top-0 z-50 shadow-sm">

        {/* Logo */}
        <div className="flex items-center gap-3 font-bold text-lg text-slate-800 tracking-tight">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-600 to-emerald-500 flex items-center justify-center text-white shadow-md text-sm">
            AI
          </div>
          <span className="hidden sm:block">ניטור עושר משפחתי</span>
        </div>

        {/* Right side: Settings + User + Logout */}
        <div className="flex items-center gap-2">

          {/* Refresh button (optional) */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="p-2 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
              title="רענן"
            >
              <RefreshCw className={clsx("w-4 h-4", isRefreshing && "animate-spin")} />
            </button>
          )}

          {/* Settings button */}
          <button
            onClick={() => navigate('/settings')}
            className="flex items-center gap-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 px-3 py-2 rounded-lg transition-colors text-sm font-medium"
            title="הגדרות"
          >
            <Settings className="w-4 h-4" />
            <span className="hidden sm:block">הגדרות</span>
          </button>

          {/* Divider */}
          <div className="w-px h-6 bg-slate-200 mx-1 hidden sm:block"></div>

          {/* User avatar + name */}
          <div className="flex items-center gap-2.5">
            <img
              src={user?.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(user?.email || 'U')}&background=3b82f6&color=fff`}
              className="w-8 h-8 rounded-full border border-slate-200 shrink-0"
              alt="פרופיל"
            />
            <div className="hidden md:block leading-tight">
              <p className="text-sm font-semibold text-slate-800 leading-none">{user?.displayName || 'משתמש'}</p>
              <p className="text-xs text-slate-400 mt-0.5" dir="ltr">{user?.email}</p>
            </div>
          </div>

          {/* Logout */}
          <button
            onClick={handleLogout}
            className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors mr-1"
            title="יציאה"
          >
            <LogOut className="w-4 h-4" />
          </button>

        </div>
      </header>

      {/* ─── Page Content ─── */}
      <main className="flex-1 p-4 md:p-8 max-w-screen-2xl w-full mx-auto">
        {children}
      </main>

    </div>
  );
}
