import React, { useState, useEffect, useCallback, useMemo } from 'react';
import DashboardLayout from '../components/layout/DashboardLayout';
import {
  RefreshCcw,
  Settings,
  Bell,
  User,
  Bot,
  Send,
  Landmark,
  LineChart,
  Shield,
  ShieldAlert,
  Wallet,
  ChevronLeft,
  HandCoins,
  Loader2,
  AlertCircle
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { useAuth } from '../context/AuthContext';
import clsx from 'clsx';
import ActionItems from '../components/dashboard/ActionItems';
import type { ActionItem } from '../types/portfolio';
import { CopilotChat } from '../components/CopilotChat';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const formatCurrency = (val: number) => 
  new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 }).format(val);

const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [portfolioData, setPortfolioData] = useState<any>(null);

  const fetchPortfolio = useCallback(async (options?: { silent?: boolean, refreshMarket?: boolean, refreshAi?: boolean } | boolean) => {
    // Support both the old boolean signature and the new options object
    const silent = typeof options === 'boolean' ? options : options?.silent ?? false;
    const refreshMarket = typeof options === 'object' ? options.refreshMarket ?? false : false;
    const refreshAi = typeof options === 'object' ? options.refreshAi ?? false : false;

    try {
      if (!silent) setLoading(true);
      setError(null);
      const idToken = await user?.getIdToken();
      if (!idToken) return;

      const params = new URLSearchParams();
      if (refreshMarket) params.append('refresh_market', 'true');
      if (refreshAi) params.append('refresh_ai', 'true');
      const query = params.toString() ? `?${params.toString()}` : '';

      const response = await fetch(`${API_URL}/api/portfolio${query}`, {
        headers: { 'Authorization': `Bearer ${idToken}` }
      });
      if (!response.ok) throw new Error('Failed to fetch portfolio');
      const data = await response.json();
      setPortfolioData(data);
    } catch (err: any) {
      console.error('Portfolio fetch error:', err);
      if (!silent) setError('אירעה שגיאה בטעינת הנתונים.');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchPortfolio();
  }, [fetchPortfolio]);

  const totals = useMemo(() => {
    if (!portfolioData || !portfolioData.portfolios) {
      return { pension: 0, market: 0, alternative: 0, insuranceMonthly: 0, total: 0 };
    }
    
    const p = portfolioData.portfolios;
    const userFunds = p.user?.funds || [];
    const spouseFunds = p.spouse?.funds || [];
    const jointStocks = p.joint?.stock_investments || [];
    const altInvest = p.user?.alternative_investments || [];
    
    const allFunds = [...userFunds, ...spouseFunds, ...jointStocks];
    
    const pensionCats = ['pension', 'managers', 'study', 'provident', 'investment_provident'];
    
    const pensionSum = allFunds
      .filter((f: any) => pensionCats.includes(f.category))
      .reduce((s: number, f: any) => s + (f.balance || 0), 0);
      
    const marketSum = allFunds
      .filter((f: any) => f.category === 'stocks')
      .reduce((s: number, f: any) => s + (f.balance || 0), 0);
      
    const altSum = altInvest.reduce((s: number, a: any) => s + (a.current_value || a.balance || 0), 0) + 
                   allFunds.filter((f: any) => f.category === 'alternative').reduce((s: number, f: any) => s + (f.balance || 0), 0);
    
    // Monthly insurance/pension deposits
    const insuranceMonthly = allFunds
      .filter((f: any) => f.category === 'insurance')
      .reduce((s: number, f: any) => s + (f.monthly_deposit || 0), 0);

    // Use backend total if available, otherwise sum locally
    const total = p.joint?.total_family_wealth || (pensionSum + marketSum + altSum);

    return {
      pension: pensionSum,
      market: marketSum,
      alternative: altSum,
      insuranceMonthly,
      total: total
    };
  }, [portfolioData]);

  const allocationData = useMemo(() => [
    { name: 'פנסיה', value: totals.pension, color: '#3b82f6' },
    { name: 'בורסה', value: totals.market, color: '#10b981' },
    { name: 'אלטרנטיבי', value: totals.alternative, color: '#8b5cf6' },
  ].filter(item => item.value > 0), [totals]);

  // If no values, use a placeholder for the pie
  const chartData = allocationData.length > 0 ? allocationData : [{ name: 'אין נתונים', value: 1, color: '#e2e8f0' }];

  if (loading) {
    return (
      <DashboardLayout>
        <div className="h-[70vh] flex flex-col items-center justify-center gap-4">
          <Loader2 className="w-12 h-12 text-blue-600 animate-spin" />
          <p className="text-slate-500 font-bold">טוען נתונים פיננסיים...</p>
        </div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="h-[70vh] flex flex-col items-center justify-center gap-4 max-w-md mx-auto text-center">
          <div className="bg-red-50 dark:bg-red-900/20 p-4 rounded-full">
            <AlertCircle className="w-10 h-10 text-red-500" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">אופס, משהו השתבש</h2>
          <p className="text-slate-500 dark:text-slate-400">{error}</p>
          <button onClick={() => fetchPortfolio()} className="mt-4 flex items-center gap-2 bg-slate-900 dark:bg-slate-800 text-white px-6 py-2.5 rounded-xl font-bold hover:bg-slate-800 transition-colors">
            <RefreshCcw className="w-4 h-4" /> נסה שנית
          </button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout onRefresh={() => fetchPortfolio(true)} isRefreshing={false}>
      <div className="max-w-7xl mx-auto w-full space-y-4 md:space-y-8">
        
        {/* Title Area */}
        <div className="animate-fade-in-up">
          <h1 className="text-2xl md:text-4xl font-bold text-slate-900 dark:text-white mb-1 md:mb-2">דשבורד משפחתי</h1>
          <p className="text-slate-500 dark:text-slate-500 text-sm md:text-lg italic">מרכז הבקרה הפיננסי המאוחד שלכם</p>
        </div>

        {/* Top Section - 3 Columns */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6 min-h-[500px] lg:min-h-[620px]">
          {/* Right Column: AI Chat */}
          <div className="relative min-h-[450px] lg:min-h-0 h-full w-full">
            <div className="absolute inset-0">
              <CopilotChat />
            </div>
          </div>

          {/* Center Column: Asset Allocation */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-4 md:p-6 flex flex-col items-center relative h-full transition-all hover:border-slate-300 dark:hover:border-slate-700">
            <h2 className="font-semibold text-lg md:text-xl w-full mb-2 md:mb-4 text-slate-900 dark:text-slate-100 flex items-center gap-2">פיזור נכסים</h2>
            <div className="flex-1 w-full relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    innerRadius={70}
                    outerRadius={100}
                    paddingAngle={allocationData.length > 1 ? 5 : 0}
                    dataKey="value"
                    stroke="none"
                    animationBegin={0}
                    animationDuration={1500}
                    animationEasing="ease-out"
                  >
                    {chartData.map((entry, index) => (
                      <Cell 
                        key={`cell-${index}`} 
                        fill={entry.color} 
                        className="hover:opacity-80 transition-opacity cursor-pointer drop-shadow-md"
                      />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'rgba(15, 23, 42, 0.9)', 
                      borderColor: 'rgba(51, 65, 85, 0.5)', 
                      borderRadius: '0.75rem', 
                      color: '#f8fafc',
                      backdropFilter: 'blur(8px)',
                      boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)'
                    }}
                    itemStyle={{ color: '#f8fafc', fontWeight: 700 }}
                    formatter={(value: number) => [formatCurrency(value), '']}
                  />
                  <Legend 
                    verticalAlign="bottom" 
                    height={40} 
                    iconType="circle"
                    formatter={(value) => <span className="text-slate-600 dark:text-slate-300 ml-2 font-bold text-xs">{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
              {/* Custom Center Text */}
              <div className="absolute top-[45%] left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none pb-2 flex flex-col justify-center items-center drop-shadow-lg">
                <div className="text-slate-500 text-xs md:text-sm font-bold mb-0.5">סה"כ</div>
                <div className="text-xl md:text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-b from-slate-900 to-slate-700 dark:from-white dark:to-slate-300">
                  {totals.total > 1000000 ? `₪${(totals.total/1000000).toFixed(1)}M` : formatCurrency(totals.total)}
                </div>
              </div>
            </div>
          </div>

          {/* Left Column: Summary Cards */}
          <div className="flex flex-col gap-3 md:gap-4 h-full">
             <Link to="/pension" className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-4 md:p-5 shadow-sm flex items-center transition-all hover:-translate-y-1 hover:border-blue-500/30 group cursor-pointer flex-1">
              <div className="w-12 h-12 md:w-14 md:h-14 rounded-2xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center text-blue-400 ml-4 md:ml-5 shrink-0 shadow-inner group-hover:scale-110 transition-transform duration-300">
                <Landmark className="w-6 h-6 md:w-7 md:h-7" />
              </div>
              <div className="flex-1">
                <p className="text-slate-500 text-xs md:text-sm font-bold mb-1">יתרת פנסיה</p>
                <h3 className="text-xl md:text-2xl font-bold text-slate-900 dark:text-slate-100">{formatCurrency(totals.pension)}</h3>
              </div>
            </Link>

            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-4 md:p-5 shadow-sm flex items-center transition-all hover:-translate-y-1 hover:border-emerald-500/30 group flex-1">
              <div className="w-12 h-12 md:w-14 md:h-14 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center text-emerald-400 ml-4 md:ml-5 shrink-0 shadow-inner group-hover:scale-110 transition-transform duration-300">
                <LineChart className="w-6 h-6 md:w-7 md:h-7" />
              </div>
              <div className="flex-1">
                <p className="text-slate-500 text-xs md:text-sm font-bold mb-1">תיק בורסה</p>
                <h3 className="text-xl md:text-2xl font-bold text-slate-900 dark:text-slate-100">{formatCurrency(totals.market)}</h3>
              </div>
            </div>

            <Link to="/alternative" className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-4 md:p-5 shadow-sm flex items-center transition-all hover:-translate-y-1 hover:border-indigo-500/30 group cursor-pointer flex-1">
              <div className="w-12 h-12 md:w-14 md:h-14 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-blue-500/20 flex items-center justify-center text-indigo-400 ml-4 md:ml-5 shrink-0 shadow-inner group-hover:scale-110 transition-transform duration-300">
                <HandCoins className="w-6 h-6 md:w-7 md:h-7" />
              </div>
              <div className="flex-1">
                <p className="text-slate-500 text-xs md:text-sm font-bold mb-1">השקעות אלטרנטיביות</p>
                <h3 className="text-xl md:text-2xl font-bold text-slate-900 dark:text-slate-100">{formatCurrency(totals.alternative)}</h3>
              </div>
            </Link>

            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-4 md:p-5 shadow-sm flex items-center transition-all hover:-translate-y-1 hover:border-violet-500/30 group flex-1">
              <div className="w-12 h-12 md:w-14 md:h-14 rounded-2xl bg-gradient-to-br from-violet-500/20 to-purple-500/20 flex items-center justify-center text-violet-400 ml-4 md:ml-5 shrink-0 shadow-inner group-hover:scale-110 transition-transform duration-300">
                <Shield className="w-6 h-6 md:w-7 md:h-7" />
              </div>
              <div className="flex-1">
                <p className="text-slate-500 text-xs md:text-sm font-bold mb-1">ביטוחים</p>
                <h3 className="text-xl md:text-2xl font-bold text-slate-900 dark:text-slate-100">{formatCurrency(totals.insuranceMonthly)} <span className="text-xs font-normal text-slate-500">/ חודש</span></h3>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Section - Alerts & Actions */}
        <div className="pt-2 md:pt-4">
          <ActionItems 
            items={portfolioData?.action_items as ActionItem[]} 
            title="התראות פנסיה וביטוח"
            onRefreshAI={() => fetchPortfolio({ refreshAi: true })}
          />
        </div>
      </div>

      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background-color: #334155;
          border-radius: 10px;
        }
        @keyframes fade-in-up {
          0% { opacity: 0; transform: translateY(10px); }
          100% { opacity: 1; transform: translateY(0); }
        }
        @keyframes fade-in-right {
          0% { opacity: 0; transform: translateX(10px); }
          100% { opacity: 1; transform: translateX(0); }
        }
        @keyframes fade-in-left {
          0% { opacity: 0; transform: translateX(-10px); }
          100% { opacity: 1; transform: translateX(0); }
        }
        @keyframes swing {
          20% { transform: rotate(15deg); }
          40% { transform: rotate(-10deg); }
          60% { transform: rotate(5deg); }
          80% { transform: rotate(-5deg); }
          100% { transform: rotate(0deg); }
        }
        .animate-fade-in-up {
          animation: fade-in-up 0.6s ease-out forwards;
        }
        .animate-fade-in-right {
          animation: fade-in-right 0.5s ease-out forwards;
        }
        .animate-fade-in-left {
          animation: fade-in-left 0.5s ease-out forwards;
        }
        .animate-swing {
          animation: swing 1s ease-in-out;
        }
      `}} />
    </DashboardLayout>
  );
};

export default DashboardPage;
