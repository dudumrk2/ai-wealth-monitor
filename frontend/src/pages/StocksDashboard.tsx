import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
} from 'recharts';
import {
  Plus,
  Upload,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
  MoreVertical,
  Pencil,
  Trash2,
  DollarSign,
  Info,
  AlertCircle,
} from 'lucide-react';
import clsx from 'clsx';
import { auth } from '../lib/firebase';
import DashboardLayout from '../components/layout/DashboardLayout';
import type { StockHolding, ExchangeRate, StockSector } from '../types/stocks';
import { SECTOR_LABELS, SECTOR_COLORS } from '../types/stocks';
import { AdvisorChat } from '../components/dashboard/AdvisorChat';
import ManualStockModal from '../components/stocks/ManualStockModal';

import { API_URL } from '../lib/api';
import { formatCurrency } from '../utils/format';
// ─────────────────────────────────────────────────────────────────
// MOCK DATA REMOVED - using live API
// ─────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────
const formatILS = (val: number) => formatCurrency(val);

const formatPct = (val: number) => {
  const prefix = val > 0 ? '+' : '';
  return `${prefix}${val.toFixed(2)}%`;
};

const toILS       = (h: StockHolding, r: number) => h.currency === 'USD' ? h.totalValueOriginal * r : h.totalValueOriginal;
const dailyILS    = (h: StockHolding, r: number) => h.currency === 'USD' ? h.dailyPnlOriginal  * r : h.dailyPnlOriginal;
const totalPnlILS = (h: StockHolding, r: number) => h.currency === 'USD' ? h.totalPnlOriginal  * r : h.totalPnlOriginal;

// ─────────────────────────────────────────────────────────────────
// Sorting
// ─────────────────────────────────────────────────────────────────
type SortKey = 'name' | 'symbol' | 'sector' | 'dailyChangePercent' | 'valueILS' | 'dailyPnlILS' | 'totalPnlILS' | 'totalReturnPercent' | 'qty';
type SortDir = 'asc' | 'desc';

function getSortValue(h: StockHolding, key: SortKey, rate: number): number | string {
  switch (key) {
    case 'name':               return h.name;
    case 'symbol':             return h.symbol;
    case 'sector':             return h.sector;
    case 'dailyChangePercent': return h.dailyChangePercent;
    case 'valueILS':           return toILS(h, rate);
    case 'dailyPnlILS':        return dailyILS(h, rate);
    case 'totalPnlILS':        return totalPnlILS(h, rate);
    case 'totalReturnPercent': return h.totalReturnPercent;
    case 'qty':                return h.qty;
    default:                   return 0;
  }
}

