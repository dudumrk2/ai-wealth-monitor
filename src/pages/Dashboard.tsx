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
import RedactionPreviewModal, { type FilePreviewGroup } from '../components/onboarding/RedactionPreviewModal';
import ProcessingStatusModal, { type ProcessingStatus } from '../components/onboarding/ProcessingStatusModal';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

export default function Dashboard() {
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
  const [isReprocessing, setIsReprocessing] = useState(false);

  // Guard to prevent auto-scan from firing more than once per session
  const autoScanFiredRef = useRef(false);

  const fetchPortfolio = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      setError(null);
      const idToken = await user?.getIdToken();
      const response = await fetch(`${API_URL}/api/portfolio`, {
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

  const handleReprocessAdvisory = async () => {
    if (!user) return;
    setIsReprocessing(true);
    try {
      const idToken = await user.getIdToken();
      const response = await fetch(`${API_URL}/api/test-reprocess-advisory`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${idToken}`
        }
      });
      if (!response.ok) throw new Error('Reprocess failed');
      alert('ההמלצות רועננו בהצלחה מהדאטה הקיים!');
      fetchPortfolio(true);
    } catch (err) {
      console.error('Reprocess error:', err);
      alert('שגיאה בריענון ההמלצות.');
    } finally {
      setIsReprocessing(false);
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
              <PortfolioSummaryCard title={`סך החשבון שצברת`} rows={balanceRows} variant="balance" />
              <PortfolioSummaryCard title="סך ההפקדות החודשי" rows={monthlyRows} variant="monthly" />
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
              <PortfolioSummaryCard title="סך החשבון שצברת" rows={balanceRows} variant="balance" />
              <PortfolioSummaryCard title="סך ההפקדות החודשי" rows={monthlyRows} variant="monthly" />
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
              <PortfolioSummaryCard title={`סך החשבון המשפחתי — ${householdName}`} rows={balanceRows} variant="balance" />
              <PortfolioSummaryCard title="סך ההפקדות החודשיות" rows={monthlyRows} variant="monthly" />
            </div>
            <ActionItems items={portfolioData.action_items as ActionItem[]} />
            {categories.map(cat => {
              const catFunds = [...jointUserFunds.filter(f => f.category === cat), ...jointSpouseFunds.filter(f => f.category === cat)];
              if (catFunds.length === 0) return null;
              return <AssetTable key={cat} title={`${CATEGORY_LABELS[cat]} — כלל המשפחה`} funds={catFunds} ownerColumn={catFunds.some(f => f._owner)} />;
            })}
            {jointStocks.length > 0 && <AssetTable title="תיק מניות משפחתי" funds={jointStocks} />}
            {altInvest.length > 0 && <AlternativeInvestmentsTable items={altInvest} />}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white p-6 rounded-2xl border border-slate-200">
                <h3 className="font-bold text-slate-800 mb-4 text-lg">פיזור נכסים</h3>
                <div className="space-y-4">
                  {[
                    { label: 'מניות', pct: joint.asset_allocation_percentages?.stocks ?? 0, color: 'bg-blue-600' },
                    { label: 'אג״ח', pct: joint.asset_allocation_percentages?.bonds ?? 0, color: 'bg-emerald-500' },
                    { label: 'מזומן ושווי מזומן', pct: joint.asset_allocation_percentages?.cash_equivalents ?? 0, color: 'bg-amber-400' },
                  ].map(({ label, pct, color }) => (
                    <div key={label}>
                      <div className="flex justify-between text-sm font-semibold mb-1.5"><span className="text-slate-600">{label}</span><span className="text-slate-900">{pct}%</span></div>
                      <div className="w-full bg-slate-100 rounded-full h-2.5"><div className={`${color} h-2.5 rounded-full`} style={{ width: `${pct}%` }}></div></div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-white p-6 rounded-2xl border border-slate-200">
                <h3 className="font-bold text-slate-800 mb-4 text-lg">חשיפה לספקים</h3>
                <div className="space-y-3">
                  {Object.entries(joint.provider_exposure || {}).map(([provider, value]) => (
                    <div key={provider} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg text-sm font-semibold"><span className="text-slate-700">{provider}</span><span className="text-slate-900">{value as number}%</span></div>
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
    <DashboardLayout>
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
          <p className="text-slate-500 font-medium">טוען נתונים פיננסיים...</p>
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
          <div className="mb-8 flex justify-between items-end">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-slate-900">סקירת תיק פנסיוני</h1>
              <p className="text-slate-500 mt-1">עקוב, נתח ומטב את עתיד משפחתך.</p>
            </div>
            <div className="flex gap-2">
              <button 
                onClick={handleReprocessAdvisory} 
                disabled={isReprocessing}
                className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-blue-600 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors disabled:opacity-50"
              >
                {isReprocessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                רענן המלצות (בדיקה)
              </button>
              <button 
                onClick={() => fetchPortfolio()} 
                className="p-2 text-slate-400 hover:text-blue-600 transition-colors bg-white border border-slate-200 rounded-lg shadow-sm"
              >
                <RefreshCw className={clsx("w-5 h-5", loading && "animate-spin")} />
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-8">
            <div className="min-w-0">
              <div className="bg-slate-200/50 p-1 rounded-xl inline-flex mb-6 overflow-x-auto max-w-full">
                {([
                  { id: 'joint',  label: 'תצוגה משותפת' },
                  { id: 'user',   label: member1Name },
                  { id: 'spouse', label: member2Name },
                ] as const).map(tab => (
                  <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                    className={clsx(
                      "px-6 py-2.5 rounded-lg text-sm font-bold transition-all whitespace-nowrap",
                      activeTab === tab.id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
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


