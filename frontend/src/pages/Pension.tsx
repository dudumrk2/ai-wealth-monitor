import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import DashboardLayout from '../components/layout/DashboardLayout';
import ActionItems from '../components/dashboard/ActionItems';
import AssetTable from '../components/dashboard/AssetTable';
import PortfolioSummaryCard from '../components/dashboard/PortfolioSummaryCard';
import AlternativeInvestmentsTable from '../components/dashboard/AlternativeInvestmentsTable';
import type { SummaryRow } from '../components/dashboard/PortfolioSummaryCard';
import type { Fund, FundCategory, ActionItem, AlternativeInvestment } from '../types/portfolio';
import { CATEGORY_LABELS } from '../types/portfolio';
import { useAuth } from '../context/AuthContext';
import clsx from 'clsx';
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { Info } from 'lucide-react';
import RedactionPreviewModal, { type FilePreviewGroup } from '../components/onboarding/RedactionPreviewModal';
import ProcessingStatusModal, { type ProcessingStatus } from '../components/onboarding/ProcessingStatusModal';

import { API_URL } from '../lib/api';

type TabView = 'user' | 'spouse' | 'joint';

const CATEGORY_COLORS: Record<FundCategory, string> = {
  pension:              '#3b82f6', // blue
  managers:             '#ef4444', // red/pink (classic ביטוח color)
  study:                '#10b981', // emerald
  provident:            '#f59e0b', // amber
  investment_provident: '#8b5cf6', // purple
  stocks:               '#f97316', // orange
  alternative:          '#6366f1', // indigo
};

/** Build SummaryRow[] from a funds list, grouping by category. */
function buildRows(funds: Fund[], field: 'balance' | 'monthly_deposit'): SummaryRow[] {
  const map = new Map<FundCategory, number>();
  for (const f of funds) {
    if (f.category === 'alternative') continue; // Alternatives handled separately
    map.set(f.category, (map.get(f.category) ?? 0) + (f[field] ?? 0));
  }
  return Array.from(map.entries())
    .filter(([, v]) => v > 0)
    .map(([cat, val]) => ({
      label: CATEGORY_LABELS[cat],
      balance: val,
      color: '',
      hex: CATEGORY_COLORS[cat],
    }));
}