// ─────────────────────────────────────────────────────────────────
// COMPONENT
// ─────────────────────────────────────────────────────────────────
const StocksDashboard: React.FC = () => {
  const [fxRate, setFxRate]       = useState<ExchangeRate | null>(null);
  const [fxLoading, setFxLoading] = useState(true);
  const [holdings, setHoldings]   = useState<StockHolding[]>([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [sortKey, setSortKey]     = useState<SortKey>('valueILS');
  const [sortDir, setSortDir]     = useState<SortDir>('desc');
  const [openMenu, setOpenMenu]   = useState<string | null>(null);

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [chartTab, setChartTab] = useState<'sector' | 'geo'>('sector');
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [editingStock, setEditingStock] = useState<StockHolding | null>(null);

  // ── Live Data Fetch ─────────────────────────────────────────────
  const fetchPortfolioData = async (silent = false) => {
    if (!silent) {
      setDataLoading(true);
      setFxLoading(true);
    }
    try {
      const user = auth.currentUser;
      if (!user) return;
      const token = await user.getIdToken();

      // Parallel fetch for portfolio and FX rate
      const [portRes, fxRes] = await Promise.all([
        fetch(`${API_URL}/api/portfolio`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        fetch(`${API_URL}/api/portfolio/fx-rate`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);

      if (portRes.ok) {
        const portData = await portRes.json();
        // Extract stocks array from backend (empty array fallback)
        setHoldings(portData.data?.stocks || portData.stocks || []);
      }

      if (fxRes.ok) {
        const fxData = await fxRes.json();
        setFxRate({ 
           rate: fxData.rate as number, 
           date: fxData.date as string, 
           source: fxData.cached ? 'firestore' : 'api', 
           isFallback: fxData.is_fallback 
        });
      }
    } catch (err) {
      console.error('Error fetching stock data:', err);
      setFxRate({ rate: 3.70, date: new Date().toISOString().slice(0, 10), source: 'fallback', isFallback: true });
    } finally {
      if (!silent) {
         setDataLoading(false);
         setFxLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchPortfolioData();
  }, []);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      const user = auth.currentUser;
      if (!user) return;
      const token = await user.getIdToken();
      
      await fetch(`${API_URL}/api/portfolio/update-prices`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      await fetchPortfolioData(true);
    } catch (err) {
      console.error('Error refreshing prices:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleDeleteStock = async (symbol: string) => {
    if (!window.confirm(`האם אתה בטוח שברצונך למחוק את ${symbol} מהתיק?`)) return;
    try {
      const user = auth.currentUser;
      if (!user) return;
      const token = await user.getIdToken();
      
      const res = await fetch(`${API_URL}/api/portfolio/stock/${symbol}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (res.ok) {
        await fetchPortfolioData(true);
      } else {
        alert('שגיאה במחיקת הנייר');
      }
    } catch (err) {
      console.error('Delete error:', err);
    }
  };

  // Close menu on outside click
  useEffect(() => {
    const handler = () => setOpenMenu(null);
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, []);

  const rate = fxRate?.rate ?? 3.70;

  // ── Portfolio totals ────────────────────────────────────────────
  const totalValueILS  = holdings.reduce((s, h) => s + toILS(h, rate), 0);
  const totalDailyILS  = holdings.reduce((s, h) => s + dailyILS(h, rate), 0);
  const totalPnlILS_val = holdings.reduce((s, h) => s + totalPnlILS(h, rate), 0);

  const dailyChangePct = totalValueILS > 0
    ? (totalDailyILS / (totalValueILS - totalDailyILS)) * 100
    : 0;

  const totalReturnPct = totalValueILS > 0
    ? (totalPnlILS_val / (totalValueILS - totalPnlILS_val)) * 100
    : 0;

  const sectorMap: Partial<Record<StockSector, number>> = {};
  holdings.forEach(h => { sectorMap[h.sector] = (sectorMap[h.sector] ?? 0) + toILS(h, rate); });
  const donutData = (Object.keys(sectorMap) as StockSector[]).map(s => ({
    name: SECTOR_LABELS[s] || s, value: sectorMap[s] ?? 0, color: SECTOR_COLORS[s] || '#94a3b8',
  }));

  // Geographic split
  const geoData = useMemo(() => {
    let usa = 0, israel = 0;
    holdings.forEach(h => {
      if (h.currency === 'USD') usa += toILS(h, rate);
      else israel += toILS(h, rate);
    });
    return [
      { name: 'ארה"ב', value: usa, color: '#f97316' },
      { name: 'ישראל', value: israel, color: '#3b82f6' },
    ].filter(d => d.value > 0);
  }, [holdings, rate]);

  const activeDonut = chartTab === 'sector' ? donutData : geoData;
  const activeTotal2 = activeDonut.reduce((s, d) => s + d.value, 0);

  // ── Sorted holdings ─────────────────────────────────────────────
  const sortedHoldings = useMemo(() => {
    return [...holdings].sort((a, b) => {
      const va = getSortValue(a, sortKey, rate);
      const vb = getSortValue(b, sortKey, rate);
      let cmp = 0;
      if (typeof va === 'number' && typeof vb === 'number') cmp = va - vb;
      else cmp = String(va).localeCompare(String(vb), 'he');
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [sortKey, sortDir, rate, holdings]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  // ─────────────────────────────────────────────────────────────────
  return (
    <DashboardLayout onRefresh={handleRefresh} isRefreshing={isRefreshing}>
      <div className="max-w-7xl mx-auto w-full space-y-5 md:space-y-6" dir="rtl">

        {/* ── Page Header ─────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white">תיק מניות</h1>
            <p className="text-slate-500 dark:text-slate-400 text-sm mt-0.5 italic">ניהול ומעקב תיק ניירות הערך המשפחתי</p>
          </div>
          <div className="grid grid-cols-2 lg:flex lg:flex-wrap items-center gap-2 w-full lg:w-auto">
            <button
              onClick={() => setIsManualModalOpen(true)}
              className="inline-flex items-center justify-center gap-1.5 px-3 lg:px-4 py-2.5 rounded-xl border-2 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold text-[13px] lg:text-sm transition-all group whitespace-nowrap"
            >
              <Plus className="w-4 h-4 text-blue-500 group-hover:scale-110 transition-transform" />
              הוספת נייר
            </button>
            <Link
              to="/settings"
              className="inline-flex items-center justify-center gap-1.5 px-3 lg:px-4 py-2.5 rounded-xl border-2 border-blue-500/40 bg-blue-500/10 hover:bg-blue-500/20 text-blue-600 dark:text-blue-400 font-bold text-[13px] lg:text-sm transition-all hover:border-blue-500/70 hover:shadow-[0_0_20px_rgba(59,130,246,0.15)] group whitespace-nowrap"
            >
              <Upload className="w-4 h-4 group-hover:-translate-y-0.5 transition-transform" />
              העלאת נתונים
            </Link>
          </div>
        </div>

        {/* ── Exchange Rate Badge ─────────────────────────────────── */}
        {!fxLoading && fxRate && (
          <div className={clsx(
            'flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg w-fit',
            fxRate.isFallback
              ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
              : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
          )}>
            {fxRate.isFallback ? <AlertCircle className="w-3.5 h-3.5" /> : <RefreshCw className="w-3.5 h-3.5" />}
            <span>שער המרה: 1$ = ₪{fxRate.rate.toFixed(3)}</span>
            <span className="opacity-60">({fxRate.date})</span>
            {fxRate.isFallback && <span className="opacity-70">— שימוש בשער ברירת מחדל</span>}
          </div>
        )}

        {/* ── Empty State & TOP SECTION ─────────── */}
        {dataLoading ? (
            <div className="flex items-center justify-center min-h-[400px]">
               <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
            </div>
        ) : holdings.length === 0 ? (
            <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-10 text-center flex flex-col items-center justify-center shadow-sm py-20 animate-fade-in-up">
              <div className="w-20 h-20 bg-blue-50 dark:bg-blue-900/30 rounded-full flex items-center justify-center mb-6">
                <TrendingUp className="w-10 h-10 text-blue-500" />
              </div>
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-3">אין נתונים בתיק המניות</h2>
              <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto mb-8 leading-relaxed">
                תיק המניות שלך ריק כרגע. כדי להתחיל, עליך לייצא את תיק המניות מהברוקר שלך כקובץ Excel או CSV ולהעלות אותו לכאן.
              </p>
              <Link
                to="/settings"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold transition-all shadow-lg hover:shadow-blue-500/25"
              >
                <Upload className="w-5 h-5" />
                העלאת נתוני ברוקר
              </Link>
            </div>
        ) : (
          <div className="space-y-6 md:space-y-8 animate-fade-in-up">
            {/* Top Section - 3 Columns Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
              
              {/* Right Column: AI Stock Advisor (Order 4 on mobile, Col 1 on LG Row 1) */}
              <div className="relative h-[400px] lg:h-full min-h-[350px] lg:min-h-[600px] order-4 lg:order-3">
                <div className="h-full lg:absolute lg:inset-0">
                  <AdvisorChat />
                </div>
              </div>

              {/* Center Column: Asset Allocation Donut (Hidden on mobile) */}
              <div className="hidden lg:flex bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-5 flex-col h-full min-h-[460px] transition-all hover:border-slate-300 dark:hover:border-slate-700 order-2">
            {/* Tab pills */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-xl p-1">
                <button
                  id="stocks-chart-tab-sector"
                  onClick={() => setChartTab('sector')}
                  className={clsx(
                    'px-3 py-1.5 text-xs font-bold rounded-lg transition-all duration-200',
                    chartTab === 'sector'
                      ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
                      : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
                  )}
                >
                  פיזור מגזרי
                </button>
                <button
                  id="stocks-chart-tab-geo"
                  onClick={() => setChartTab('geo')}
                  className={clsx(
                    'px-3 py-1.5 text-xs font-bold rounded-lg transition-all duration-200',
                    chartTab === 'geo'
                      ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
                      : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300'
                  )}
                >
                  פיזור גיאוגרפי
                </button>
              </div>
              <Info className="w-3.5 h-3.5 text-slate-400" />
            </div>

            {/* Donut */}
            <div className="flex-1 relative min-h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={activeDonut.length > 0 ? activeDonut : [{ name: '', value: 1, color: '#e2e8f0' }]}
                    cx="50%" cy="50%"
                    innerRadius="52%" outerRadius="72%"
                    paddingAngle={activeDonut.length > 1 ? 3 : 0}
                    dataKey="value"
                    stroke="none"
                    animationBegin={0}
                    animationDuration={900}
                    animationEasing="ease-out"
                  >
                    {activeDonut.map((entry, i) => (
                      <Cell key={i} fill={entry.color} className="hover:opacity-80 cursor-pointer transition-opacity" />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(15,23,42,0.95)', borderColor: 'rgba(51,65,85,0.5)',
                      borderRadius: '0.75rem', color: '#f8fafc', backdropFilter: 'blur(8px)',
                      fontSize: '12px', fontWeight: 700, direction: 'rtl',
                    }}
                    formatter={(value: any, name: any) => [
                      `${formatILS(value)} (${activeTotal2 > 0 ? ((value / activeTotal2) * 100).toFixed(1) : 0}%)`, name,
                    ]}
                  />
                </PieChart>
              </ResponsiveContainer>
              {/* Center label */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <p className="text-slate-400 text-[10px] font-bold mb-0.5">סה"כ</p>
                <p className="text-slate-900 dark:text-white text-lg font-black">
                  {totalValueILS > 1_000_000
                    ? `₪${(totalValueILS / 1_000_000).toFixed(2)}M`
                    : formatILS(totalValueILS)}
                </p>
              </div>
            </div>

            {/* Custom legend rows */}
            <div className="mt-3 space-y-1.5">
              {activeDonut.map((item) => {
                const pct = activeTotal2 > 0 ? ((item.value / activeTotal2) * 100).toFixed(1) : '0';
                return (
                  <div key={item.name} className="flex items-center gap-2 text-xs">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                    <span className="text-slate-600 dark:text-slate-400 font-medium flex-1 truncate">{item.name}</span>
                    <span className="font-bold text-slate-900 dark:text-slate-100">{formatILS(item.value)}</span>
                    <span className="text-slate-400 font-bold w-12 text-left">{pct}%</span>
                  </div>
                );
              })}
            </div>
          </div>

              {/* Top Row: Summary Cards (Order 1 on mobile, Col 1 on LG Row 1) */}
              <div className="grid grid-cols-3 lg:flex lg:flex-col gap-2 lg:gap-4 h-full w-full order-1 lg:order-1">
                {fxLoading ? (
                  <>
                    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 h-[60px] lg:h-[120px] animate-pulse flex-1" />
                    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 h-[60px] lg:h-[120px] animate-pulse flex-1" />
                    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 h-[60px] lg:h-[120px] animate-pulse flex-1" />
                  </>
                ) : (
                  <>
                    {/* Card 1 — Total Value */}
                    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-2 lg:p-5 shadow-sm hover:border-blue-500/30 lg:hover:-translate-y-0.5 transition-all group flex-1">
                      <div className="flex items-center justify-between mb-0.5 lg:mb-2">
                        <p className="text-slate-500 dark:text-slate-400 text-[10px] lg:text-xs font-bold uppercase tracking-wider">שווי פדיון</p>
                        <div className="hidden lg:flex w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 items-center justify-center group-hover:scale-110 transition-transform">
                          <DollarSign className="w-4 h-4 text-blue-500" />
                        </div>
                      </div>
                      <p className="text-[13px] sm:text-base lg:text-3xl font-black text-slate-900 dark:text-white leading-tight">{formatILS(totalValueILS)}</p>
                      <p className="hidden lg:block text-xs text-slate-400 mt-1">{holdings.length} ניירות ערך</p>
                    </div>

                    {/* Card 2 — Daily Change */}
                    <div className={clsx(
                      'bg-white dark:bg-slate-900 rounded-2xl border p-2 lg:p-5 shadow-sm lg:hover:-translate-y-0.5 transition-all group flex-1',
                      totalDailyILS >= 0 ? 'border-slate-200 dark:border-slate-800 hover:border-emerald-500/30' : 'border-slate-200 dark:border-slate-800 hover:border-red-500/30'
                    )}>
                      <div className="flex items-center justify-between mb-0.5 lg:mb-2">
                        <p className="text-slate-500 dark:text-slate-400 text-[10px] lg:text-xs font-bold uppercase tracking-wider">שינוי יומי</p>
                        <div className={clsx(
                          'hidden lg:flex w-9 h-9 rounded-xl items-center justify-center group-hover:scale-110 transition-transform',
                          totalDailyILS >= 0 ? 'bg-gradient-to-br from-emerald-500/20 to-teal-500/20' : 'bg-gradient-to-br from-red-500/20 to-rose-500/20'
                        )}>
                          {totalDailyILS >= 0
                            ? <TrendingUp className="w-4 h-4 text-emerald-500" />
                            : <TrendingDown className="w-4 h-4 text-red-500" />}
                        </div>
                      </div>
                      <div className="flex flex-col lg:items-baseline lg:gap-2 leading-tight">
                        <p className={clsx('text-[13px] sm:text-base lg:text-3xl font-black', totalDailyILS >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400')}>
                          {totalDailyILS >= 0 ? '+' : ''}{formatILS(totalDailyILS)}
                        </p>
                        <span className={clsx('text-[9px] lg:text-sm font-bold', dailyChangePct >= 0 ? 'text-emerald-500' : 'text-red-400')}>
                          ({formatPct(dailyChangePct)})
                        </span>
                      </div>
                    </div>

                    {/* Card 3 — Total Summary */}
                    <div className={clsx(
                      'bg-white dark:bg-slate-900 rounded-2xl border p-2 lg:p-5 shadow-sm lg:hover:-translate-y-0.5 transition-all group flex-1',
                      totalPnlILS_val >= 0 ? 'border-slate-200 dark:border-slate-800 hover:border-violet-500/30' : 'border-slate-200 dark:border-slate-800 hover:border-red-500/30'
                    )}>
                      <div className="flex items-center justify-between mb-0.5 lg:mb-2">
                        <p className="text-slate-500 dark:text-slate-400 text-[10px] lg:text-xs font-bold uppercase tracking-wider">סנ"כ רווח</p>
                        <div className={clsx(
                          'hidden lg:flex w-9 h-9 rounded-xl items-center justify-center group-hover:scale-110 transition-transform',
                          totalPnlILS_val >= 0 ? 'bg-gradient-to-br from-violet-500/20 to-purple-500/20' : 'bg-gradient-to-br from-red-500/20 to-rose-500/20'
                        )}>
                          {totalPnlILS_val >= 0
                            ? <TrendingUp className="w-4 h-4 text-violet-500" />
                            : <TrendingDown className="w-4 h-4 text-red-500" />}
                        </div>
                      </div>
                      <div className="flex flex-col lg:items-baseline lg:gap-2 leading-tight">
                        <p className={clsx('text-[13px] sm:text-base lg:text-3xl font-black', totalPnlILS_val >= 0 ? 'text-violet-600 dark:text-violet-400' : 'text-red-500 dark:text-red-400')}>
                          {totalPnlILS_val >= 0 ? '+' : ''}{formatILS(totalPnlILS_val)}
                        </p>
                        <span className={clsx('text-[9px] lg:text-sm font-bold', totalReturnPct >= 0 ? 'text-violet-500' : 'text-red-400')}>
                          ({formatPct(totalReturnPct)})
                        </span>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Middle Section: Full Width Sortable Table (Order 2 on mobile, Span 3 on LG Row 2) */}
              <div className="order-2 lg:order-4 lg:col-span-3 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden mb-2 lg:mb-0">
                <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-800">
                  <h2 className="font-bold text-slate-900 dark:text-slate-100 text-base">אחזקות התיק</h2>
                  <span className="text-xs text-slate-400 font-semibold">{holdings.length} ניירות ערך</span>
                </div>

                {/* Desktop Table */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-800">
                        <SortableTh label="שם / סימבול"    sortKey="name"               current={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableTh label="כמות"           sortKey="qty"                current={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableTh label="שינוי יומי %"   sortKey="dailyChangePercent" current={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableTh label="שווי (₪)"       sortKey="valueILS"           current={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableTh label="רווח/הפסד יומי" sortKey="dailyPnlILS"        current={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableTh label="רווח/הפסד כולל" sortKey="totalPnlILS"        current={sortKey} dir={sortDir} onSort={handleSort} />
                        <SortableTh label="תשואה %"        sortKey="totalReturnPercent" current={sortKey} dir={sortDir} onSort={handleSort} />
                        <th className="px-4 py-3 text-right text-xs font-bold text-slate-400 uppercase tracking-wider whitespace-nowrap w-[60px]">
                          פעולות
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {sortedHoldings.map((h) => {
                        const vILS  = toILS(h, rate);
                        const dILS  = dailyILS(h, rate);
                        const pILS  = totalPnlILS(h, rate);
                        const pct   = (vILS / totalValueILS) * 100;
                        return (
                          <tr key={h.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors">
                            {/* Name / Symbol */}
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-3">
                                <div 
                                  className="w-8 h-8 rounded-lg flex items-center justify-center text-[11px] font-black text-white shrink-0" 
                                  style={{ backgroundColor: (SECTOR_COLORS[h.sector] || '#94a3b8') + 'cc' }}
                                >
                                  {h.sector === 'cash' ? <DollarSign className="w-4 h-4" /> : h.symbol.slice(0, 2)}
                                </div>
                                <div>
                                  <div className="flex items-center gap-2">
                                    <p className="font-bold text-slate-900 dark:text-slate-100 text-[13px] leading-tight">{h.name}</p>
                                    {h.source === 'manual' && (
                                      <span className="bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 text-[9px] font-black px-1.5 py-0.5 rounded border border-blue-100 dark:border-blue-800 uppercase tracking-tighter">ידני</span>
                                    )}
                                  </div>
                                  <p className="text-slate-400 text-[11px] font-mono">{h.symbol} · {h.currency}</p>
                                </div>
                              </div>
                            </td>
                            {/* Quantity */}
                            <td className="px-4 py-3">
                              <p className="font-medium text-slate-600 dark:text-slate-300">{(h.qty ?? h.shares ?? 0).toLocaleString()}</p>
                            </td>
                            {/* Daily % */}
                            <td className="px-4 py-3">
                              <span className={clsx(
                                'inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-bold',
                                h.dailyChangePercent >= 0 
                                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' 
                                  : 'bg-red-500/10 text-red-600 dark:text-red-400'
                              )}>
                                {h.dailyChangePercent >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                {formatPct(h.dailyChangePercent)}
                              </span>
                            </td>
                            {/* Value ILS */}
                            <td className="px-4 py-3">
                              <p className="font-bold text-slate-900 dark:text-slate-100 text-[13px]">{formatILS(vILS)}</p>
                              <div className="mt-1 h-1 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden w-16">
                                <div className="h-full rounded-full" style={{ width: `${Math.min(pct || 0, 100)}%`, backgroundColor: SECTOR_COLORS[h.sector] || '#94a3b8' }} />
                              </div>
                            </td>
                            {/* Daily P&L ILS */}
                            <td className="px-4 py-3">
                              <span className={clsx('font-bold text-[13px]', dILS >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400')}>
                                {dILS >= 0 ? '+' : ''}{formatILS(dILS)}
                              </span>
                            </td>
                            {/* Total P&L ILS */}
                            <td className="px-4 py-3">
                              <span className={clsx('font-bold text-[13px]', pILS >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400')}>
                                {pILS >= 0 ? '+' : ''}{formatILS(pILS)}
                              </span>
                            </td>
                            {/* Total Return % */}
                            <td className="px-4 py-3">
                              <span className={clsx('text-xs font-bold', h.totalReturnPercent >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-400')}>
                                {formatPct(h.totalReturnPercent)}
                              </span>
                            </td>
                            {/* Actions */}
                            <td className="px-4 py-3">
                              <div className="relative" onClick={e => e.stopPropagation()}>
                                <button 
                                  onClick={() => setOpenMenu(openMenu === h.id ? null : h.id)}
                                  className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                                >
                                  <MoreVertical className="w-4 h-4" />
                                </button>
                                {openMenu === h.id && (
                                  <div className="absolute left-0 top-full mt-1 w-36 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl z-50 overflow-hidden py-1">
                                    <button 
                                      onClick={() => {
                                        setEditingStock(h);
                                        setIsManualModalOpen(true);
                                        setOpenMenu(null);
                                      }}
                                      className="w-full text-right flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                                    >
                                      <Pencil className="w-3.5 h-3.5 text-blue-500" />
                                      עדכון
                                    </button>
                                    <button 
                                      onClick={() => handleDeleteStock(h.symbol)}
                                      className="w-full text-right flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                                    >
                                      <Trash2 className="w-3.5 h-3.5" />
                                      מחיקה
                                    </button>
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Mobile Cards */}
                <div className="md:hidden divide-y divide-slate-100 dark:divide-slate-800">
                  {sortedHoldings.map((h) => {
                    const vILS = toILS(h, rate);
                    const dILS = dailyILS(h, rate);
                    return (
                      <div key={h.id} className="px-4 py-3 flex items-center gap-3">
                        <div 
                          className="w-10 h-10 rounded-xl flex items-center justify-center text-xs font-black text-white shrink-0" 
                          style={{ backgroundColor: (SECTOR_COLORS[h.sector] || '#94a3b8') + 'cc' }}
                        >
                          {h.sector === 'cash' ? <DollarSign className="w-5 h-5" /> : h.symbol.slice(0, 2)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-900 dark:text-slate-100 text-sm truncate">{h.name}</span>
                            <span className={clsx(
                              'text-[10px] font-bold px-1.5 py-0.5 rounded-md shrink-0',
                              h.dailyChangePercent >= 0 ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : 'bg-red-500/10 text-red-500 dark:text-red-400'
                            )}>
                              {formatPct(h.dailyChangePercent)}
                            </span>
                          </div>
                          <p className="text-slate-400 text-xs font-mono">{h.sector === 'cash' ? 'מזומן' : h.symbol} · {(h.qty ?? h.shares ?? 0).toLocaleString()} {h.sector === 'cash' ? 'יחידות מטבע' : 'יחידות'}</p>
                        </div>
                        <div className="text-left shrink-0">
                          <p className="font-bold text-slate-900 dark:text-slate-100 text-sm">{formatILS(vILS)}</p>
                          <p className={clsx('text-xs font-bold', dILS >= 0 ? 'text-emerald-500' : 'text-red-400')}>
                            {dILS >= 0 ? '+' : ''}{formatILS(dILS)}
                          </p>
                        </div>
                        {/* Mobile actions */}
                        <div className="relative shrink-0" onClick={e => e.stopPropagation()}>
                          <button 
                            onClick={() => setOpenMenu(openMenu === h.id ? null : h.id)}
                            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 transition-colors"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </button>
                          {openMenu === h.id && (
                            <div className="absolute left-0 top-full mt-1 w-32 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl z-50 overflow-hidden py-1">
                              <button 
                                onClick={() => {
                                  setEditingStock(h);
                                  setIsManualModalOpen(true);
                                  setOpenMenu(null);
                                }}
                                className="w-full text-right flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700"
                              >
                                <Pencil className="w-3.5 h-3.5 text-blue-500" />עדכון
                              </button>
                              <button className="w-full text-right flex items-center gap-2 px-3 py-2 text-sm font-medium text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10">
                                <Trash2 className="w-3.5 h-3.5" />מחיקה
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
            {/* Footer note */}
            <p className="text-[11px] text-slate-400 text-center py-4">
              * נתוני התיק נשמרים בענן; שערי המרה מסונכרנים פעם ב-12 שעות.
            </p>
          </div>
        )}
      </div>
      
      {/* ── Modals ────────────────────────────────────────────── */}
      <ManualStockModal 
        isOpen={isManualModalOpen} 
        onClose={() => {
          setIsManualModalOpen(false);
          setEditingStock(null);
        }}
        onSuccess={() => fetchPortfolioData(true)} 
        initialData={editingStock}
      />


    </DashboardLayout>
  );
};

// ─────────────────────────────────────────────────────────────────
// SortableTh Sub-component
// ─────────────────────────────────────────────────────────────────
interface SortableThProps {
  label: string;
  sortKey: SortKey;
  current: SortKey;
  dir: SortDir;
  onSort: (key: SortKey) => void;
}
const SortableTh: React.FC<SortableThProps> = ({ label, sortKey, current, dir, onSort }) => {
  const isActive = current === sortKey;
  return (
    <th
      onClick={() => onSort(sortKey)}
      className="px-4 py-3 text-right text-xs font-bold text-slate-400 uppercase tracking-wider whitespace-nowrap cursor-pointer select-none hover:text-slate-600 dark:hover:text-slate-200 transition-colors group"
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <span className={clsx('transition-colors', isActive ? 'text-blue-500' : 'text-slate-300 dark:text-slate-600 group-hover:text-slate-400')}>
          {isActive
            ? (dir === 'asc' ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />)
            : <ChevronsUpDown className="w-3.5 h-3.5" />}
        </span>
      </span>
    </th>
  );
};

export default StocksDashboard;
