import { useAuth } from '../context/AuthContext';
import { STORAGE_KEYS } from '../lib/storageKeys';
import { TrendingUp, ShieldCheck, Users, LogIn, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Login() {
  const { signInWithGoogle } = useAuth();
  const navigate = useNavigate();

  // Path 1: returning user — sign in and go to dashboard
  const handleSignIn = async () => {
    try {
      await signInWithGoogle();
      navigate('/dashboard');
    } catch (error) {
      console.error("כשל בכניסה", error);
    }
  };

  // Path 2: new family — sign in and go to onboarding to set up names
  const handleCreateFamily = async () => {
    try {
      // Clear any old family config so onboarding shows fresh
      localStorage.removeItem(STORAGE_KEYS.ONBOARDING_DONE);
      localStorage.removeItem(STORAGE_KEYS.FAMILY_CONFIG);
      await signInWithGoogle();
      navigate('/onboarding');
    } catch (error) {
      console.error("כשל בכניסה", error);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center items-center p-4 relative overflow-hidden">
      {/* Background gradient orbs */}
      <div className="absolute top-[-10%] right-[-10%] w-[55%] h-[55%] bg-blue-600/25 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-[-10%] left-[-10%] w-[55%] h-[55%] bg-emerald-600/20 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[30%] h-[30%] bg-indigo-500/10 rounded-full blur-[100px] pointer-events-none" />

      <div className="max-w-lg w-full relative z-10 space-y-6">

        {/* Logo & Title */}
        <div className="text-center mb-10">
          <div className="bg-gradient-to-br from-blue-500 to-emerald-400 p-5 rounded-3xl inline-flex mb-6 shadow-xl shadow-blue-500/30">
            <TrendingUp className="w-12 h-12 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-white mb-3 tracking-tight">ניטור עושר משפחתי</h1>
          <p className="text-slate-400 text-base">פלטפורמה אוטומטית לניתוח פנסיה ותיק השקעות</p>
        </div>

        {/* Feature pills */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="flex items-center gap-3 text-slate-300 text-sm bg-slate-800/70 backdrop-blur-sm p-3.5 rounded-xl border border-slate-700/40">
            <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
            <span>הצפנה ברמה בנקאית</span>
          </div>
          <div className="flex items-center gap-3 text-slate-300 text-sm bg-slate-800/70 backdrop-blur-sm p-3.5 rounded-xl border border-slate-700/40">
            <TrendingUp className="w-5 h-5 text-blue-400 shrink-0" />
            <span>השוואת תשואות בזמן אמת</span>
          </div>
        </div>

        {/* --- Main CTAs --- */}

        {/* Option A: Create New Family */}
        <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-2xl p-px shadow-2xl shadow-blue-900/50">
          <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-2xl p-6">
            <div className="flex items-start gap-4 mb-5">
              <div className="bg-white/20 p-2.5 rounded-xl">
                <Users className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-white font-bold text-lg leading-tight">יצירת משפחה חדשה</h2>
                <p className="text-blue-200 text-sm mt-1">הגדרה ראשונית של הבית, השמות וחשבונות מורשים</p>
              </div>
            </div>
            <button
              onClick={handleCreateFamily}
              className="w-full flex items-center justify-center gap-3 bg-white hover:bg-blue-50 text-blue-700 py-3.5 px-4 rounded-xl font-bold transition-all transform active:scale-95 shadow-lg"
            >
              <img className="w-5 h-5" src="https://www.svgrepo.com/show/475656/google-color.svg" alt="Google" />
              כניסה עם Google ליצירת משפחה חדשה
            </button>
          </div>
        </div>

        {/* Divider */}
        <div className="flex items-center gap-4">
          <div className="flex-1 h-px bg-slate-700"></div>
          <span className="text-slate-500 text-sm font-medium">או חזרה לחשבון קיים</span>
          <div className="flex-1 h-px bg-slate-700"></div>
        </div>

        {/* Option B: Returning User Login */}
        <button
          onClick={handleSignIn}
          className="w-full flex items-center justify-center gap-3 bg-slate-800/80 hover:bg-slate-800 border border-slate-700/50 text-white py-3.5 px-4 rounded-xl font-semibold transition-all transform active:scale-95 backdrop-blur-sm"
        >
          <LogIn className="w-5 h-5 text-blue-400" />
          כניסה לחשבון משפחה קיים
          <ArrowLeft className="w-4 h-4 opacity-50 mr-auto" />
        </button>

        <p className="text-center text-slate-600 text-xs pt-2">לשימוש בני משפחה מורשים בלבד</p>
      </div>
    </div>
  );
}
