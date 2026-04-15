import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
} from 'recharts';
import {
  Upload,
  TrendingUp,
  TrendingDown,
  DollarSign,
  RefreshCw,
  AlertCircle,
  Info,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  MoreVertical,
  Pencil,
  Trash2,
} from 'lucide-react';
import clsx from 'clsx';
import { auth } from '../lib/firebase';
import DashboardLayout from '../components/layout/DashboardLayout';
import type { StockHolding, ExchangeRate, StockSector } from '../types/stocks';
import { SECTOR_LABELS, SECTOR_COLORS } from '../types/stocks';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ─────────────────────────────────────────────────────────────────
// MOCK DATA REMOVED - using live API
// ─────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────
const formatILS = (val: number) =>
  new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 }).format(val);

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

  // ── Live Data Fetch ─────────────────────────────────────────────
  useEffect(() => {
    let isSubscribed = true;

    const fetchData = async () => {
      setDataLoading(true);
      setFxLoading(true);
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

        if (portRes.ok && isSubscribed) {
          const portData = await portRes.json();
          // Extract stocks array from backend (empty array fallback)
          setHoldings(portData.data?.stocks || portData.stocks || []);
        }

        if (fxRes.ok && isSubscribed) {
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
        if (isSubscribed) {
           setFxRate({ rate: 3.70, date: new Date().toISOString().slice(0, 10), source: 'fallback', isFallback: true });
        }
      } finally {
        if (isSubscribed) {
           setDataLoading(false);
           setFxLoading(false);
        }
      }
    };

    fetchData();

    return () => { isSubscribed = false; };
  }, []);

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

  // ── Donut data ──────────────────────────────────────────────────
  const sectorMap: Partial<Record<StockSector, number>> = {};
  holdings.forEach(h => { sectorMap[h.sector] = (sectorMap[h.sector] ?? 0) + toILS(h, rate); });
  const donutData = (Object.keys(sectorMap) as StockSector[]).map(s => ({
    name: SECTOR_LABELS[s] || s, value: sectorMap[s] ?? 0, color: SECTOR_COLORS[s] || '#94a3b8',
  }));

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
    <DashboardLayout>
      <div className="max-w-7xl mx-auto w-full space-y-5 md:space-y-6" dir="rtl">

        {/* ── Page Header ─────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white">תיק מניות</h1>
            <p className="text-slate-500 dark:text-slate-400 text-sm mt-0.5 italic">ניהול ומעקב תיק ניירות הערך המשפחתי</p>
          </div>
          <Link
            to="/settings"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border-2 border-blue-500/40 bg-blue-500/10 hover:bg-blue-500/20 text-blue-600 dark:text-blue-400 font-bold text-sm transition-all hover:border-blue-500/70 hover:shadow-[0_0_20px_rgba(59,130,246,0.15)] group whitespace-nowrap"
          >
            <Upload className="w-4 h-4 group-hover:-translate-y-0.5 transition-transform" />
            העלאת CSV / ניהול נתונים
          </Link>
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
          <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

            {/* Right — Donut Chart */}
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-5 flex flex-col min-h-[340px]">
            <div className="flex items-center gap-2 mb-3">
              <h2 className="font-bold text-slate-900 dark:text-slate-100 text-base">פיזור גיאוגרפי / מגזרי</h2>
              <Info className="w-3.5 h-3.5 text-slate-400 mr-auto" />
            </div>
            <div className="flex-1 relative min-h-[270px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={donutData}
                    cx="50%" cy="44%"
                    innerRadius="50%" outerRadius="70%"
                    paddingAngle={3}
                    dataKey="value"
                    stroke="none"
                    animationBegin={0}
                    animationDuration={1200}
                    animationEasing="ease-out"
                  >
                    {donutData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} className="hover:opacity-80 cursor-pointer transition-opacity" />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(15,23,42,0.93)', borderColor: 'rgba(51,65,85,0.5)',
                      borderRadius: '0.75rem', color: '#f8fafc', backdropFilter: 'blur(8px)', direction: 'rtl',
                    }}
                    formatter={(value: number, name: string) => [
                      `${formatILS(value)} (${((value / totalValueILS) * 100).toFixed(1)}%)`, name,
                    ]}
                  />
                  <Legend
                    verticalAlign="bottom" height={52} iconType="circle" iconSize={8}
                    formatter={(value) => <span className="text-slate-600 dark:text-slate-300 text-xs font-semibold">{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
              {/* Center label */}
              <div className="absolute top-[41%] left-1/2 -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none">
                <p className="text-slate-400 text-[10px] font-bold mb-0.5">סה"כ</p>
                <p className="text-slate-900 dark:text-white text-lg font-black">
                  {totalValueILS > 1_000_000
                    ? `₪${(totalValueILS / 1_000_000).toFixed(2)}M`
                    : formatILS(totalValueILS)}
                </p>
              </div>
            </div>
          </div>

          {/* Left — 3 Summary Cards stacked */}
          <div className="flex flex-col gap-4">

            {/* Card 1 — Total Value */}
            {fxLoading ? (
              <>
                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 h-[100px] animate-pulse flex-1" />
                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 h-[100px] animate-pulse flex-1" />
                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 h-[100px] animate-pulse flex-1" />
              </>
            ) : (
              <>
                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm hover:border-blue-500/30 hover:-translate-y-0.5 transition-all group flex-1">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-slate-500 dark:text-slate-400 text-xs font-bold uppercase tracking-wider">שווי כולל תיק</p>
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center group-hover:scale-110 transition-transform">
                      <DollarSign className="w-4 h-4 text-blue-500" />
                    </div>
                  </div>
                  <p className="text-3xl font-black text-slate-900 dark:text-white">{formatILS(totalValueILS)}</p>
                  <p className="text-xs text-slate-400 mt-1">{holdings.length} ניירות ערך</p>
                </div>

                {/* Card 2 — Daily Change (Amount & %) */}
                <div className={clsx(
                  'bg-white dark:bg-slate-900 rounded-2xl border p-5 shadow-sm hover:-translate-y-0.5 transition-all group flex-1',
                  totalDailyILS >= 0 ? 'border-slate-200 dark:border-slate-800 hover:border-emerald-500/30' : 'border-slate-200 dark:border-slate-800 hover:border-red-500/30'
                )}>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-slate-500 dark:text-slate-400 text-xs font-bold uppercase tracking-wider">שינוי יומי</p>
                    <div className={clsx(
                      'w-9 h-9 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform',
                      totalDailyILS >= 0 ? 'bg-gradient-to-br from-emerald-500/20 to-teal-500/20' : 'bg-gradient-to-br from-red-500/20 to-rose-500/20'
                    )}>
                      {totalDailyILS >= 0
                        ? <TrendingUp className="w-4 h-4 text-emerald-500" />
                        : <TrendingDown className="w-4 h-4 text-red-500" />}
                    </div>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <p className={clsx('text-3xl font-black', totalDailyILS >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500 dark:text-red-400')}>
                      {totalDailyILS >= 0 ? '+' : ''}{formatILS(totalDailyILS)}
                    </p>
                    <span className={clsx('text-sm font-bold', dailyChangePct >= 0 ? 'text-emerald-500' : 'text-red-400')}>
                      ({formatPct(dailyChangePct)})
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">שינוי שקלי ואחוזי ביום האחרון</p>
                </div>

                {/* Card 3 — Total Summary (P&L & %) */}
                <div className={clsx(
                  'bg-white dark:bg-slate-900 rounded-2xl border p-5 shadow-sm hover:-translate-y-0.5 transition-all group flex-1',
                  totalPnlILS_val >= 0 ? 'border-slate-200 dark:border-slate-800 hover:border-violet-500/30' : 'border-slate-200 dark:border-slate-800 hover:border-red-500/30'
                )}>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-slate-500 dark:text-slate-400 text-xs font-bold uppercase tracking-wider">סכימה כוללת (רווח/הפסד)</p>
                    <div className={clsx(
                      'w-9 h-9 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform',
                      totalPnlILS_val >= 0 ? 'bg-gradient-to-br from-violet-500/20 to-purple-500/20' : 'bg-gradient-to-br from-red-500/20 to-rose-500/20'
                    )}>
                      {totalPnlILS_val >= 0
                        ? <TrendingUp className="w-4 h-4 text-violet-500" />
                        : <TrendingDown className="w-4 h-4 text-red-500" />}
                    </div>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <p className={clsx('text-3xl font-black', totalPnlILS_val >= 0 ? 'text-violet-600 dark:text-violet-400' : 'text-red-500 dark:text-red-400')}>
                      {totalPnlILS_val >= 0 ? '+' : ''}{formatILS(totalPnlILS_val)}
                    </p>
                    <span className={clsx('text-sm font-bold', totalReturnPct >= 0 ? 'text-violet-500' : 'text-red-400')}>
                      ({formatPct(totalReturnPct)})
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">רווח/הפסד אבסולוטי ואחוזי מתחילת ההשקעה</p>
                </div>
              </>
            )}
          </div>
        </div>

        {/* ── SORTABLE HOLDINGS TABLE ──────────────────────────────── */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
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
                            {h.symbol.slice(0, 2)}
                          </div>
                          <div>
                            <p className="font-bold text-slate-900 dark:text-slate-100 text-[13px] leading-tight">{h.name}</p>
                            <p className="text-slate-400 text-[11px] font-mono">{h.symbol} · {h.currency}</p>
                          </div>
                        </div>
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
                              <button className="w-full text-right flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
                                <Pencil className="w-3.5 h-3.5 text-blue-500" />
                                עדכון
                              </button>
                              <button className="w-full text-right flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors">
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
                    {h.symbol.slice(0, 2)}
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
                    <p className="text-slate-400 text-xs font-mono">{h.symbol}</p>
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
                        <button className="w-full text-right flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700">
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

        {/* Footer note */}
        <p className="text-[11px] text-slate-400 text-center pb-2">
          * נתוני התיק נשמרים בענן; שערי המרה מסונכרנים פעם ב-12 שעות.
        </p>
        </>
        )}
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes fade-in-up { 0%{opacity:0;transform:translateY(10px)} 100%{opacity:1;transform:translateY(0)} }
        .animate-fade-in-up { animation: fade-in-up 0.6s ease-out forwards; }
      ` }} />
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
