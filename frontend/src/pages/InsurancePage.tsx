import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  UploadCloud, AlertCircle, Car, HeartPulse, Home, FileText, ShieldAlert, MessageCircle, X, Loader2, Trash2, Upload
} from 'lucide-react';
import DashboardLayout from '../components/layout/DashboardLayout';
import ActionItems from '../components/dashboard/ActionItems';
import PolicyUploadModal from '../components/PolicyUploadModal';

import { API_URL } from '../lib/api';

export default function InsurancePage() {
  const [activeTab, setActiveTab] = useState('רכב');
  const navigate = useNavigate();
  const { user } = useAuth();
  
  const [funds, setFunds] = useState<any[]>([]);
  const [actionItems, setActionItems] = useState<any[]>([]);
  const [totalCost, setTotalCost] = useState(1850);
  
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
          // Use policy_number + provider as a unique key (fallback to its own ID if missing)
          const isRealPolicy = fund.policy_number && fund.policy_number !== 'לא ידוע' && fund.policy_number !== 'nan';
          const key = isRealPolicy ? `${fund.provider_name}_${fund.policy_number}` : fund.id;

          if (policyMap.has(key)) {
              const existing = policyMap.get(key);
              // Sum the normalized monthly premiums
              existing.monthly_deposit = Number(existing.monthly_deposit || 0) + Number(fund.monthly_deposit || 0);
              existing.balance = existing.monthly_deposit * 12;
              
              // Sum the actual original premiums
              existing.original_premium = Number(existing.original_premium || 0) + Number(fund.original_premium || 0);
              
              // Append name if it's different to show both spouses
              if (fund.owner_name && existing.owner_name && !existing.owner_name.includes(fund.owner_name)) {
                  existing.owner_name = `${existing.owner_name}, ${fund.owner_name}`;
              }
          } else {
              policyMap.set(key, { ...fund });
          }
      }
      
      setFunds(Array.from(policyMap.values()));
      
      const customActionItems = (data.action_items || []).filter((a: any) => 
          a.category === 'insurance' || a.category === 'ביטוח' || a.type === 'insurance'
      );
      setActionItems(customActionItems);
      
      const cost = insFunds.reduce((sum, f) => sum + (Number(f.monthly_deposit) || 0), 0);
      if (cost > 0) setTotalCost(cost);
    } catch (e) {
        console.error("Fetch error:", e);
    }
  }, [user]);

  useEffect(() => {
    fetchPortfolio();
  }, [fetchPortfolio]);

  const handleDeleteFund = async (fundId: string) => {
    if (!window.confirm("האם ברצונך למחוק פוליסה זו? הפעולה אינה הפיכה.")) return;
    try {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_URL}/api/portfolio/fund/${fundId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setFunds(prev => prev.filter(f => f.id !== fundId));
      } else {
        alert("שגיאה במחיקת הפוליסה");
      }
    } catch (e) {
      console.error(e);
      alert("שגיאה במחיקת הפוליסה");
    }
  };

  const filteredFunds = funds.filter(fund => {
    const name = (fund.track_name || '').toLowerCase();
    const provider = (fund.provider_name || fund.provider || '').toLowerCase();
    const combined = `${name} ${provider}`;

    if (activeTab === 'רכב') {
        return combined.includes('רכב') || combined.includes('מקיף') || combined.includes('חובה') || combined.includes('צד ג');
    }
    if (activeTab === 'חיים ובריאות') {
        return combined.includes('חיים') || combined.includes('בריאות') || combined.includes('סעודי') || combined.includes('תאונות') || combined.includes('מחלות') || combined.includes('ריסק');
    }
    if (activeTab === 'דירה ורכוש') {
        return combined.includes('דירה') || combined.includes('מבנה') || combined.includes('תכולה') || combined.includes('רכוש') || combined.includes('ועד הבית');
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
        setCompareDraft("שגיאה בעת הפקת טיוטת וואטסאפ.");
    } finally {
        setComparingId(null);
    }
  };

  return (
    <DashboardLayout>
      <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 relative">
        
        {/* Page Header & Actions */}
        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6">
          <div>
            <h1 className="text-3xl font-bold mb-2">ביטוחים</h1>
            <p className="text-slate-400">ניהול פוליסות, מניעת כפל ביטוחי והעלאת מסמכים</p>
          </div>
          
          <div className="flex flex-col md:flex-row items-start md:items-center gap-4 w-full xl:w-auto">
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4 w-full md:w-auto">
              <div className="bg-slate-800 px-4 py-2.5 rounded-lg flex items-center justify-center gap-2 border border-slate-700 shadow-sm">
                <span className="text-sm text-slate-400">סה״כ עלות חודשית:</span>
                <span className="text-lg font-bold text-white">₪{totalCost.toLocaleString()}</span>
              </div>
              {actionItems.length > 0 && (
                <div className="bg-orange-500/10 px-4 py-2.5 rounded-lg flex items-center justify-center gap-2 border border-orange-500/20 text-orange-500 shadow-sm">
                  <AlertCircle size={20} />
                  <span className="text-sm font-medium">התראה אמיתית: קיימות המלצות AI חדשות לביצוע!</span>
                </div>
              )}
            </div>
            
            <button 
              onClick={() => navigate('/settings')}
              className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg font-medium transition-colors shadow-sm w-full md:w-auto mt-2 md:mt-0"
            >
              <UploadCloud size={20} />
              <span>העלאת מסמך / הר ביטוח</span>
            </button>
          </div>
        </div>

        {/* Dynamic AI Alerts Section */}
        <ActionItems 
            items={actionItems}
            onRefreshAI={() => fetchPortfolio({ refreshAi: true })}
            title="התראות AI ופעולות לביצוע בתיק הביטוח"
        />

        {/* Tabs Navigation */}
        <div className="flex gap-8 border-b border-slate-700 mb-6">
          {[
            { id: 'חיים ובריאות', icon: HeartPulse },
            { id: 'רכב', icon: Car },
            { id: 'דירה ורכוש', icon: Home }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 pb-4 px-1 text-sm font-medium transition-colors relative ${
                activeTab === tab.id 
                  ? 'text-blue-400' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <tab.icon size={18} />
              {tab.id}
              {activeTab === tab.id && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500 rounded-t-full shadow-[0_-2px_8px_rgba(59,130,246,0.5)]" />
              )}
            </button>
          ))}
        </div>

        {/* Content Area */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            
            {/* Dynamic Real Funds */}
            {filteredFunds.map((fund, idx) => (
                <div key={idx} className="bg-slate-800 rounded-xl border border-slate-700 hover:border-slate-600 transition-colors shadow-lg overflow-hidden flex flex-col group relative">
                    <div className="p-6 pb-4 border-b border-slate-700/50">
                        <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center gap-3">
                            <div className="bg-blue-500/10 p-2.5 text-blue-400 rounded-lg">
                                <ShieldAlert size={24} />
                            </div>
                            <h3 className="font-bold text-lg">{fund.track_name || 'פוליסת ביטוח'}</h3>
                        </div>
                        <div className="flex items-center gap-2">
                           <span className="bg-green-500/10 text-green-400 border border-green-500/20 text-xs font-semibold px-2.5 py-1 rounded-full">פעיל</span>
                           <button onClick={(e) => { e.stopPropagation(); handleDeleteFund(fund.id); }} className="text-slate-500 hover:text-red-400 p-1 transition-colors" title="מחק פוליסה">
                               <Trash2 size={16} />
                           </button>
                        </div>
                        </div>
                    </div>
                    <div className="p-6 py-4 flex-1 space-y-3.5">
                        <div className="flex justify-between text-sm pb-2 border-b border-slate-700/30">
                            <span className="text-slate-400">חברה:</span>
                            <span className="font-bold text-slate-200">{fund.provider_name || fund.provider || 'לא צוין'}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-slate-400">שם המבוטח:</span>
                            <span className="font-medium text-slate-200">{fund.owner_name || 'לא ידוע'}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-slate-400">מספר פוליסה:</span>
                            <span className="font-medium text-white bg-slate-700/50 px-2 rounded">{fund.policy_number || 'לא קיים'}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-slate-400">פרמיה:</span>
                            <span className="font-semibold text-white">
                                ₪{Number((fund.premium_type === 'שנתית' ? fund.original_premium : fund.monthly_deposit) || 0).toLocaleString()} 
                                <span className="text-xs font-normal text-slate-500">
                                    {fund.premium_type === 'שנתית' ? ' / לשנה' : ' / לחודש'}
                                </span>
                            </span>
                        </div>
                        <div className="flex justify-between text-sm">
                            <span className="text-slate-400">תאריך תפוגה:</span>
                            <span className="font-medium text-slate-200">{fund.expiration_date || 'לא צוין'}</span>
                        </div>
                        <div className="flex justify-between text-sm items-center mt-4 pt-4 border-t border-slate-700/50">
                            <span className="text-slate-400 font-medium">מסמך מקור:</span>
                            {fund.source_document_url ? (
                                <a href={fund.source_document_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 font-bold text-blue-400 hover:text-blue-300 transition-colors underline decoration-blue-500/30">
                                    <FileText size={14} />
                                    צפה במסמך
                                </a>
                            ) : (
                                <button 
                                  onClick={() => {
                                    setSelectedPolicy({ id: fund.id, name: fund.track_name || 'פוליסת ביטוח' });
                                    setIsUploadModalOpen(true);
                                  }}
                                  className="inline-flex items-center gap-1.5 font-bold text-amber-500 hover:text-amber-400 transition-colors"
                                >
                                    <Upload size={14} />
                                    העלאת פוליסה
                                </button>
                            )}
                        </div>
                    </div>
                    <div className="p-4 bg-slate-800/80 border-t border-slate-700/50 flex gap-2">
                        <button 
                            disabled={comparingId === fund.id}
                            onClick={() => handleCompare(fund.id || fund.policy_number)}
                            className="flex-1 inline-flex items-center justify-center gap-2 text-sm font-medium bg-indigo-600/20 text-indigo-300 hover:bg-indigo-600/40 py-2 rounded transition-colors"
                        >
                            {comparingId === fund.id ? <Loader2 size={16} className="animate-spin" /> : <MessageCircle size={16} />}
                            השווה והפק הודעה
                        </button>
                    </div>
                </div>
            ))}

            {/* Empty State visual */}
            {filteredFunds.length === 0 && (
                <div className="col-span-full py-12 flex flex-col items-center justify-center bg-slate-800/50 rounded-2xl border border-dashed border-slate-700">
                    <div className="bg-slate-700/50 p-4 rounded-full text-slate-400 mb-4">
                        <FileText size={32} />
                    </div>
                    <p className="text-slate-400 font-medium">לא נמצאו פוליסות בקטגוריית "{activeTab}"</p>
                    <p className="text-slate-500 text-sm mt-1">נסה להעלות מסמך הר ביטוח לקבלת תמונה מלאה</p>
                </div>
            )}
        </div>
      </div>

      {/* --- Compare WhatsApp Modal --- */}
      {compareDraft && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-slate-900 border border-emerald-900/50 rounded-2xl w-full max-w-xl overflow-hidden shadow-2xl relative">
                <button onClick={() => setCompareDraft(null)} className="absolute top-4 right-4 text-slate-400 hover:text-white">
                    <X size={20} />
                </button>
                <div className="p-6 bg-emerald-900/20 border-b border-emerald-900/50 flex items-center gap-3">
                    <div className="bg-emerald-500/20 text-emerald-400 p-2 rounded-lg">
                        <MessageCircle size={24} />
                    </div>
                    <div>
                        <h3 className="font-bold text-white text-lg">טיוטת הודעה לסוכן</h3>
                        <p className="text-sm text-slate-400">הודעה זו יוצרה אישית עבורך ע"י מנוע ה-AI למשא ומתן.</p>
                    </div>
                </div>
                <div className="p-6">
                    <div className="bg-slate-800 rounded-xl p-4 text-slate-200 leading-relaxed font-medium whitespace-pre-wrap border border-slate-700 text-sm">
                        {compareDraft}
                    </div>
                    <div className="mt-6 flex justify-end gap-3">
                        <button 
                            onClick={() => {
                                navigator.clipboard.writeText(compareDraft);
                                setCompareDraft(null);
                            }}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white px-5 py-2.5 rounded-lg font-medium transition-colors"
                        >
                            העתק טקסט וסגור
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
