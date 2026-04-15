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
  Shield 
} from 'lucide-react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import clsx from 'clsx';

interface DashboardLayoutProps {
  children: React.ReactNode;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export default function DashboardLayout({ children, onRefresh, isRefreshing }: DashboardLayoutProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navLinks = [
    { name: 'דשבורד', path: '/dashboard', icon: LayoutDashboard },
    { name: 'פנסיה', path: '/pension', icon: Landmark },
    { name: 'בורסה', path: '/stocks', icon: LineChart },
    { name: 'אלטרנטיבי', path: '/alternative', icon: HandCoins },
    { name: 'ביטוח', path: '/insurance', icon: Shield },
  ];

  return (
    <div dir="rtl" className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col font-sans text-slate-900 dark:text-slate-100 transition-colors duration-200">
      
      {/* Premium Navbar */}
      <header className="flex items-center justify-between px-4 md:px-8 py-2 md:py-4 border-b border-slate-200 dark:border-slate-800/50 bg-white/80 dark:bg-slate-950/80 backdrop-blur-md sticky top-0 z-50 shadow-sm">
        
        {/* Right (Start in RTL) - Logo */}
        <Link to="/dashboard" className="flex items-center gap-2 md:gap-3 font-bold text-lg md:text-xl text-slate-800 dark:text-slate-100 tracking-wide hover:opacity-80 transition-opacity">
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-600 via-indigo-500 to-emerald-500 dark:from-blue-400 dark:via-indigo-400 dark:to-emerald-400 select-none">
            ניהול פיננסי
          </span>
        </Link>

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

        {/* Left (End in RTL) - Tools, User & Logout */}
        <div className="flex items-center gap-2 md:gap-5 text-slate-500 dark:text-slate-400">
          
          {/* Refresh button */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              className="hover:text-blue-600 dark:hover:text-white transition-all transform hover:rotate-180 duration-500 disabled:opacity-50 disabled:cursor-not-allowed p-1"
              title="רענן"
            >
              <RefreshCw className={clsx("w-4 h-4 md:w-5 md:h-5", isRefreshing && "animate-spin")} />
            </button>
          )}

          <button onClick={() => navigate('/settings')} className="hover:text-slate-800 dark:hover:text-white transition-all transform hover:scale-110 duration-300 hidden md:block">
            <Settings className="w-5 h-5" />
          </button>
          
          <button className="hover:text-slate-800 dark:hover:text-white transition-all transform hover:scale-110 duration-300 relative group hidden md:block">
            <Bell className="w-5 h-5 group-hover:animate-swing" />
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-red-500 rounded-full border-2 border-white dark:border-slate-950"></span>
          </button>

          <div className="w-px h-6 bg-slate-200 dark:bg-slate-700 mx-1 hidden md:block"></div>

          {/* User Profile */}
          <div className="flex items-center gap-2" title={user?.displayName || user?.email || 'משתמש'}>
            <img
              src={user?.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(user?.email || 'U')}&background=3b82f6&color=fff`}
              className="w-7 h-7 md:w-9 md:h-9 rounded-full border border-slate-200 dark:border-slate-700 shrink-0 hover:shadow-[0_0_15px_rgba(59,130,246,0.3)] transition-shadow cursor-pointer"
              alt="פרופיל"
            />
          </div>

          <button
            onClick={handleLogout}
            className="p-1.5 md:p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors"
            title="יציאה"
          >
            <LogOut className="w-4 h-4 md:w-5 md:h-5" />
          </button>
        </div>
      </header>

      {/* ─── Page Content ─── */}
      <main className="flex-1 p-3 md:p-8 max-w-screen-2xl w-full mx-auto pb-20 lg:pb-8">
        {children}
      </main>

      {/* ─── Mobile Bottom Navigation ─── */}
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
          )
        })}
        <button 
          onClick={() => navigate('/settings')}
          className={clsx(
            "flex flex-col items-center gap-1 flex-1 py-1 text-slate-400",
            location.pathname === '/settings' && "text-blue-600 dark:text-blue-400"
          )}
        >
          <Settings className="w-5 h-5" />
          <span className="text-[10px] font-bold">הגדרות</span>
        </button>
      </nav>

    </div>
  );
}
