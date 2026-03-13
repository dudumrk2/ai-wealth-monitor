 import React from 'react'; 
import { useAuth } from '../../context/AuthContext';
import { LogOut, Home, Users, Briefcase, Settings, Bell, Search, Menu } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row font-sans text-slate-900">
      
      {/* Mobile Header Sidebar placeholder */}
      <div className="md:hidden bg-white border-b border-slate-200 p-4 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-2 font-bold text-lg text-slate-800">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white">AI</div>
          Wealth Monitor
        </div>
        <button className="text-slate-500 hover:text-slate-800"><Menu /></button>
      </div>

      {/* Desktop Sidebar */}
      <aside className="hidden md:flex flex-col w-64 bg-white border-r border-slate-200 h-screen sticky top-0 shadow-sm z-40">
        <div className="p-6">
          <div className="flex items-center gap-3 font-bold text-xl text-slate-800 tracking-tight">
             <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-emerald-500 flex items-center justify-center text-white shadow-lg shadow-blue-500/20">AI</div>
             Wealth
          </div>
        </div>

        <nav className="flex-1 px-4 space-y-1 overflow-y-auto">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 px-3 mt-4">Main Menu</div>
          <a href="#" className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-blue-50 text-blue-700 font-medium font-medium transition-colors">
            <Home className="w-5 h-5" /> Dashboard
          </a>
          <a href="#" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-600 hover:bg-slate-50 hover:text-slate-900 font-medium transition-colors">
            <Users className="w-5 h-5" /> Family Members
          </a>
          <a href="#" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-600 hover:bg-slate-50 hover:text-slate-900 font-medium transition-colors">
            <Briefcase className="w-5 h-5" /> All Assets
          </a>
          
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 px-3 mt-8">Configuration</div>
          <a href="#" className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-600 hover:bg-slate-50 hover:text-slate-900 font-medium transition-colors">
            <Settings className="w-5 h-5" /> Settings
          </a>
        </nav>

        <div className="p-4 border-t border-slate-200">
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-50 cursor-pointer">
            <img 
              src={user?.photoURL || `https://ui-avatars.com/api/?name=${user?.email}`} 
              className="w-9 h-9 rounded-full border border-slate-200"
              alt="Profile"
            />
            <div className="flex-1 min-w-0">
               <p className="text-sm font-medium text-slate-900 truncate">{user?.displayName || 'User'}</p>
               <p className="text-xs text-slate-500 truncate">{user?.email}</p>
            </div>
            <button onClick={handleLogout} className="text-slate-400 hover:text-red-500 transition-colors p-1" title="Logout">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {/* Top bar */}
        <header className="hidden md:flex bg-white/80 backdrop-blur-md border-b border-slate-200 h-16 items-center justify-between px-8 z-30 sticky top-0">
          <div className="flex items-center gap-2 max-w-md w-full">
            <Search className="w-4 h-4 text-slate-400 absolute ml-3" />
            <input 
               type="text" 
               placeholder="Search assets, providers..." 
               className="w-full bg-slate-100/50 border-none pl-10 pr-4 py-2 rounded-full text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-shadow placeholder:text-slate-400 text-slate-700"
            />
          </div>
          <div className="flex items-center gap-4">
             <button className="relative p-2 text-slate-400 hover:bg-slate-100 rounded-full transition-colors">
               <Bell className="w-5 h-5" />
               <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
             </button>
          </div>
        </header>

        {/* Dynamic Page Content */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8">
           {children}
        </div>
      </main>

    </div>
  );
}
