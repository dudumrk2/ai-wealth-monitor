import { useState, useEffect } from 'react';
import { Building2, Shield, Plus, Calendar, ArrowUpRight, Clock, CheckCircle2, Wallet, TrendingUp, AlertTriangle } from 'lucide-react';
import type { AltProject, LeveragedPolicy } from '../types/alternative';
import AddAlternativeModal from '../components/dashboard/AddAlternativeModal';
import PolicyDetailsModal from '../components/dashboard/PolicyDetailsModal';
import ProjectDetailsModal from '../components/dashboard/ProjectDetailsModal';
import DashboardLayout from '../components/layout/DashboardLayout';
import { auth, db } from '../lib/firebase';
import { doc, getDoc } from 'firebase/firestore';

import { API_URL } from '../lib/api';
import { getMonthsElapsed } from '../utils/date';
import { formatCurrency } from '../utils/format';

export default function AltInvestmentsDashboard() {
  const [showExited, setShowExited] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState<LeveragedPolicy | null>(null);
  const [selectedProject, setSelectedProject] = useState<AltProject | null>(null);
  const [editingAsset, setEditingAsset] = useState<{ item: AltProject | LeveragedPolicy; type: 'real_estate' | 'policy' } | null>(null);

  const [projects, setProjects] = useState<AltProject[]>([]);
  const [policies, setPolicies] = useState<LeveragedPolicy[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [currentPrimeRate, setCurrentPrimeRate] = useState<number>(6.0);

  const fetchAlternativeData = async (silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      const user = auth.currentUser;
      if (!user) return;
      const token = await user.getIdToken();

      const [projectsRes, policiesRes] = await Promise.all([
        fetch(`${API_URL}/api/alternatives/projects`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        fetch(`${API_URL}/api/alternatives/leveraged-policies`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);

      if (projectsRes.ok) {
        const pData = await projectsRes.json();
        setProjects(pData);
      }
      if (policiesRes.ok) {
        const polData = await policiesRes.json();
        setPolicies(polData);
      }

      // Fetch prime rate from Firestore settings/financials
      try {
        const settingsDoc = await getDoc(doc(db, 'settings', 'financials'));
        if (settingsDoc.exists()) {
          const rate = settingsDoc.data()?.current_prime_rate;
          if (typeof rate === 'number' && rate > 0) {
            setCurrentPrimeRate(rate);
            console.log(`[AltDashboard] Prime rate loaded from Firestore: ${rate}%`);
          }
        }
      } catch (fsErr) {
        console.warn('[AltDashboard] Could not fetch prime rate from Firestore:', fsErr);
      }
    } catch (error) {
      console.error('Error fetching alt investments data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAlternativeData();
  }, []);

  const handleSaveAsset = async (data: AltProject | LeveragedPolicy, type: 'real_estate' | 'policy', file: File | null) => {
    try {
      const user = auth.currentUser;
      if (!user) return;
      const token = await user.getIdToken();

      let finalData = { ...data };

      if (file) {
        const formData = new FormData();
        formData.append('file', file);
        const uploadRes = await fetch(`${API_URL}/api/alternatives/upload-pdf`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: formData
        });
        
        if (uploadRes.ok) {
          const uData = await uploadRes.json();
          if (type === 'policy') {
            (finalData as LeveragedPolicy).pdfUrl = uData.url;
          } else if (type === 'real_estate') {
            (finalData as AltProject).pdfUrl = uData.url;
          }
        } else {
          console.error("PDF upload failed");
        }
      }

      const endpoint = type === 'real_estate' 
        ? `${API_URL}/api/alternatives/projects`
        : `${API_URL}/api/alternatives/leveraged-policies`;

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(finalData),
      });

      if (!res.ok) {
        throw new Error('Failed to save asset');
      }

      setEditingAsset(null);
      setIsModalOpen(false);
      // Refresh user interface
      await fetchAlternativeData(true);
    } catch (error) {
      console.error('Save error:', error);
      alert('אירעה שגיאה בשמירת הנתונים.');
    }
  };

  const handleEditAsset = (item: AltProject | LeveragedPolicy, type: 'real_estate' | 'policy') => {
    setEditingAsset({ item, type });
    setSelectedPolicy(null);
    setSelectedProject(null);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingAsset(null);
  };

  // --- MACRO CALCULATIONS ---
  const activeProjects = projects.filter(p => p.status === 'Active');
  const exitedProjects = projects.filter(p => p.status === 'Exited');

  const totalPolicyBalance = policies.reduce((sum, p) => sum + p.currentBalance, 0);
  
  // Projects: Sum original amount + accrued profit for active projects
  const totalActiveProjectsAmount = activeProjects.reduce((sum, p) => {
    const monthsElapsed = getMonthsElapsed(p.startDate);
    const yearlyProfit = p.originalAmount * (p.expectedReturn / 100);
    const accruedProfit = (yearlyProfit / 12) * monthsElapsed;
    return sum + p.originalAmount + accruedProfit;
  }, 0); 
  
  const totalActiveAssets = totalPolicyBalance + totalActiveProjectsAmount;
  const totalLiabilities = policies.reduce((sum, p) => sum + p.balloonLoanAmount, 0);
  const netEquity = totalActiveAssets - totalLiabilities;
  const realizedProfit = exitedProjects.reduce((sum, p) => sum + ((p.finalAmount || 0) - p.originalAmount), 0);

  return (
    <DashboardLayout onRefresh={() => fetchAlternativeData(false)} isRefreshing={isLoading}>
      <div className="max-w-7xl mx-auto w-full space-y-6 md:space-y-8" dir="rtl">
        {/* --- TOP BAR --- */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-700 to-indigo-600 dark:from-blue-400 dark:to-indigo-300">
              השקעות אלטרנטיביות
            </h1>
            <p className="text-slate-500 dark:text-slate-400 mt-1">תיק השקעות ריאלי, מינופים ופוליסות חיסכון</p>
          </div>
          
          <div className="flex items-center gap-4 bg-white dark:bg-slate-900 p-1.5 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <label
              onClick={() => setShowExited(v => !v)}
              className="flex items-center gap-3 cursor-pointer select-none px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-lg transition-colors"
            >
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">הצג השקעות שהסתיימו</span>
              <div className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${showExited ? 'bg-indigo-500' : 'bg-slate-300 dark:bg-slate-700'}`}>
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${showExited ? '-translate-x-6' : '-translate-x-1'}`} />
              </div>
            </label>
            <div className="w-px h-6 bg-slate-200 dark:bg-slate-800 mx-1"></div>
            <button 
              onClick={() => setIsModalOpen(true)}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition-all focus:ring-4 focus:ring-indigo-500/20 active:scale-95"
            >
              <Plus className="w-4 h-4" /> הוסף נכס
            </button>
          </div>
        </div>

        {/* --- LOADER --- */}
        {isLoading ? (
          <div className="flex items-center justify-center min-h-[400px]">
             <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500"></div>
          </div>
        ) : (
          <div className="space-y-8 animate-fade-in-up">
            {/* --- TIER 1: MACRO SUMMARY --- */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
              <div className="bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">סך נכסים פעילים (AUM)</p>
                  <p className="text-2xl font-bold text-slate-800 dark:text-slate-100">{formatCurrency(totalActiveAssets)}</p>
                </div>
                <div className="w-12 h-12 bg-blue-50 dark:bg-blue-900/30 rounded-xl flex items-center justify-center text-blue-600 dark:text-blue-400">
                  <Wallet className="w-6 h-6" />
                </div>
              </div>
              
              <div className="bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">התחייבויות (מינוף)</p>
                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{formatCurrency(totalLiabilities)}</p>
                </div>
                <div className="w-12 h-12 bg-red-50 dark:bg-red-900/30 rounded-xl flex items-center justify-center text-red-600 dark:text-red-400">
                  <AlertTriangle className="w-6 h-6" />
                </div>
              </div>

              <div className="bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">הון עצמי (Net Equity)</p>
                  <p className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">{formatCurrency(netEquity)}</p>
                </div>
                <div className="w-12 h-12 bg-indigo-50 dark:bg-indigo-900/30 rounded-xl flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                  <Building2 className="w-6 h-6" />
                </div>
              </div>

              <div className="bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">רווח ממומש (Realized)</p>
                  <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">+{formatCurrency(realizedProfit)}</p>
                </div>
                <div className="w-12 h-12 bg-emerald-50 dark:bg-emerald-900/30 rounded-xl flex items-center justify-center text-emerald-600 dark:text-emerald-400">
                  <TrendingUp className="w-6 h-6" />
                </div>
              </div>
            </div>

            {/* --- TIER 2: POLICIES (LEVERAGE) --- */}
            {policies.length > 0 && (
              <>
                <div className="flex items-center justify-between mb-4 mt-8">
                  <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
                    <Shield className="w-5 h-5 text-indigo-500" /> פוליסות חיסכון ומינופים
                  </h2>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-10">
                  {policies.map(policy => {
                    const ltvPct = Math.min(100, Math.round((policy.balloonLoanAmount / policy.currentBalance) * 100));
                    const isHighRisk = ltvPct > 70;
                    
                    return (
                      <div
                        key={policy.id}
                        onClick={() => setSelectedPolicy(policy)}
                        className="bg-white dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden group cursor-pointer hover:border-indigo-400 dark:hover:border-indigo-600 hover:shadow-md hover:shadow-indigo-500/10 transition-all duration-200"
                      >
                        <div className="absolute top-0 right-0 p-4">
                           <a href={policy.funderLink} target="_blank" rel="noreferrer" className="text-slate-400 hover:text-indigo-500 transition-colors">
                             <ArrowUpRight className="w-5 h-5" />
                           </a>
                        </div>
                        <div className="flex gap-4 items-start">
                          <div className="w-12 h-12 bg-slate-50 dark:bg-slate-800 rounded-xl flex items-center justify-center shrink-0">
                            <Shield className="w-6 h-6 text-slate-600 dark:text-slate-400" />
                          </div>
                          <div className="flex-1 w-full">
                            <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100 mb-4">{policy.name}</h3>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                              <div>
                                <p className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">שווי קופה</p>
                                <p className="font-bold text-slate-800 dark:text-slate-200">{formatCurrency(policy.currentBalance)}</p>
                              </div>
                              <div>
                                <p className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">הלוואת בלון</p>
                                <p className="font-bold text-red-600 dark:text-red-400">{formatCurrency(policy.balloonLoanAmount)}</p>
                              </div>
                              <div>
                                <p className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">הפקדה מקורית</p>
                                <p className="font-semibold text-slate-600 dark:text-slate-300">{formatCurrency(policy.initialDepositAmount || 0)}</p>
                              </div>
                              <div>
                                <p className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">רווח/הפסד נומינלי</p>
                                <p className={`font-bold ${policy.currentBalance - (policy.initialDepositAmount || 0) >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                                  {policy.currentBalance - (policy.initialDepositAmount || 0) >= 0 ? '+' : ''}
                                  {formatCurrency(policy.currentBalance - (policy.initialDepositAmount || 0))}
                                </p>
                              </div>
                            </div>
                            
                            {/* LTV Progress Bar */}
                            <div>
                              <div className="flex justify-between items-center mb-2">
                                 <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">חשיפה (LTV)</span>
                                 <span className={`text-xs font-bold ${isHighRisk ? 'text-red-500' : 'text-slate-700 dark:text-slate-300'}`}>{ltvPct}%</span>
                              </div>
                              <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2.5 overflow-hidden flex">
                                <div className={`h-2.5 rounded-full transition-all duration-1000 ${isHighRisk ? 'bg-red-500' : 'bg-indigo-500'}`} style={{ width: `${ltvPct}%` }}></div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            {/* --- TIER 3: PROJECTS (TIMELINE) --- */}
            {projects.length > 0 ? (
              <>
                <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2 mb-4 mt-8">
                  <Building2 className="w-5 h-5 text-indigo-500" /> פרויקטי נדל"ן (סטטוס)
                </h2>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {(showExited ? projects : activeProjects).map(project => {
                    const isExited = project.status === 'Exited';
                    const monthsElapsed = getMonthsElapsed(project.startDate);
                    const progressPct = Math.min(100, Math.max(0, (monthsElapsed / project.durationMonths) * 100));
                    
                    return (
                      <div
                        key={project.id || project.name}
                        onClick={() => setSelectedProject(project)}
                        className={`bg-white dark:bg-slate-900 rounded-2xl p-6 border cursor-pointer transition-all duration-200 ${
                          isExited
                            ? 'border-dashed border-slate-300 dark:border-slate-700 opacity-80 mix-blend-luminosity hover:opacity-100'
                            : 'border-slate-200 dark:border-slate-800 shadow-sm hover:border-emerald-400 dark:hover:border-emerald-600 hover:shadow-md hover:shadow-emerald-500/10'
                        } relative`}
                      >
                        {isExited && (
                          <div className="absolute left-6 top-6 px-3 py-1 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-xs font-bold rounded-lg flex items-center gap-1.5 border border-slate-200 dark:border-slate-700">
                            <CheckCircle2 className="w-3.5 h-3.5" /> אקזיט
                          </div>
                        )}

                        <div className="mb-5">
                          <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100 leading-tight">{project.name}</h3>
                          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">{project.developer}</p>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                          <div>
                            <p className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">סכום השקעה</p>
                            <p className="font-bold text-slate-800 dark:text-slate-200">{formatCurrency(project.originalAmount, project.currency)}</p>
                          </div>
                          <div>
                            <p className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">תשואה צפויה (%)</p>
                            <p className="font-bold text-emerald-600 dark:text-emerald-400" dir="ltr">{project.expectedReturn.toFixed(1)}%</p>
                          </div>
                          {!isExited && (
                            <>
                              <div>
                                <p className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">רווח צפוי (סה"כ)</p>
                                <p className="font-bold text-indigo-600 dark:text-indigo-400">
                                  {formatCurrency(project.originalAmount * (project.expectedReturn / 100) * (project.durationMonths / 12), project.currency)}
                                </p>
                              </div>
                              <div>
                                <p className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">שווי משוער כיום</p>
                                <p className="font-bold text-blue-600 dark:text-blue-400">
                                  {formatCurrency(
                                    project.originalAmount + 
                                    (project.originalAmount * (project.expectedReturn / 100) * (getMonthsElapsed(project.startDate) / 12)), 
                                    project.currency
                                  )}
                                </p>
                              </div>
                            </>
                          )}
                          {isExited && (
                            <div className="col-span-2">
                               <p className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">רווח סופי ממומש</p>
                               <p className="font-bold text-emerald-600 dark:text-emerald-400">
                                  {formatCurrency((project.finalAmount || 0) - project.originalAmount, project.currency)}
                               </p>
                            </div>
                          )}
                        </div>

                        {/* Dynamic Bottom Area */}
                        {isExited ? (
                          <div className="bg-slate-50 dark:bg-slate-800/80 rounded-xl p-4 flex justify-between items-center">
                            <div>
                              <p className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">תאריך יציאה בפועל</p>
                              <p className="text-sm font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5"><Calendar className="w-3.5 h-3.5" /> {project.actualExitDate}</p>
                            </div>
                            <div className="text-left">
                              <p className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">החזר בפועל</p>
                              <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400">{formatCurrency(project.finalAmount || 0, project.currency)}</p>
                            </div>
                          </div>
                        ) : (
                          <div className="mt-2">
                            <div className="flex justify-between items-center mb-2">
                              <span className="text-xs font-semibold flex items-center gap-1.5 text-slate-600 dark:text-slate-400"><Clock className="w-3.5 h-3.5" /> חלפו {monthsElapsed} חודשים (מתוך {project.durationMonths})</span>
                            </div>
                            <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2.5 overflow-hidden flex">
                                <div className="h-2.5 rounded-full transition-all duration-1000 bg-emerald-500" style={{ width: `${progressPct}%` }}></div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            ) : null}

            {/* Empty State */}
            {projects.length === 0 && policies.length === 0 && (
              <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 p-10 text-center flex flex-col items-center justify-center shadow-sm py-20 mt-10">
                <div className="w-20 h-20 bg-indigo-50 dark:bg-indigo-900/30 rounded-full flex items-center justify-center mb-6">
                  <Building2 className="w-10 h-10 text-indigo-500" />
                </div>
                <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-3">אין נכסים אלטרנטיביים למעקב</h2>
                <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto mb-8 leading-relaxed">
                  תיק ההשקעות ופוליסות המינוף שלך ריק כרגע. תוכל להוסיף אותם על ידי לחיצה על כפתור התוספת למעלה.
                </p>
                <button
                  onClick={() => setIsModalOpen(true)}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold transition-all shadow-lg hover:shadow-indigo-500/25"
                >
                  <Plus className="w-5 h-5" />
                  הוסף נכס ריאלי ראשון
                </button>
              </div>
            )}
          </div>
        )}

        <AddAlternativeModal 
          isOpen={isModalOpen}
          onClose={handleCloseModal}
          onSave={handleSaveAsset}
          editData={editingAsset}
        />

        {selectedPolicy && (
          <PolicyDetailsModal
            policy={selectedPolicy}
            currentPrimeRate={currentPrimeRate}
            onClose={() => setSelectedPolicy(null)}
            onEdit={(p) => handleEditAsset(p, 'policy')}
          />
        )}

        {selectedProject && (
          <ProjectDetailsModal
            project={selectedProject}
            onClose={() => setSelectedProject(null)}
            onEdit={(p) => handleEditAsset(p, 'real_estate')}
          />
        )}


      </div>
    </DashboardLayout>
  );
}