export default function Pension() {
  const { user, familyConfig } = useAuth();
  const [activeTab, setActiveTab] = useState<TabView>('joint');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [portfolioData, setPortfolioData] = useState<any>(null);

  // Analysis Flow State
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [fileGroups, setFileGroups] = useState<FilePreviewGroup[]>([]);
  const [seenFiles, setSeenFiles] = useState<Set<string>>(new Set());
  const [isStatusModalOpen, setIsStatusModalOpen] = useState(false);
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus>('loading');
  const [processingResultsSummary, setProcessingResultsSummary] = useState<any>(null);
  const [processingError, setProcessingError] = useState<string | null>(null);

  const [chartTab, setChartTab] = useState<'assets' | 'providers'>('assets');
  const [summaryTab, setSummaryTab] = useState<'balance' | 'monthly'>('balance');

  // Guard to prevent auto-scan from firing more than once per session
  const autoScanFiredRef = useRef(false);

  const fetchPortfolio = useCallback(async (options?: { silent?: boolean, refreshMarket?: boolean, refreshAi?: boolean } | boolean) => {
    // Support both the old boolean signature and the new options object
    const silent = typeof options === 'boolean' ? options : options?.silent ?? false;
    const refreshMarket = typeof options === 'object' ? options.refreshMarket ?? false : false;
    const refreshAi = typeof options === 'object' ? options.refreshAi ?? false : false;

    try {
      if (!silent) setLoading(true);
      setError(null);
      const startTime = Date.now();
      const idToken = await user?.getIdToken();

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

      // Ensure at least 600ms of loading for visual feedback
      const elapsed = Date.now() - startTime;
      if (!silent && elapsed < 600) {
        await new Promise(resolve => setTimeout(resolve, 600 - elapsed));
      }
    } catch (err: any) {
      console.error('Portfolio fetch error:', err);
      if (!silent) setError('אירעה שגיאה בטעינת הנתונים.');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [user]);

  const { member1Name, member2Name, householdName } = useMemo(() => ({
    member1Name: familyConfig?.member1?.name?.split(' ')[0] || 'המבוטח הראשי',
    member2Name: familyConfig?.member2?.name?.split(' ')[0] || 'בן/בת הזוג',
    householdName: familyConfig?.householdName || 'המשפחה',
  }), [familyConfig]);

  // Initial portfolio fetch on mount
  useEffect(() => {
    fetchPortfolio();
  }, [fetchPortfolio]);

  // Auto-scan for inbox files whenever familyConfig becomes available
  useEffect(() => {
    if (!user || !familyConfig) return;

    // Prevent double-firing (React StrictMode or deps changing twice)
    if (autoScanFiredRef.current) return;
    autoScanFiredRef.current = true;
    
    const checkInbox = async () => {
      try {
        const idToken = await user.getIdToken();
        const piiData = {
          member1: familyConfig.member1,
          member2: familyConfig.member2,
          debug: true,
          analyze: false
        };
        const res = await fetch(`${API_URL}/api/process-inbox`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${idToken}`
          },
          body: JSON.stringify(piiData)
        });
        
        if (!res.ok) {
          const errText = await res.text();
          console.error('[Dashboard] /api/process-inbox failed:', errText);
          return;
        }
        
        const result = await res.json();
        
        // Detect new files by filename (backend returns {filename, status:'preview_only'})
        const allResults: any[] = result.results || [];
        const newFiles = allResults
          .filter((r: any) => !r.error && !seenFiles.has(r.filename))
          .map((r: any) => r.filename);
        
        if (newFiles.length > 0) {
          // Build per-file groups preserving {filename, images} structure
          const groups: FilePreviewGroup[] = allResults
            .filter((r: any) => !r.error && !seenFiles.has(r.filename))
            .map((r: any) => ({
              filename: r.filename,
              images: r.preview_images || [],
            }));
          setFileGroups(groups);

          const nextSeen = new Set(seenFiles);
          newFiles.forEach((name: string) => nextSeen.add(name));
          setSeenFiles(nextSeen);

          setIsPreviewOpen(true);
        }
      } catch (e) {
        console.error('[Dashboard] Auto-scan check failed:', e);
      }
    };

    checkInbox();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, familyConfig]);

  const handleConfirmAnalysis = async () => {
    if (!user || !familyConfig) return;
    setIsPreviewOpen(false);
    setIsStatusModalOpen(true);
    setProcessingStatus('loading');
    setProcessingError(null);

    try {
      const idToken = await user?.getIdToken();
      const piiData = {
        member1: familyConfig.member1,
        member2: familyConfig.member2,
        debug: false,
        analyze: true
      };

      const response = await fetch(`${API_URL}/api/process-inbox`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${idToken}`
        },
        body: JSON.stringify(piiData)
      });

      if (!response.ok) throw new Error('הניתוח נכשל');
      const result = await response.json();

      // Separate successes from errors
      const successResults = result.results.filter((r: any) => !r.error);
      const errorResults = result.results.filter((r: any) => r.error);

      const fundsCount = successResults.reduce((acc: number, res: any) => acc + (res.data?.products?.length || 0), 0);
      setProcessingResultsSummary({
        filesCount: successResults.length,
        fundsFound: fundsCount,
        errors: errorResults.length > 0 ? errorResults.map((r: any) => r.error) : undefined,
      });

      // Refresh data silently so new funds appear in dashboard
      fetchPortfolio(true);

      // Show success even for partial results; if ALL failed, show error
      if (successResults.length === 0 && errorResults.length > 0) {
        setProcessingStatus('error');
        setProcessingError(errorResults[0]?.error || 'אירעה שגיאה בניתוח הקבצים.');
      } else {
        setProcessingStatus('success');
      }

    } catch (err: any) {
      console.error('Analysis error:', err);
      setProcessingStatus('error');
      setProcessingError(err.message || 'לא ניתן היה להשלים את הניתוח.');
    }
  };



  const userFunds    = portfolioData?.portfolios?.user?.funds as Fund[] || [];
  const spouseFunds  = portfolioData?.portfolios?.spouse?.funds as Fund[] || [];
  const jointStocks  = (portfolioData?.portfolios?.joint?.stock_investments || []) as Fund[];
  const altInvest    = (portfolioData?.portfolios?.user?.alternative_investments || []) as AlternativeInvestment[];
  const joint        = portfolioData?.portfolios?.joint || { total_family_wealth: 0, asset_allocation_percentages: {}, provider_exposure: {} };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'user': {
        const balanceRows  = buildRows(userFunds, 'balance');
        const monthlyRows  = buildRows(userFunds.filter(f => f.monthly_deposit > 0), 'monthly_deposit');
        const categories = [...new Set(userFunds.map(f => f.category))];
        return (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Mobile Tabbed View */}
              <div className="lg:hidden bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                <div className="flex bg-slate-100 dark:bg-slate-800 p-1 m-4 rounded-xl w-fit">
                  <button
                    onClick={() => setSummaryTab('balance')}
                    className={clsx(
                      "px-4 py-1.5 text-xs font-bold rounded-lg transition-all",
                      summaryTab === 'balance' ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm" : "text-slate-500 hover:text-slate-700"
                    )}
                  >
                    סיכום צבירה
                  </button>
                  <button
                    onClick={() => setSummaryTab('monthly')}
                    className={clsx(
                      "px-4 py-1.5 text-xs font-bold rounded-lg transition-all",
                      summaryTab === 'monthly' ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm" : "text-slate-500 hover:text-slate-700"
                    )}
                  >
                    הפקדות חודשיות
                  </button>
                </div>
                {summaryTab === 'balance' ? (
                  <PortfolioSummaryCard title={`סך החשבון שצברת`} rows={balanceRows} variant="balance" />
                ) : (
                  <PortfolioSummaryCard title="סך ההפקדות החודשי" rows={monthlyRows} variant="monthly" />
                )}
              </div>

              {/* Desktop Side-by-Side View */}
              <div className="hidden lg:block h-full">
                <PortfolioSummaryCard title={`סך החשבון שצברת`} rows={balanceRows} variant="balance" />
              </div>
              <div className="hidden lg:block h-full">
                <PortfolioSummaryCard title="סך ההפקדות החודשי" rows={monthlyRows} variant="monthly" />
              </div>
            </div>
            {categories.map(cat => (
              <AssetTable key={cat} title={CATEGORY_LABELS[cat]} funds={userFunds.filter(f => f.category === cat)} />
            ))}
            {altInvest.length > 0 && <AlternativeInvestmentsTable items={altInvest} />}
          </div>
        );
      }
      case 'spouse': {
        const balanceRows  = buildRows(spouseFunds, 'balance');
        const monthlyRows  = buildRows(spouseFunds.filter(f => f.monthly_deposit > 0), 'monthly_deposit');
        const categories   = [...new Set(spouseFunds.map(f => f.category))];
        return (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Mobile Tabbed View */}
              <div className="lg:hidden bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                <div className="flex bg-slate-100 dark:bg-slate-800 p-1 m-4 rounded-xl w-fit">
                  <button
                    onClick={() => setSummaryTab('balance')}
                    className={clsx(
                      "px-4 py-1.5 text-xs font-bold rounded-lg transition-all",
                      summaryTab === 'balance' ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm" : "text-slate-500 hover:text-slate-700"
                    )}
                  >
                    סיכום צבירה
                  </button>
                  <button
                    onClick={() => setSummaryTab('monthly')}
                    className={clsx(
                      "px-4 py-1.5 text-xs font-bold rounded-lg transition-all",
                      summaryTab === 'monthly' ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm" : "text-slate-500 hover:text-slate-700"
                    )}
                  >
                    הפקדות חודשיות
                  </button>
                </div>
                {summaryTab === 'balance' ? (
                  <PortfolioSummaryCard title="סך החשבון שצברת" rows={balanceRows} variant="balance" />
                ) : (
                  <PortfolioSummaryCard title="סך ההפקדות החודשי" rows={monthlyRows} variant="monthly" />
                )}
              </div>

              {/* Desktop Side-by-Side View */}
              <div className="hidden lg:block h-full">
                <PortfolioSummaryCard title="סך החשבון שצברת" rows={balanceRows} variant="balance" />
              </div>
              <div className="hidden lg:block h-full">
                <PortfolioSummaryCard title="סך ההפקדות החודשי" rows={monthlyRows} variant="monthly" />
              </div>
            </div>
            {categories.map(cat => (
              <AssetTable key={cat} title={CATEGORY_LABELS[cat]} funds={spouseFunds.filter(f => f.category === cat)} />
            ))}
          </div>
        );
      }
      case 'joint':
      default: {
        const allFundsForSummary = [...userFunds, ...spouseFunds, ...jointStocks];
        const balanceRows = buildRows(allFundsForSummary, 'balance');
        const monthlyRows = buildRows(allFundsForSummary.filter(f => f.monthly_deposit > 0), 'monthly_deposit');
        const jointUserFunds   = userFunds.map(f  => ({ ...f, _owner: member1Name }));
        const jointSpouseFunds = spouseFunds.map(f => ({ ...f, _owner: member2Name }));
        const categories = [...new Set([...userFunds, ...spouseFunds].map(f => f.category))];
        return (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Mobile Tabbed View */}
              <div className="lg:hidden bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                <div className="flex bg-slate-100 dark:bg-slate-800 p-1 m-4 rounded-xl w-fit">
                  <button
                    onClick={() => setSummaryTab('balance')}
                    className={clsx(
                      "px-4 py-1.5 text-xs font-bold rounded-lg transition-all",
                      summaryTab === 'balance' ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm" : "text-slate-500 hover:text-slate-700"
                    )}
                  >
                    סיכום משפחתי
                  </button>
                  <button
                    onClick={() => setSummaryTab('monthly')}
                    className={clsx(
                      "px-4 py-1.5 text-xs font-bold rounded-lg transition-all",
                      summaryTab === 'monthly' ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm" : "text-slate-500 hover:text-slate-700"
                    )}
                  >
                    הפקדות חודשיות
                  </button>
                </div>
                {summaryTab === 'balance' ? (
                  <PortfolioSummaryCard title={`סך החשבון המשפחתי — ${householdName}`} rows={balanceRows} variant="balance" />
                ) : (
                  <PortfolioSummaryCard title="סך ההפקדות החודשיות" rows={monthlyRows} variant="monthly" />
                )}
              </div>

              {/* Desktop Side-by-Side View */}
              <div className="hidden lg:block h-full">
                <PortfolioSummaryCard title={`סך החשבון המשפחתי — ${householdName}`} rows={balanceRows} variant="balance" />
              </div>
              <div className="hidden lg:block h-full">
                <PortfolioSummaryCard title="סך ההפקדות החודשיות" rows={monthlyRows} variant="monthly" />
              </div>
            </div>
            <ActionItems 
              items={(portfolioData.action_items as ActionItem[] || []).filter(item => 
                ['פנסיה', 'בורסה', 'כללי', 'equity', 'מניות'].includes(item.category || 'כללי')
              )} 
              onRefreshAI={() => fetchPortfolio({ refreshAi: true })}
              member1Name={member1Name}
              member2Name={member2Name}
            />
            {categories.map(cat => {
              const catFunds = [...jointUserFunds.filter(f => f.category === cat), ...jointSpouseFunds.filter(f => f.category === cat)];
              if (catFunds.length === 0) return null;
              return <AssetTable key={cat} title={`${CATEGORY_LABELS[cat]} — כלל המשפחה`} funds={catFunds} ownerColumn={catFunds.some(f => f._owner)} />;
            })}
            {jointStocks.length > 0 && <AssetTable title="תיק מניות משפחתי" funds={jointStocks} />}
            {altInvest.length > 0 && <AlternativeInvestmentsTable items={altInvest} />}
            
            {/* Bottom Analysis Cards */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Mobile Tabbed Analysis View */}
              <div className="lg:hidden bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm transition-all hover:border-slate-300 dark:hover:border-slate-700">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
                  <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-xl p-1">
                    <button
                      onClick={() => setChartTab('assets')}
                      className={clsx(
                        "px-4 py-2 text-xs md:text-sm font-bold rounded-lg transition-all duration-200",
                        chartTab === 'assets'
                          ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm"
                          : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
                      )}
                    >
                      פיזור נכסים
                    </button>
                    <button
                      onClick={() => setChartTab('providers')}
                      className={clsx(
                        "px-4 py-2 text-xs md:text-sm font-bold rounded-lg transition-all duration-200",
                        chartTab === 'providers'
                          ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm"
                          : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
                      )}
                    >
                      חשיפה לספקים
                    </button>
                  </div>
                  <Info className="w-5 h-5 text-slate-400 hidden sm:block" />
                </div>

                {chartTab === 'assets' ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
                    <div className="relative h-[220px] md:h-[280px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={[
                              { name: 'מניות', value: joint.asset_allocation_percentages?.stocks ?? 0, color: '#3b82f6' },
                              { name: 'אג״ח', value: joint.asset_allocation_percentages?.bonds ?? 0, color: '#10b981' },
                              { name: 'מזומן', value: joint.asset_allocation_percentages?.cash_equivalents ?? 0, color: '#f59e0b' },
                            ].filter(d => d.value > 0)}
                            cx="50%" cy="50%"
                            innerRadius="60%" outerRadius="85%"
                            paddingAngle={5}
                            dataKey="value"
                            stroke="none"
                          >
                            {[
                              { color: '#3b82f6' },
                              { color: '#10b981' },
                              { color: '#f59e0b' }
                            ].map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip 
                            contentStyle={{ 
                              borderRadius: '12px', 
                              border: 'none', 
                              boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
                              direction: 'rtl'
                            }} 
                          />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                        <span className="text-[10px] md:text-xs font-bold text-slate-400 uppercase tracking-wider">פיזור</span>
                        <span className="text-xl md:text-2xl font-black text-slate-800 dark:text-white">נכסים</span>
                      </div>
                    </div>
                    
                    <div className="space-y-4">
                      {[
                        { label: 'מניות', pct: joint.asset_allocation_percentages?.stocks ?? 0, color: 'bg-blue-600' },
                        { label: 'אג״ח', pct: joint.asset_allocation_percentages?.bonds ?? 0, color: 'bg-emerald-500' },
                        { label: 'מזומן ושווי מזומן', pct: joint.asset_allocation_percentages?.cash_equivalents ?? 0, color: 'bg-amber-400' },
                      ].map(({ label, pct, color }) => (
                        <div key={label} className="group">
                          <div className="flex justify-between text-sm font-bold mb-1.5">
                            <span className="text-slate-600 dark:text-slate-400 group-hover:text-slate-900 dark:group-hover:text-slate-200 transition-colors">{label}</span>
                            <span className="text-slate-900 dark:text-slate-100">{pct}%</span>
                          </div>
                          <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2">
                            <div className={clsx(color, "h-2 rounded-full transition-all duration-1000 shadow-sm")} style={{ width: `${pct}%` }}></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {Object.entries(joint.provider_exposure || {}).map(([provider, value]) => (
                      <div key={provider} className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-800/60 hover:border-blue-500/30 transition-all group">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 bg-white dark:bg-slate-700 rounded-lg flex items-center justify-center font-black text-[10px] text-slate-400 border border-slate-100 dark:border-slate-600 group-hover:text-blue-500 transition-colors">
                            {provider.slice(0, 1)}
                          </div>
                          <span className="text-sm font-bold text-slate-700 dark:text-slate-300">{provider}</span>
                        </div>
                        <span className="text-sm font-black text-slate-900 dark:text-slate-100">{value as number}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Desktop Separate Analysis View */}
              <div className="hidden lg:block h-full bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800">
                <h3 className="font-bold text-slate-800 dark:text-slate-100 mb-4 text-lg">פיזור נכסים</h3>
                <div className="space-y-4">
                  {[
                    { label: 'מניות', pct: joint.asset_allocation_percentages?.stocks ?? 0, color: 'bg-blue-600' },
                    { label: 'אג״ח', pct: joint.asset_allocation_percentages?.bonds ?? 0, color: 'bg-emerald-500' },
                    { label: 'מזומן ושווי מזומן', pct: joint.asset_allocation_percentages?.cash_equivalents ?? 0, color: 'bg-amber-400' },
                  ].map(({ label, pct, color }) => (
                    <div key={label}>
                      <div className="flex justify-between text-sm font-semibold mb-1.5"><span className="text-slate-600 dark:text-slate-400">{label}</span><span className="text-slate-900 dark:text-slate-100">{pct}%</span></div>
                      <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2.5"><div className={`${color} h-2.5 rounded-full`} style={{ width: `${pct}%` }}></div></div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="hidden lg:block h-full bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800">
                <h3 className="font-bold text-slate-800 dark:text-slate-100 mb-4 text-lg">חשיפה לספקים</h3>
                <div className="space-y-3">
                  {Object.entries(joint.provider_exposure || {}).map(([provider, value]) => (
                    <div key={provider} className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg text-sm font-semibold">
                      <span className="text-slate-700 dark:text-slate-300">{provider}</span>
                      <span className="text-slate-900 dark:text-slate-100">{value as number}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        );
      }
    }
  };

  return (
    <DashboardLayout onRefresh={() => fetchPortfolio({ refreshMarket: true, refreshAi: true })} isRefreshing={loading}>
      {/* Analysis Modals - Rendered here so they stay in DOM during content swaps */}
      <RedactionPreviewModal 
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
        fileGroups={fileGroups}
        onConfirm={handleConfirmAnalysis}
        isProcessing={processingStatus === 'loading' && isStatusModalOpen}
      />

      <ProcessingStatusModal
        isOpen={isStatusModalOpen}
        status={processingStatus}
        resultsSummary={processingResultsSummary}
        error={processingError || undefined}
        onClose={() => setIsStatusModalOpen(false)}
        onProceed={() => {
          setIsStatusModalOpen(false);
          fetchPortfolio(); // Final loud refresh to ensure UI sync
        }}
      />

      {loading ? (
        <div className="h-[60vh] flex flex-col items-center justify-center gap-4">
          <Loader2 className="w-12 h-12 text-blue-600 animate-spin" />
          <p className="text-slate-500 font-medium">טוען ננתונים פיננסיים...</p>
        </div>
      ) : error || !portfolioData ? (
        <div className="h-[60vh] flex flex-col items-center justify-center gap-4 max-w-md mx-auto text-center">
          <div className="bg-red-50 p-4 rounded-full">
            <AlertCircle className="w-10 h-10 text-red-500" />
          </div>
          <h2 className="text-xl font-bold text-slate-800">אופס, משהו השתבש</h2>
          <p className="text-slate-500">{error || 'לא הצלחנו לטעון את תיק ההשקעות שלך. וודא שהשרת רץ ונסה שוב.'}</p>
          <button onClick={() => fetchPortfolio()} className="mt-4 flex items-center gap-2 bg-slate-900 text-white px-6 py-2.5 rounded-xl font-semibold hover:bg-slate-800 transition-colors">
            <RefreshCw className="w-4 h-4" /> טען שוב
          </button>
        </div>
      ) : (
        <>
          <div className="mb-4 md:mb-8 animate-fade-in-up">
            <h1 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-slate-100">סקירת תיק פנסיוני</h1>
            <p className="text-slate-500 dark:text-slate-500 text-sm md:text-base mt-1 italic">עקוב, נתח ומטב את עתיד משפחתך.</p>
          </div>

          <div className="flex flex-col gap-4 md:gap-8">
            <div className="min-w-0">
              <div className="bg-slate-200/50 dark:bg-slate-800/50 p-1 rounded-xl inline-flex mb-4 md:mb-6 overflow-x-auto max-w-full">
                {([
                  { id: 'joint',  label: 'תצוגה משותפת' },
                  { id: 'user',   label: member1Name },
                  { id: 'spouse', label: member2Name },
                ] as const).map(tab => (
                  <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                    className={clsx(
                      "px-4 md:px-6 py-2 md:py-2.5 rounded-lg text-xs md:text-sm font-bold transition-all whitespace-nowrap",
                      activeTab === tab.id 
                        ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm" 
                        : "text-slate-500 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                    )}>
                    {tab.label}
                  </button>
                ))}
              </div>
              {renderTabContent()}
            </div>
          </div>
        </>
      )}
    </DashboardLayout>
  );
}


