import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  UploadCloud, Car, HeartPulse, Home, FileText, ShieldAlert, MessageCircle, X, Loader2, Trash2, Shield
} from 'lucide-react';
import DashboardLayout from '../components/layout/DashboardLayout';
import ActionItems from '../components/dashboard/ActionItems';
import PolicyUploadModal from '../components/PolicyUploadModal';
import { API_URL } from '../lib/api';
import { formatCurrency } from '../utils/format';
import { getTranslation } from '../utils/i18n';
import { DEMO_PORTFOLIO_DATA_EN } from '../data/demoData';

export default function InsurancePage() {
  const navigate = useNavigate();
  const { user, familyConfig, isDemo, isEnglishDemo } = useAuth();
  const t = getTranslation(isEnglishDemo);

  const defaultTab = isEnglishDemo ? 'Health & Critical' : 'רכב';
  const [activeTab, setActiveTab] = useState(defaultTab);
  
  const member1Name = familyConfig?.member1?.name?.split(' ')[0] || (isEnglishDemo ? 'David' : 'אבי');
  const member2Name = familyConfig?.member2?.name?.split(' ')[0] || (isEnglishDemo ? 'Sarah' : 'דנה');
  
  const [funds, setFunds] = useState<any[]>([]);
  const [actionItems, setActionItems] = useState<any[]>([]);
  const [totalCost, setTotalCost] = useState(820);
  
  // Compare State
  const [comparingId, setComparingId] = useState<string | null>(null);
  const [compareDraft, setCompareDraft] = useState<string | null>(null);

  // Upload Modal State
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState<{id: string, name: string} | null>(null);

  const fetchPortfolio = useCallback(async (options?: { refreshAi?: boolean }) => {
    if (!user) return;
    try {
      const token = await user.getIdToken();
      const params = new URLSearchParams();
      if (options?.refreshAi) params.append('refresh_ai', 'true');
      if (isDemo) params.append('lang', isEnglishDemo ? 'en' : 'he');
      const query = params.toString() ? `?${params.toString()}` : '';

      const res = await fetch(`${API_URL}/api/portfolio${query}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      
      let allFunds: any[] = [];
      ['user', 'spouse'].forEach(key => {
          const f = data.portfolios?.[key]?.funds || [];
          allFunds = [...allFunds, ...f];
      });
      
      const insFunds = allFunds.filter(f => f.category === 'insurance');
      
      // Merge identical policies covering both spouses into a single UI card
      const policyMap = new Map<string, any>();

      for (const fund of insFunds) {
          const isRealPolicy = fund.policy_number && fund.policy_number !== 'לא ידוע' && fund.policy_number !== 'nan';
          const key = isRealPolicy ? `${fund.provider_name}_${fund.policy_number}` : fund.id;

          if (policyMap.has(key)) {
              const existing = policyMap.get(key);
              existing.monthly_deposit = Number(existing.monthly_deposit || 0) + Number(fund.monthly_deposit || 0);
              existing.balance = existing.monthly_deposit * 12;
              existing.original_premium = Number(existing.original_premium || 0) + Number(fund.original_premium || 0);
              
              if (fund.owner_name && existing.owner_name && !existing.owner_name.includes(fund.owner_name)) {
                  existing.owner_name = `${existing.owner_name}, ${fund.owner_name}`;
              }
          } else {
              policyMap.set(key, { ...fund });
          }
      }
      
      const finalFunds = Array.from(policyMap.values());
      setFunds(finalFunds);
      
      const customActionItems = (data.action_items || []).filter((a: any) => 
          a.category === 'insurance' || a.category === 'ביטוח' || a.type === 'insurance'
      );
      setActionItems(customActionItems);
      
      const cost = insFunds.reduce((sum, f) => sum + (Number(f.monthly_deposit) || 0), 0);
      if (cost > 0) setTotalCost(cost);
    } catch (e) {
        console.error("Fetch error:", e);
        if (isEnglishDemo) {
          const enFunds = [
            ...(DEMO_PORTFOLIO_DATA_EN.portfolios.user.funds.filter(f => f.category === 'insurance')),
            ...(DEMO_PORTFOLIO_DATA_EN.portfolios.spouse.funds.filter(f => f.category === 'insurance')),
          ];
          setFunds(enFunds);
          setActionItems(DEMO_PORTFOLIO_DATA_EN.action_items.filter(a => a.category === 'insurance'));
          setTotalCost(820);
        }
    }
  }, [user, isDemo, isEnglishDemo]);

  useEffect(() => {
    if (isEnglishDemo) {
      const enFunds = [
        ...(DEMO_PORTFOLIO_DATA_EN.portfolios.user.funds.filter(f => f.category === 'insurance')),
        ...(DEMO_PORTFOLIO_DATA_EN.portfolios.spouse.funds.filter(f => f.category === 'insurance')),
      ];
      setFunds(enFunds);
      setActionItems(DEMO_PORTFOLIO_DATA_EN.action_items.filter(a => a.category === 'insurance'));
      setTotalCost(820);
    }
    fetchPortfolio();
  }, [fetchPortfolio, isEnglishDemo]);

  useEffect(() => {
    setActiveTab(isEnglishDemo ? 'Health & Critical' : 'רכב');
  }, [isEnglishDemo]);

  const handleDeleteFund = async (fundId: string) => {
    if (!window.confirm(isEnglishDemo ? "Are you sure you want to delete this policy?" : "האם ברצונך למחוק פוליסה זו? הפעולה אינה הפיכה.")) return;
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/api/portfolio/fund/${fundId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setFunds(prev => prev.filter(f => f.id !== fundId));
      } else {
        alert("Error deleting policy");
      }
    } catch (e) {
      console.error(e);
      alert("Error deleting policy");
    }
  };

  const filteredFunds = funds.filter(fund => {
    const name = (fund.track_name || fund.name || '').toLowerCase();
    const provider = (fund.provider_name || fund.provider || '').toLowerCase();
    const combined = `${name} ${provider}`;

    if (activeTab === 'Health & Critical' || activeTab === 'חיים ובריאות') {
        return combined.includes('health') || combined.includes('critical') || combined.includes('aetna') || combined.includes('life') || combined.includes('prudential') || combined.includes('בריאות') || combined.includes('חיים') || combined.includes('סעודי') || combined.includes('ריסק');
    }
    if (activeTab === 'Auto & Vehicle' || activeTab === 'רכב') {
        return combined.includes('auto') || combined.includes('car') || combined.includes('tesla') || combined.includes('geico') || combined.includes('רכב') || combined.includes('מקיף') || combined.includes('חובה');
    }
    if (activeTab === 'Property & Umbrella' || activeTab === 'דירה ורכוש') {
        return combined.includes('home') || combined.includes('property') || combined.includes('umbrella') || combined.includes('state farm') || combined.includes('דירה') || combined.includes('מבנה') || combined.includes('תכולה');
    }
    return true;
  });

  const handleCompare = async (policyId: string) => {
    if (!user) return;
    setComparingId(policyId);
    try {
        const token = await user.getIdToken();
        const res = await fetch(`${API_URL}/api/insurance/compare`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ policy_id: policyId })
        });
        const data = await res.json();
        setCompareDraft(data.draft);
    } catch (e) {
        if (isEnglishDemo) {
          setCompareDraft(`Subject: Policy Negotiation & Rate Review - Policy #${policyId}

Dear Insurance Broker,

I am writing regarding my current policy (#${policyId}). Following an AI portfolio review, we identified that comparable comprehensive global health and auto policies offer identical coverages at lower market premiums.

Could you please review our account and provide updated rate matching or deductible optimization options?

Best regards,
David Miller`);
        } else {
          setCompareDraft("שגיאה בעת הפקת טיוטת וואטסאפ.");
        }
    } finally {
        setComparingId(null);
    }
  };

  const tabs = isEnglishDemo ? [
    { id: 'Health & Critical', label: 'Health & Life', icon: HeartPulse },
    { id: 'Auto & Vehicle', label: 'Auto', icon: Car },
    { id: 'Property & Umbrella', label: 'Home & Umbrella', icon: Home }
  ] : [
    { id: 'חיים ובריאות', label: 'חיים ובריאות', icon: HeartPulse },
    { id: 'רכב', label: 'רכב', icon: Car },
    { id: 'דירה ורכוש', label: 'דירה ורכוש', icon: Home }
  ];

  return (
    <DashboardLayout>
      <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 relative">
        
        {/* Page Header & Actions */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 md:mb-8 gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-700 to-indigo-600 dark:from-blue-400 dark:to-indigo-300">
              {t.insurance.title}
            </h1>
            <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm md:text-base">
              {t.insurance.subtitle}
            </p>
          </div>
          
          <button 
            onClick={() => navigate('/settings')}
            className="flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-4 md:px-5 py-2 rounded-lg font-bold text-[11px] md:text-sm transition-all shadow-lg hover:shadow-blue-500/20 w-full md:w-auto"
          >
            <UploadCloud className="w-3.5 h-3.5 md:w-4 md:h-4" />
            <span>{isEnglishDemo ? "Upload Policy Document" : "העלאת מסמך / הר ביטוח"}</span>
          </button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl p-3 md:p-6 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center group transition-all hover:border-violet-500/30">
            <div className="w-10 h-10 md:w-12 md:h-12 bg-violet-50 dark:bg-violet-900/30 rounded-xl flex items-center justify-center text-violet-600 dark:text-violet-400 shrink-0 group-hover:scale-110 transition-transform mx-2">
              <ShieldAlert className="w-5 h-5 md:w-6 md:h-6" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[10px] md:text-xs font-bold text-slate-500 dark:text-slate-400 mb-0.5 md:mb-1 truncate">{t.insurance.totalCost}</p>
              <p className="text-base md:text-2xl font-bold text-slate-900 dark:text-slate-100 truncate">{formatCurrency(totalCost)}</p>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-2xl p-3 md:p-6 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center group transition-all hover:border-blue-500/30">
            <div className="w-10 h-10 md:w-12 md:h-12 bg-blue-50 dark:bg-blue-900/30 rounded-xl flex items-center justify-center text-blue-600 dark:text-blue-400 shrink-0 group-hover:scale-110 transition-transform mx-2">
              <FileText className="w-5 h-5 md:w-6 md:h-6" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[10px] md:text-xs font-bold text-slate-500 dark:text-slate-400 mb-0.5 md:mb-1 truncate">{isEnglishDemo ? "Active Policies" : "פוליסות פעילות"}</p>
              <p className="text-base md:text-2xl font-bold text-slate-900 dark:text-slate-100 truncate">{funds.length}</p>
            </div>
          </div>
        </div>

        {/* Dynamic AI Alerts Section */}
        <ActionItems 
            items={actionItems}
            onRefreshAI={() => fetchPortfolio({ refreshAi: true })}
            title={isEnglishDemo ? "Insurance AI Optimizations & Coverage Warnings" : "התראות AI ופעולות לביצוע בתיק הביטוח"}
            member1Name={member1Name}
            member2Name={member2Name}
        />

        {/* Tabs Navigation */}
        <div className="flex gap-8 border-b border-slate-200 dark:border-slate-700 mb-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 pb-4 px-1 text-sm font-medium transition-colors relative ${
                activeTab === tab.id 
                  ? 'text-blue-600 dark:text-blue-400' 
                  : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
              }`}
            >
              <tab.icon size={18} />
              {tab.label}
              {activeTab === tab.id && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500 rounded-t-full shadow-[0_-2px_8px_rgba(59,130,246,0.5)]" />
              )}
            </button>
          ))}
        </div>

        {/* Content Area */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            
            {/* Dynamic Policies */}
            {filteredFunds.map((fund, idx) => (
                <div key={idx} className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 transition-colors shadow-sm overflow-hidden flex flex-col group relative">
                    <div className="p-6 pb-4 border-b border-slate-100 dark:border-slate-800">
                        <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center gap-3">
                            <div className="bg-blue-500/10 p-2.5 text-blue-500 rounded-lg">
                                <Shield size={24} />
                            </div>
                            <h3 className="font-bold text-base md:text-lg text-slate-900 dark:text-slate-100">{fund.name || fund.track_name || (isEnglishDemo ? 'Insurance Policy' : 'פוליסת ביטוח')}</h3>
                        </div>
                        <div className="flex items-center gap-2">
                           <span className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-xs font-semibold px-2.5 py-1 rounded-full">{t.insurance.activeStatus}</span>
                           <button onClick={(e) => { e.stopPropagation(); handleDeleteFund(fund.id); }} className="text-slate-400 hover:text-red-500 p-1 transition-colors" title="Delete">
                               <Trash2 size={16} />
                           </button>
                        </div>
                        </div>
                    </div>
                    <div className="p-6 py-4 flex-1 space-y-3.5">
                        <div className="flex justify-between text-sm pb-2 border-b border-slate-100 dark:border-slate-800">
                            <span className="text-slate-400">{t.insurance.provider}:</span>
                            <span className="font-bold text-slate-900 dark:text-slate-200">{fund.provider_name || fund.provider || (isEnglishDemo ? 'Aetna International' : 'לא צוין')}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-slate-400">{t.insurance.insured}:</span>
                            <span className="font-medium text-slate-800 dark:text-slate-200">{fund.owner_name || (isEnglishDemo ? 'David & Sarah Miller' : 'לא ידוע')}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-slate-400">{t.insurance.policyNumber}:</span>
                            <span className="font-medium text-slate-800 dark:text-slate-100 bg-slate-100 dark:bg-slate-800 px-2 rounded font-mono">{fund.policy_number || 'AET-773019'}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-slate-400">{t.insurance.monthlyPremium}:</span>
                            <span className="font-semibold text-slate-900 dark:text-white">
                                {formatCurrency(Number((fund.premium_type === 'שנתית' ? fund.original_premium : fund.monthly_deposit) || 0))} 
                                <span className="text-xs font-normal text-slate-500">
                                    {fund.premium_type === 'שנתית' ? (isEnglishDemo ? ' / yr' : ' / לשנה') : (isEnglishDemo ? ' / mo' : ' / לחודש')}
                                </span>
                            </span>
                        </div>
                        <div className="flex justify-between text-sm items-center mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
                            <span className="text-slate-400 font-medium">{isEnglishDemo ? "Policy Document (RAG):" : "מסמך מקור:"}</span>
                            {fund.source_document_url ? (
                                <a href={fund.source_document_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 font-bold text-blue-500 hover:text-blue-600 transition-colors underline">
                                    <FileText size={14} />
                                    {isEnglishDemo ? "View PDF" : "צפה במסמך"}
                                </a>
                            ) : (
                                <button 
                                  onClick={() => {
                                    setSelectedPolicy({ id: fund.id, name: fund.name || fund.track_name || 'Policy' });
                                    setIsUploadModalOpen(true);
                                  }}
                                  className="inline-flex items-center gap-1.5 font-bold text-emerald-500 hover:text-emerald-400 transition-colors"
                                >
                                    <FileText size={14} />
                                    {isEnglishDemo ? "Indexed for RAG" : "העלאת פוליסה"}
                                </button>
                            )}
                        </div>
                    </div>
                    <div className="p-4 bg-slate-50 dark:bg-slate-800/50 border-t border-slate-100 dark:border-slate-800 flex gap-2">
                        <button 
                            disabled={comparingId === fund.id}
                            onClick={() => handleCompare(fund.id || fund.policy_number)}
                            className="flex-1 inline-flex items-center justify-center gap-2 text-sm font-medium bg-blue-600/10 text-blue-600 dark:text-blue-400 hover:bg-blue-600/20 py-2 rounded-lg transition-colors cursor-pointer"
                        >
                            {comparingId === fund.id ? <Loader2 size={16} className="animate-spin" /> : <MessageCircle size={16} />}
                            {isEnglishDemo ? "Generate Agent Letter" : "השווה והפק הודעה"}
                        </button>
                    </div>
                </div>
            ))}

            {/* Empty State visual */}
            {filteredFunds.length === 0 && (
                <div className="col-span-full py-12 flex flex-col items-center justify-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700">
                    <div className="bg-slate-100 dark:bg-slate-800 p-4 rounded-full text-slate-400 mb-4">
                        <FileText size={32} />
                    </div>
                    <p className="text-slate-600 dark:text-slate-400 font-medium">
                      {isEnglishDemo ? `No active policies under "${activeTab}"` : `לא נמצאו פוליסות בקטגוריית "${activeTab}"`}
                    </p>
                </div>
            )}
        </div>
      </div>

      {/* --- Compare WhatsApp / Email Modal --- */}
      {compareDraft && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl overflow-hidden shadow-2xl relative" dir={isEnglishDemo ? "ltr" : "rtl"}>
                <button onClick={() => setCompareDraft(null)} className="absolute top-4 right-4 text-slate-400 hover:text-white">
                    <X size={20} />
                </button>
                <div className="p-6 bg-slate-800/80 border-b border-slate-700 flex items-center gap-3">
                    <div className="bg-blue-500/20 text-blue-400 p-2 rounded-lg">
                        <MessageCircle size={24} />
                    </div>
                    <div>
                        <h3 className="font-bold text-white text-lg">{isEnglishDemo ? "Negotiation Message Draft" : "טיוטת הודעה לסוכן"}</h3>
                        <p className="text-sm text-slate-400">{isEnglishDemo ? "AI-crafted rate matching draft ready to send to your insurance agent." : "הודעה זו יוצרה אישית ע\"י מנוע ה-AI למשא ומתן."}</p>
                    </div>
                </div>
                <div className="p-6">
                    <div className="bg-slate-800 rounded-xl p-4 text-slate-200 leading-relaxed font-medium whitespace-pre-wrap border border-slate-700 text-sm font-sans">
                        {compareDraft}
                    </div>
                    <div className="mt-6 flex justify-end gap-3">
                        <button 
                            onClick={() => {
                                navigator.clipboard.writeText(compareDraft);
                                setCompareDraft(null);
                            }}
                            className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg font-medium transition-colors cursor-pointer"
                        >
                            {isEnglishDemo ? "Copy & Close" : "העתק טקסט וסגור"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
      )}

      {/* ─── Policy Upload Modal ─── */}
      {user && (
        <PolicyUploadModal 
          isOpen={isUploadModalOpen}
          onClose={() => setIsUploadModalOpen(false)}
          onSuccess={() => fetchPortfolio()}
          policyId={selectedPolicy?.id || ''}
          policyName={selectedPolicy?.name || ''}
          uid={user.uid}
        />
      )}

    </DashboardLayout>
  );
}
