import { useAuth } from '../../context/AuthContext';
import { 
  LogOut, 
  Settings, 
  RefreshCw, 
  Bell, 
  LayoutDashboard, 
  Landmark, 
  LineChart, 
  HandCoins,
  Shield, 
  Sparkles
} from 'lucide-react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import clsx from 'clsx';
import { getTranslation } from '../../utils/i18n';

interface DashboardLayoutProps {
  children: React.ReactNode;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export default function DashboardLayout({ children, onRefresh, isRefreshing }: DashboardLayoutProps) {
  const { user, logout, isDemo, isEnglishDemo, setDemoLanguage } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const t = getTranslation(isEnglishDemo);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navLinks = [
    { name: t.nav.dashboard, path: '/dashboard', icon: LayoutDashboard },
    { name: t.nav.pension, path: '/pension', icon: Landmark },
    { name: t.nav.stocks, path: '/stocks', icon: LineChart },
    { name: t.nav.alternative, path: '/alternative', icon: HandCoins },
    { name: t.nav.insurance, path: '/insurance', icon: Shield },
  ];

  return (
    <div dir={isEnglishDemo ? "ltr" : "rtl"} className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col font-sans text-slate-900 dark:text-slate-100 transition-colors duration-200">
      
      {/* Premium Navbar */}
      <header className="flex items-center justify-between px-4 md:px-8 py-2 md:py-4 border-b border-slate-200 dark:border-slate-800/50 bg-white/80 dark:bg-slate-950/80 backdrop-blur-md sticky top-0 z-50 shadow-sm">
        
        {/* Brand Logo & Demo Pill */}
        <div className="flex items-center gap-3">
          <Link to="/dashboard" className="flex items-center gap-2 md:gap-3 font-bold text-lg md:text-xl text-slate-800 dark:text-slate-100 tracking-wide hover:opacity-80 transition-opacity">
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-600 via-indigo-500 to-emerald-500 dark:from-blue-400 dark:via-indigo-400 dark:to-emerald-400 select-none">
              {isEnglishDemo ? 'WealthPilot AI' : 'ניהול פיננסי'}
            </span>
          </Link>
          {isDemo && isEnglishDemo && (
            <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 shadow-sm">
              <Sparkles className="w-3 h-3 animate-pulse" />
              Global Demo (USD)
            </span>
          )}
        </div>

        {/* Center - Navigation links (Desktop) */}
        <nav className="hidden lg:flex items-center gap-6 xl:gap-8 font-medium">
          {navLinks.map((link) => {
            const isActive = location.pathname.startsWith(link.path);
            return (
              <Link 
                key={link.path}
                to={link.path} 
                className={clsx(
                  "pb-1 px-1 transition-all border-b-2 whitespace-nowrap text-sm",
                  isActive 
                    ? "text-blue-600 dark:text-blue-400 border-blue-600 dark:border-blue-400" 
                    : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 border-transparent hover:border-slate-300 dark:hover:border-slate-700"
                )}
              >
                {link.name}
              </Link>
            )
          })}
        </nav>

        {/* Tools, Language Switcher, User & Logout */}
        <div className="flex items-center gap-2 md:gap-4 text-slate-500 dark:text-slate-400">
          
          {/* Demo Language Switcher Pill */}
          {isDemo && (
            <div className="flex items-center bg-slate-100 dark:bg-slate-800 rounded-lg p-0.5 border border-slate-200 dark:border-slate-700 text-xs font-bold shadow-inner">
              <button
                onClick={() => setDemoLanguage('he')}
                className={clsx(
                  "px-2 py-1 rounded-md transition-all text-[11px]",
                  !isEnglishDemo 
                    ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm" 
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                )}
                title="החלף לעברית"
              >
                עב ₪
              </button>
              <button
                onClick={() => setDemoLanguage('en')}
                className={clsx(
                  "px-2 py-1 rounded-md transition-all text-[11px]",
                  isEnglishDemo 
                    ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm" 
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                )}
                title="Switch to English (USD Demo)"
              >
                EN $
              </button>
            </div>
          )}

          {/* Refresh button */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              className="hover:text-blue-600 dark:hover:text-white transition-all transform hover:rotate-180 duration-500 disabled:opacity-50 disabled:cursor-not-allowed p-1"
              title={t.nav.refresh}
            >
              <RefreshCw className={clsx("w-4 h-4 md:w-5 md:h-5", isRefreshing && "animate-spin")} />
            </button>
          )}

          <button onClick={() => navigate('/settings')} className="hover:text-slate-800 dark:hover:text-white transition-all transform hover:scale-110 duration-300 hidden md:block" title={t.nav.settings}>
            <Settings className="w-5 h-5" />
          </button>
          
          <button className="hover:text-slate-800 dark:hover:text-white transition-all transform hover:scale-110 duration-300 relative group hidden md:block" title="Notifications">
            <Bell className="w-5 h-5 group-hover:animate-swing" />
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-white dark:border-slate-950"></span>
          </button>

          <div className="w-px h-6 bg-slate-200 dark:bg-slate-700 mx-1 hidden md:block"></div>

          {/* User Profile */}
          <div className="flex items-center gap-2" title={user?.displayName || (isEnglishDemo ? 'Demo User' : 'משתמש')}>
            {user?.photoURL ? (
              <img 
                src={user.photoURL} 
                alt="Profile" 
                className="w-8 h-8 rounded-full border-2 border-blue-500/20 object-cover" 
              />
            ) : (
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold text-xs shadow-md shadow-blue-500/20">
                {user?.displayName ? user.displayName.slice(0, 2).toUpperCase() : 'U'}
              </div>
            )}
            <span className="text-sm font-semibold hidden xl:inline text-slate-700 dark:text-slate-300 max-w-[120px] truncate">
              {user?.displayName || (isEnglishDemo ? 'Demo User' : 'משתמש')}
            </span>
          </div>

          {/* Logout */}
          <button
            onClick={handleLogout}
            className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-slate-400 hover:text-red-500 transition-colors"
            title={t.nav.logout}
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Main Page Content */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 md:px-8 py-6 md:py-8 pb-24 lg:pb-8">
        {children}
      </main>

      {/* Mobile Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 flex items-center justify-around py-2 px-2 lg:hidden z-50 shadow-[0_-4px_10px_rgba(0,0,0,0.05)]">
        {navLinks.map((link) => {
          const isActive = location.pathname.startsWith(link.path);
          const Icon = link.icon;
          return (
            <Link 
              key={link.path}
              to={link.path} 
              className={clsx(
                "flex flex-col items-center gap-1 flex-1 py-1 transition-all rounded-lg",
                isActive 
                  ? "text-blue-600 dark:text-blue-400" 
                  : "text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              )}
            >
              <Icon className={clsx("w-5 h-5", isActive && "scale-110")} />
              <span className="text-[10px] font-bold">{link.name}</span>
            </Link>
          );
        })}
        <button 
          onClick={() => navigate('/settings')}
          className={clsx(
            "flex flex-col items-center gap-1 flex-1 py-1 text-slate-400",
            location.pathname === '/settings' && "text-blue-600 dark:text-blue-400"
          )}
        >
          <Settings className="w-5 h-5" />
          <span className="text-[10px] font-bold">{t.nav.settings}</span>
        </button>
      </nav>

      {/* Footer */}
      <footer className="w-full border-t border-slate-200 dark:border-slate-800/50 py-6 text-center text-xs text-slate-500 dark:text-slate-400 hidden lg:block">
        <p>© {new Date().getFullYear()} WealthPilot AI. {isEnglishDemo ? 'All rights reserved.' : 'כל הזכויות שמורות.'}</p>
      </footer>
    </div>
  );
}
