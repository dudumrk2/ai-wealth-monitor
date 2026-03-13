 import React from 'react'; 
import { useAuth } from '../context/AuthContext';
import { TrendingUp, ShieldCheck, Mail } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Login() {
  const { signInWithGoogle } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async () => {
    try {
      await signInWithGoogle();
      navigate('/dashboard');
    } catch (error) {
      console.error("Login Failed", error);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center items-center p-4 relative overflow-hidden">
      {/* Background decoration elements */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-blue-600/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-emerald-600/20 rounded-full blur-[120px] pointer-events-none" />
      
      <div className="max-w-md w-full backdrop-blur-xl bg-slate-800/60 border border-slate-700/50 p-8 rounded-3xl shadow-2xl relative z-10 overflow-hidden group">
        
        {/* Shimmer Effect */}
        <div className="absolute inset-0 -translate-x-full group-hover:animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/5 to-transparent pointer-events-none" />

        <div className="text-center mb-10">
          <div className="bg-gradient-to-br from-blue-500 to-emerald-400 p-4 rounded-2xl inline-flex mb-6 shadow-lg shadow-blue-500/30">
            <TrendingUp className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-3 tracking-tight">AI Wealth Monitor</h1>
          <p className="text-slate-400 text-sm">Automated Family Pension & Portfolio Analytics</p>
        </div>

        <div className="space-y-4 mb-8">
          <div className="flex items-center text-slate-300 gap-3 text-sm bg-slate-800/50 p-3 rounded-lg border border-slate-700/30">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <span>Bank-level Data Encryption</span>
          </div>
          <div className="flex items-center text-slate-300 gap-3 text-sm bg-slate-800/50 p-3 rounded-lg border border-slate-700/30">
            <TrendingUp className="w-5 h-5 text-blue-400" />
            <span>Real-time Competitor Yield Matching</span>
          </div>
        </div>

        <button 
          onClick={handleLogin}
          className="w-full flex items-center justify-center gap-3 bg-white hover:bg-slate-50 text-slate-900 py-3.5 px-4 rounded-xl font-semibold transition-all transform active:scale-95 shadow-lg"
        >
          <img className="w-5 h-5" src="https://www.svgrepo.com/show/475656/google-color.svg" alt="Google" />
          Sign in with Google
        </button>
      </div>

      <div className="mt-8 text-center text-slate-500 text-sm z-10 w-full max-w-md flex items-center justify-center gap-2">
        <Mail className="w-4 h-4" /> Strictly for authorized family members
      </div>
    </div>
  );
}
