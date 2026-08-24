import React, { useState, useEffect, useCallback, useMemo } from 'react';
import DashboardLayout from '../components/layout/DashboardLayout';
import {
  RefreshCcw,
  Landmark,
  LineChart,
  Shield,
  Loader2,
  AlertCircle
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { useAuth } from '../context/AuthContext';
import clsx from 'clsx';
import ActionItems from '../components/dashboard/ActionItems';
import type { ActionItem } from '../types/portfolio';
import { CopilotChat } from '../components/CopilotChat';

import { API_URL } from '../lib/api';
import { STORAGE_KEYS } from '../lib/storageKeys';
import { formatCurrency } from '../utils/format';
import { getTranslation } from '../utils/i18n';

/** Per-user cache key — keeps one family's data from ever showing under another's login. */
const portfolioCacheKey = (uid?: string) =>
  uid ? `${STORAGE_KEYS.PORTFOLIO_CACHE}_${uid}` : null;

const DashboardPage: React.FC = () => {
  const { user, isDemo, isEnglishDemo } = useAuth();
  const t = getTranslation(isEnglishDemo);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [portfolioData, setPortfolioData] = useState<any>(null);

  const fetchPortfolio = useCallback(async (options?: { silent?: boolean, refreshMarket?: boolean, refreshAi?: boolean } | boolean) => {
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
      const key = portfolioCacheKey(user?.uid);
      try { if (key) localStorage.setItem(key, JSON.stringify(data)); } catch { /* quota */ }
    } catch (err: any) {
      console.error('Portfolio fetch error:', err);
      if (!silent) setError(isDemo ? 'Failed to load financial data.' : 'אירעה שגיאה בטעינת הנתונים.');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [user, isDemo]);

  useEffect(() => {
    const key = portfolioCacheKey(user?.uid);
    const cached = key ? localStorage.getItem(key) : null;
    if (cached) {
      try {
        setPortfolioData(JSON.parse(cached));
        setLoading(false);
        fetchPortfolio(true);
        return;
      } catch { /* ignore bad cache */ }
    }
    fetchPortfolio();
  }, [fetchPortfolio, user]);

  const totals = useMemo(() => {
    if (!portfolioData || !portfolioData.portfolios) {
      return { pension: 0, market: 0, alternative: 0, insuranceMonthly: 0, total: 0, stockDailyReturnPct: 0 };
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
      
    const stockPortfolioSummary = portfolioData.stock_portfolio_summary || {};
    const stockPortfolioTotal = stockPortfolioSummary.total_value || 0;
    const stockDailyReturnPct = stockPortfolioSummary.daily_return || 0;

    const marketSum = allFunds
      .filter((f: any) => f.category === 'stocks')
      .reduce((s: number, f: any) => s + (f.balance || 0), 0) + stockPortfolioTotal;
      
    const altSum = altInvest.reduce((s: number, a: any) => s + (a.current_value || a.balance || 0), 0) + 
                   allFunds.filter((f: any) => f.category === 'alternative').reduce((s: number, f: any) => s + (f.balance || 0), 0);
    
    const insuranceMonthly = allFunds
      .filter((f: any) => f.category === 'insurance')
      .reduce((s: number, f: any) => s + (f.monthly_deposit || 0), 0);

    const total = p.joint?.total_family_wealth || (pensionSum + marketSum + altSum);

    return {
      pension: pensionSum,
      market: marketSum,
      alternative: altSum,
      insuranceMonthly,
      total: total,
      stockDailyReturnPct
    };
  }, [portfolioData]);

  const [chartTab, setChartTab] = useState<'assets' | 'geo'>('assets');

  const allocationData = useMemo(() => [
    { name: isDemo ? 'Retirement / 401(k)' : 'פנסיה', value: totals.pension, color: '#3b82f6' },
    { name: isDemo ? 'Equities & ETFs' : 'בורסה', value: totals.market, color: '#10b981' },
    { name: isDemo ? 'Alternative Assets' : 'אלטרנטיבי', value: totals.alternative, color: '#8b5cf6' },
  ].filter(item => item.value > 0), [totals, isDemo]);

  const geoData = useMemo(() => {
    const stocks: any[] = portfolioData?.stocks || [];
    const fxRate = portfolioData?.fx_rate || 3.70;
    let usa = 0, local = 0;
    for (const s of stocks) {
      const val = (s.totalValueOriginal || 0) * (s.currency === 'USD' ? (isEnglishDemo ? 1 : fxRate) : 1);
      if (s.currency === 'USD') usa += val;
      else local += val;
    }
    local += totals.pension + totals.alternative;
    const total = usa + local;
    return total > 0 ? [
      { name: isEnglishDemo ? 'United States' : 'ארה"ב', value: usa, color: '#f97316' },
      { name: isEnglishDemo ? 'Global Markets' : 'ישראל', value: local, color: '#3b82f6' },
    ] : [];
  }, [portfolioData, totals, isEnglishDemo]);

  const activeChartData = chartTab === 'assets' ? allocationData : geoData;
  const activeTotal   = activeChartData.reduce((s, d) => s + d.value, 0);
  const chartData = activeChartData.length > 0 ? activeChartData : [{ name: t.dashboard.noData, value: 1, color: '#e2e8f0' }];

  if (loading) {
    return (
      <DashboardLayout>
        <div className="h-[70vh] flex flex-col items-center justify-center gap-4">
          <Loader2 className="w-12 h-12 text-blue-600 animate-spin" />
          <p className="text-slate-500 font-bold">{t.dashboard.loading}</p>
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
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">{t.dashboard.errorTitle}</h2>
          <p className="text-slate-500 dark:text-slate-400">{error}</p>
          <button onClick={() => fetchPortfolio()} className="mt-4 flex items-center gap-2 bg-slate-900 dark:bg-slate-800 text-white px-6 py-2.5 rounded-xl font-bold hover:bg-slate-800 transition-colors">
            <RefreshCcw className="w-4 h-4" /> {t.dashboard.retry}
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
          <h1 className="text-2xl md:text-4xl font-bold text-slate-900 dark:text-white mb-1 md:mb-2">{t.dashboard.title}</h1>
          <p className="text-slate-500 dark:text-slate-500 text-sm md:text-lg italic">{t.dashboard.subtitle}</p>
        </div>

        {/* Top Section - 3 Columns */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6 lg:min-h-[620px]">

          {/* Summary Cards */}
          <div className="grid grid-cols-2 lg:flex lg:flex-col gap-3 md:gap-4 h-full order-1 lg:order-3">
             <Link to="/pension" className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-3 md:p-5 shadow-sm flex items-center transition-all hover:-translate-y-1 hover:border-blue-500/30 group cursor-pointer flex-1">
              <div className="w-10 h-10 md:w-14 md:h-14 rounded-2xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center text-blue-400 shrink-0 shadow-inner group-hover:scale-110 transition-transform duration-300 mx-2">
                <Landmark className="w-5 h-5 md:w-7 md:h-7" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-slate-500 text-[10px] md:text-sm font-bold mb-0.5 md:mb-1">{t.dashboard.pensionBalance}</p>
                <h3 className="text-base md:text-2xl font-bold text-slate-900 dark:text-slate-100 truncate">{formatCurrency(totals.pension)}</h3>
              </div>
            </Link>

            <Link to="/stocks" className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-3 md:p-5 shadow-sm flex items-center transition-all hover:-translate-y-1 hover:border-emerald-500/30 group cursor-pointer flex-1">
              <div className="w-10 h-10 md:w-14 md:h-14 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center text-emerald-400 shrink-0 shadow-inner group-hover:scale-110 transition-transform duration-300 mx-2">
                <LineChart className="w-5 h-5 md:w-7 md:h-7" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-0.5 md:mb-1">
                  <p className="text-slate-500 text-[10px] md:text-sm font-bold">{t.dashboard.stocksPortfolio}</p>
                  {totals.stockDailyReturnPct !== 0 && (
                    <span className={clsx(
                      "text-[9px] md:text-xs font-bold px-1 md:px-1.5 py-0.5 rounded-full flex items-center gap-0.5",
                      totals.stockDailyReturnPct > 0 ? "bg-emerald-500/10 text-emerald-500" : "bg-red-500/10 text-red-500"
                    )}>
                      {totals.stockDailyReturnPct > 0 ? '+' : ''}{totals.stockDailyReturnPct.toFixed(2)}%
                    </span>
                  )}
                </div>
                <h3 className="text-base md:text-2xl font-bold text-slate-900 dark:text-slate-100 truncate">{formatCurrency(totals.market)}</h3>
              </div>
            </Link>

            <Link to="/insurance" className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-3 md:p-5 shadow-sm flex items-center transition-all hover:-translate-y-1 hover:border-violet-500/30 group cursor-pointer flex-1">
              <div className="w-10 h-10 md:w-14 md:h-14 rounded-2xl bg-gradient-to-br from-violet-500/20 to-purple-500/20 flex items-center justify-center text-violet-400 shrink-0 shadow-inner group-hover:scale-110 transition-transform duration-300 mx-2">
                <Shield className="w-5 h-5 md:w-7 md:h-7" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-slate-500 text-[10px] md:text-sm font-bold mb-0.5 md:mb-1">{t.dashboard.insuranceMonthly}</p>
                <h3 className="text-base md:text-2xl font-bold text-slate-900 dark:text-slate-100 truncate">
                  {formatCurrency(totals.insuranceMonthly)} <span className="text-[10px] md:text-xs font-normal text-slate-500">{isDemo ? '/ mo' : '/ חודש'}</span>
                </h3>
              </div>
            </Link>
          </div>

          {/* Center Column: Asset Allocation */}
          <div className="hidden lg:flex bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-4 md:p-6 flex-col relative h-full transition-all hover:border-slate-300 dark:hover:border-slate-700 order-2">
            {/* Tab Header */}
            <div className="flex items-center gap-1 mb-4 bg-slate-100 dark:bg-slate-800 rounded-xl p-1 self-start">
              <button
                id="chart-tab-assets"
                onClick={() => setChartTab('assets')}
                className={clsx(
                  "px-3 py-1.5 text-xs font-bold rounded-lg transition-all duration-200",
                  chartTab === 'assets'
                    ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm"
                    : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
                )}
              >
                {t.dashboard.assetAllocation}
              </button>
              <button
                id="chart-tab-geo"
                onClick={() => setChartTab('geo')}
                className={clsx(
                  "px-3 py-1.5 text-xs font-bold rounded-lg transition-all duration-200",
                  chartTab === 'geo'
                    ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm"
                    : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
                )}
              >
                {t.dashboard.geoAllocation}
              </button>
            </div>

            {/* Donut Chart */}
            <div className="flex-1 relative min-h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    innerRadius="55%"
                    outerRadius="75%"
                    paddingAngle={activeChartData.length > 1 ? 3 : 0}
                    dataKey="value"
                    stroke="none"
                    animationBegin={0}
                    animationDuration={900}
                    animationEasing="ease-out"
                  >
                    {chartData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.color}
                        className="hover:opacity-85 transition-opacity cursor-pointer"
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(15, 23, 42, 0.95)',
                      borderColor: 'rgba(51, 65, 85, 0.5)',
                      borderRadius: '0.75rem',
                      color: '#f8fafc',
                      backdropFilter: 'blur(8px)',
                      fontSize: '12px',
                      fontWeight: 700,
                    }}
                    formatter={(value: any, name: any) => [
                      `${formatCurrency(value)} (${activeTotal > 0 ? ((value / activeTotal) * 100).toFixed(1) : 0}%)`,
                      name
                    ]}
                  />
                </PieChart>
              </ResponsiveContainer>

              {/* Center Label */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <div className="text-slate-400 text-[10px] font-bold mb-0.5">{isDemo ? 'TOTAL' : 'סה"כ'}</div>
                <div className="text-lg md:text-xl font-bold text-slate-900 dark:text-white leading-tight">
                  {activeTotal > 1000000
                    ? (isDemo ? `$${(activeTotal / 1000000).toFixed(2)}M` : `₪${(activeTotal / 1000000).toFixed(1)}M`)
                    : formatCurrency(activeTotal)}
                </div>
              </div>
            </div>

            {/* Legend rows */}
            <div className="mt-3 space-y-2">
              {activeChartData.map((item) => {
                const pct = activeTotal > 0 ? ((item.value / activeTotal) * 100).toFixed(1) : '0';
                return (
                  <div key={item.name} className="flex items-center gap-2 text-xs">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                    <span className="text-slate-600 dark:text-slate-400 font-medium flex-1">{item.name}</span>
                    <span className="font-bold text-slate-900 dark:text-slate-100">{formatCurrency(item.value)}</span>
                    <span className="text-slate-400 font-bold w-12 text-left">{pct}%</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* AI Chat */}
          <div className="relative h-[400px] lg:h-full min-h-[350px] lg:min-h-0 w-full order-3 lg:order-1">
            <div className="h-full lg:absolute lg:inset-0">
              <CopilotChat />
            </div>
          </div>

        </div>

        {/* Bottom Section - Alerts & Actions */}
        <div className="pt-2 md:pt-4">
          <ActionItems 
            items={portfolioData?.action_items as ActionItem[]} 
            title={t.actionItems.title}
            onRefreshAI={() => fetchPortfolio({ refreshAi: true })}
            member1Name={portfolioData?.portfolios?.user?.ownerName || (isDemo ? "David" : "משתמש")}
            member2Name={portfolioData?.portfolios?.spouse?.ownerName || (isDemo ? "Sarah" : "בן/בת זוג")}
          />
        </div>
      </div>
    </DashboardLayout>
  );
};

export default DashboardPage;
