import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { deleteFamily, addAuthorizedEmail } from '../lib/familyService';
import { STORAGE_KEYS } from '../lib/storageKeys';
import { Trash2, AlertTriangle, Users, UserCircle2, Mail, ChevronRight, X, RefreshCw, Loader2, Link2, Settings2, Clock, Moon, Sun, Play, Activity } from 'lucide-react';
import UploadSection from '../components/dashboard/UploadSection';
import { useTheme } from '../context/ThemeContext';
import clsx from 'clsx';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function Settings() {
  const navigate = useNavigate();
  const { user, familyConfig, familyId } = useAuth();
  const { theme, toggleTheme } = useTheme();

  // Load family config — from context (Firestore-synced) or localStorage cache
  const config = familyConfig ?? (() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEYS.FAMILY_CONFIG);
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  })();

  // Delete confirmation modal state
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Reprocess advisory state
  const [isReprocessing, setIsReprocessing] = useState(false);
  const [reprocessMsg, setReprocessMsg] = useState<string | null>(null);

  // Add email state
  const [newEmail, setNewEmail] = useState('');
  const [addingEmail, setAddingEmail] = useState(false);
  const { refreshFamily } = useAuth();

  // Gmail settings state
  const [searchParams] = useSearchParams();
  const [gmailConnected, setGmailConnected] = useState<boolean | null>(null);
  const [gmailConnectedMember, setGmailConnectedMember] = useState<string | null>(null);
  const [gmailSender, setGmailSender] = useState('no-reply@surense.com');
  const [gmailSubject, setGmailSubject] = useState('דוח מצב ביטוח ופנסיה');
  const [cronDay, setCronDay] = useState(1);
  const [cronFreq, setCronFreq] = useState(3);
  const [lastFetched, setLastFetched] = useState<string | null>(null);
  const [gmailConnecting, setGmailConnecting] = useState(false);
  const [gmailSaving, setGmailSaving] = useState(false);
  const [gmailSaveMsg, setGmailSaveMsg] = useState<string | null>(null);
  const [gmailBannerMsg, setGmailBannerMsg] = useState<string | null>(null);
  const [gmailScanning, setGmailScanning] = useState(false);
  const [gmailScanMsg, setGmailScanMsg] = useState<string | null>(null);

  // Cron states
  const [cronFetchEmailsEnabled, setCronFetchEmailsEnabled] = useState(true);
  const [cronStockPricesEnabled, setCronStockPricesEnabled] = useState(true);
  const [cronWeeklySummaryEnabled, setCronWeeklySummaryEnabled] = useState(true);

  const [runningStockPrices, setRunningStockPrices] = useState(false);
  const [runningWeeklySummary, setRunningWeeklySummary] = useState(false);
  const [runningFunderYields, setRunningFunderYields] = useState(false);
  const [cronRunMsg, setCronRunMsg] = useState<string | null>(null);

  const updateCronStatus = async (key: string, value: boolean) => {
    if (!user) return;
    try {
      const idToken = await user.getIdToken();
      await fetch(`${API_URL}/api/settings/gmail`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${idToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value }),
      });
    } catch { /* ignore */ }
  };

  // Load Gmail settings from backend on mount + handle OAuth return
  useEffect(() => {
    const gmailParam = searchParams.get('gmail');
    if (gmailParam === 'connected') setGmailBannerMsg('✅ Gmail חובר בהצלחה!');
    else if (gmailParam === 'denied') setGmailBannerMsg('⚠️ לא חיברת את Gmail — תוכל לחבר בכל עת.');
    else if (gmailParam === 'error') setGmailBannerMsg('❌ שגיאה בחיבור Gmail. נסה שנית.');

    const load = async () => {
      if (!user) return;
      try {
        const idToken = await user.getIdToken();
        const res = await fetch(`${API_URL}/api/settings/gmail`, {
          headers: { Authorization: `Bearer ${idToken}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        setGmailConnected(data.gmail_connected);
        setGmailConnectedMember(data.gmail_connected_member ?? null);
        setGmailSender(data.gmail_sender_email ?? 'no-reply@surense.com');
        setGmailSubject(data.gmail_subject ?? 'דוח מצב ביטוח ופנסיה');
        setCronDay(data.cron_day ?? 1);
        setCronFreq(data.cron_frequency_months ?? 3);
        setLastFetched(data.last_fetched_at ?? null);
        setCronFetchEmailsEnabled(data.cron_fetch_emails_enabled ?? true);
        setCronStockPricesEnabled(data.cron_stock_prices_enabled ?? true);
        setCronWeeklySummaryEnabled(data.cron_weekly_summary_enabled ?? true);
      } catch { /* silent */ }
    };
    load();
  }, [user, searchParams]);

  const handleConnectGmail = async (memberId: string) => {
    if (!user) return;
    setGmailConnecting(true);
    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/auth/gmail/url?member=${memberId}`, {
        headers: { Authorization: `Bearer ${idToken}` },
      });
      const data = await res.json();
      if (data.url) window.location.href = data.url;
    } catch {
      setGmailBannerMsg('❌ שגיאה בהכנת קישור Gmail.');
    } finally {
      setGmailConnecting(false);
    }
  };

  const handleDisconnectGmail = async () => {
    if (!user) return;
    if (!window.confirm('האם אתה בטוח שברצונך לנתק את החשבון מקריאת מיילים? (עדיף להימנע אם אין סיבה מיוחדת)')) return;
    setGmailConnecting(true);
    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/settings/gmail`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${idToken}` },
      });
      if (res.ok) {
        setGmailConnected(false);
        setGmailConnectedMember(null);
        setGmailBannerMsg('✅ החשבון נותק בהצלחה');
      } else {
        setGmailBannerMsg('❌ שגיאה בניתוק החשבון');
      }
    } catch {
      setGmailBannerMsg('❌ שגיאה בניתוק החשבון');
    } finally {
      setGmailConnecting(false);
    }
  };

  const handleSaveGmailSettings = async () => {
    if (!user) return;
    setGmailSaving(true);
    setGmailSaveMsg(null);
    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/settings/gmail`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${idToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          gmail_sender_email: gmailSender,
          gmail_subject: gmailSubject,
          cron_day: cronDay,
          cron_frequency_months: cronFreq,
          cron_fetch_emails_enabled: cronFetchEmailsEnabled,
          cron_stock_prices_enabled: cronStockPricesEnabled,
          cron_weekly_summary_enabled: cronWeeklySummaryEnabled,
        }),
      });
      if (res.ok) setGmailSaveMsg('✅ ההגדרות נשמרו בהצלחה');
      else setGmailSaveMsg('❌ שגיאה בשמירה');
    } catch {
      setGmailSaveMsg('❌ שגיאה בשמירה');
    } finally {
      setGmailSaving(false);
    }
  };

  const handleScanNow = async () => {
    if (!user) return;
    setGmailScanning(true);
    setGmailScanMsg(null);
    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/settings/gmail/scan`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${idToken}` }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'שגיאה בסריקה');
      
      const processed = data?.result?.processed || 0;
      if (processed > 0) {
        setGmailScanMsg(`✅ הסריקה הסתיימה! נמצאו ועובדו ${processed} דוחות חדשים.`);
      } else {
        setGmailScanMsg('✅ הסריקה הסתיימה. לא נמצאו דוחות חדשים במייל זה.');
      }
    } catch (err: any) {
      setGmailScanMsg('❌ שגיאה בסריקה: ' + err.message);
    } finally {
      setGmailScanning(false);
    }
  };

  const handleRunStockPrices = async () => {
    if (!user) return;
    setRunningStockPrices(true);
    setCronRunMsg(null);
    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/settings/cron/update-stock-prices/run`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${idToken}` }
      });
      if (!res.ok) throw new Error('שגיאה בשרת');
      const data = await res.json();
      setCronRunMsg(`✅ מחירים עודכנו בהצלחה. ${data.result?.updated || 0} מניות התעדכנו.`);
    } catch (err: any) {
      setCronRunMsg('❌ שגיאה בעדכון מחירים: ' + err.message);
    } finally {
      setRunningStockPrices(false);
    }
  };

  const handleRunWeeklySummary = async () => {
    if (!user) return;
    setRunningWeeklySummary(true);
    setCronRunMsg(null);
    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/settings/cron/weekly-stock-summary/run`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${idToken}` }
      });
      if (!res.ok) throw new Error('שגיאה בשרת');
      setCronRunMsg('✅ דוח שבועי הופק ונשלח למייל בהצלחה.');
    } catch (err: any) {
      setCronRunMsg('❌ שגיאה בהפקת הדוח השבועי: ' + err.message);
    } finally {
      setRunningWeeklySummary(false);
    }
  };

  const handleRunFunderYields = async () => {
    if (!user) return;
    setRunningFunderYields(true);
    setCronRunMsg(null);
    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/settings/cron/update-funder-yields/run`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${idToken}` }
      });
      if (!res.ok) throw new Error('שגיאה בשרת');
      const data = await res.json();
      const updatedCount = data?.updatedPolices ?? 0;
      setCronRunMsg(`✅ יתרות אלטרנטיביות (פאנדר) עודכנו. ${updatedCount} פוליסות התעדכנו.`);
    } catch (err: any) {
      setCronRunMsg('❌ שגיאה בעדכון תשואות פאנדר: ' + err.message);
    } finally {
      setRunningFunderYields(false);
    }
  };

  const householdName = config?.householdName || 'המשפחה';
  const confirmNeeded = householdName;

  const handleDeleteFamily = async () => {
    if (!familyId || !user) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteFamily(familyId, user.uid);
      navigate('/login');
    } catch (err: any) {
      if (err?.message === 'NOT_FAMILY_OWNER') {
        setDeleteError('רק מנהל המשפחה יכול למחוק אותה.');
      } else {
        setDeleteError('אירעה שגיאה. נסה שוב.');
      }
      setDeleting(false);
    }
  };

  const handleAddEmail = async () => {
    if (!newEmail || !familyId || !user) return;
    setAddingEmail(true);
    try {
      await addAuthorizedEmail(familyId, user.uid, newEmail);
      setNewEmail('');
      await refreshFamily();
    } catch (err: any) {
      if (err?.message === 'NOT_FAMILY_OWNER') {
        alert('רק מנהל המשפחה יכול להוסיף רשאות גישה.');
      } else {
        alert('שגיאה בהוספת המייל.');
      }
    } finally {
      setAddingEmail(false);
    }
  };

  const handleReprocessAdvisory = async () => {
    if (!user) return;
    setIsReprocessing(true);
    setReprocessMsg(null);
    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/test-reprocess-advisory`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${idToken}` },
      });
      if (!res.ok) throw new Error('failed');
      setReprocessMsg('✅ ההמלצות רועננו בהצלחה מהדאטה הקיים!');
    } catch {
      setReprocessMsg('❌ שגיאה בריענון ההמלצות.');
    } finally {
      setIsReprocessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-200">

      {/* Header */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-6 py-4 flex items-center justify-between sticky top-0 z-20 shadow-sm">
        <button
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-2 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 font-medium text-sm transition-colors"
        >
          <ChevronRight className="w-4 h-4" /> חזרה ללוח הבקרה
        </button>
        <h1 className="font-bold text-slate-800 dark:text-slate-100 text-lg">הגדרות</h1>
        
        <div className="flex items-center gap-2">
        </div>
      </div>

      <div className="max-w-2xl mx-auto py-10 px-4 space-y-6">
        {/* 1. PDF Upload Card */}
        {user && <UploadSection user={user} onSuccess={() => {}} />}

        {/* 2. Family Details & Gmail Integration Card */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-xl flex items-center justify-center">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-slate-800 dark:text-slate-100 text-lg">פרטי המשפחה וקריאת מיילים</h2>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">ניהול בני הזוג וחיבור לקריאה אוטומטית של דוחות</p>
            </div>
          </div>
          
          <div className="p-6 space-y-6">
            
            {/* Banner (OAuth result) */}
            {gmailBannerMsg && (
              <div className={`flex items-start justify-between gap-3 px-4 py-3 rounded-xl text-sm font-medium ${
                gmailBannerMsg.startsWith('✅') ? 'bg-green-50 text-green-800' :
                gmailBannerMsg.startsWith('⚠️') ? 'bg-amber-50 text-amber-800' : 'bg-red-50 text-red-800'
              }`}>
                <span>{gmailBannerMsg}</span>
                <button onClick={() => setGmailBannerMsg(null)} className="shrink-0 opacity-60 hover:opacity-100"><X className="w-4 h-4" /></button>
              </div>
            )}

            {/* Household Name */}
            <div>
              <p className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-1">שם הבית</p>
              <p className="text-lg font-bold text-slate-900 dark:text-slate-100">{config?.householdName || '—'}</p>
            </div>

            {/* Members List */}
            <div className="space-y-3">
              {[
                { obj: config?.member1, key: 'member1' },
                { obj: config?.member2, key: 'member2' }
              ].map(({ obj, key }) => {
                if (!obj) return null;
                const isConnected = gmailConnected && gmailConnectedMember === key;
                const disableConnect = gmailConnected && !isConnected;

                return (
                  <div key={key} className={`p-4 rounded-xl border transition-colors ${isConnected ? 'bg-blue-50/50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800' : 'bg-slate-50 dark:bg-slate-800/50 border-slate-100 dark:border-slate-800'}`}>
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                         <UserCircle2 className={`w-10 h-10 shrink-0 ${isConnected ? 'text-blue-500' : 'text-slate-400 dark:text-slate-500'}`} />
                         <div>
                           <p className="font-bold text-slate-800 dark:text-slate-100 text-sm">{obj.name}</p>
                           <p className="text-xs text-slate-500 dark:text-slate-400" dir="ltr">{obj.email || '—'}</p>
                         </div>
                      </div>
                      
                      <div className="flex flex-wrap items-center gap-2 shrink-0">
                         {isConnected ? (
                            <>
                              <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1.5 bg-green-100 text-green-800 rounded-lg">
                                <Link2 className="w-3.5 h-3.5" /> Gmail מחובר לסריקה
                              </span>
                              <button 
                                onClick={handleDisconnectGmail}
                                disabled={gmailConnecting}
                                className="text-xs font-semibold px-3 py-1.5 bg-white border border-slate-200 text-red-600 rounded-lg hover:bg-red-50 disabled:opacity-50 transition-colors"
                              >
                                ניתוק
                              </button>
                            </>
                         ) : (
                            <button
                              onClick={() => handleConnectGmail(key)}
                              disabled={disableConnect || gmailConnecting}
                              className="flex items-center gap-2 text-xs font-semibold px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:bg-slate-400 transition-colors"
                            >
                              <Link2 className="w-3.5 h-3.5" /> 
                              {disableConnect ? 'חשבון אחר מחובר' : 'חבר ל-Gmail'}
                            </button>
                         )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Gmail Settings & Explanation (inline in Family) */}
            <div className="mt-6 pt-6 border-t border-slate-100 dark:border-slate-800 space-y-6">
              
              <div className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4">
                <p className="font-semibold text-slate-700 dark:text-slate-300 mb-1">למה אנחנו צריכים גישה ל-Gmail?</p>
                <p>כדי שנייצר המלצות עדכניות אנחנו צריכים את דוחות הפנסיה האחרונים שלכם. האפליקציה בודקת רק את תיבת המייל שחוברה, מחפשת מיילים מהכתובת והנושא שהוגדרו מטה, מחלצת את ה-PDF ולא נוגעת באף מייל אחר. <strong className="text-slate-800 dark:text-slate-200">ניתן לחבר רק חשבון אחד למשפחה בכל זמן נתון.</strong></p>
                {lastFetched && <p className="text-xs text-slate-400 dark:text-slate-500 mt-2 font-medium">קריאה אחרונה התבצעה ב: <span dir="ltr">{lastFetched}</span></p>}
              </div>

            </div>
          </div>
        </div>

        {/* 3. Gmail Search Settings Card */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center gap-3">
            <div className="w-9 h-9 bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-xl flex items-center justify-center">
              <Settings2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-slate-800 dark:text-slate-100 text-lg">הגדרות סריקת דוחות ממייל</h2>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">פרטי חיפוש ותזמונים (מתייחס לחשבון ה-Gmail המחובר)</p>
            </div>
          </div>
          
          <div className="p-6 space-y-6">
            
            {/* Search settings */}
            <div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">כתובת שולח הדוח</label>
                  <input
                    type="email"
                    value={gmailSender}
                    onChange={e => setGmailSender(e.target.value)}
                    className="w-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-3 py-2 text-sm text-left focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-slate-900 dark:text-slate-100"
                    dir="ltr"
                    placeholder="no-reply@surense.com"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">נושא המייל (Subject)</label>
                  <input
                    type="text"
                    value={gmailSubject}
                    onChange={e => setGmailSubject(e.target.value)}
                    className="w-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-3 py-2 text-sm text-right focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-slate-900 dark:text-slate-100"
                    placeholder="דוח מצב ביטוח ופנסיה"
                  />
                </div>
              </div>
            </div>

            {/* Schedule */}
            <div className="border-t border-slate-100 dark:border-slate-800 pt-5">
              <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300 font-semibold text-sm mb-4">
                <Clock className="w-4 h-4" /> תזמון קריאה
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">יום בחודש <span className="text-slate-400 dark:text-slate-500 font-normal">(1–30)</span></label>
                  <input
                    type="number" min={1} max={30}
                    value={cronDay}
                    onChange={e => setCronDay(Math.min(30, Math.max(1, Number(e.target.value))))}
                    className="w-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-3 py-2 text-sm text-center focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-slate-900 dark:text-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">כל כמה חודשים <span className="text-slate-400 dark:text-slate-500 font-normal">(1–12)</span></label>
                  <input
                    type="number" min={1} max={12}
                    value={cronFreq}
                    onChange={e => setCronFreq(Math.min(12, Math.max(1, Number(e.target.value))))}
                    className="w-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-3 py-2 text-sm text-center focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-slate-900 dark:text-slate-100"
                  />
                </div>
              </div>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-2">ברירת מחדל: ב-1 לחודש, כל 3 חודשים</p>
            </div>

            {/* Save and Scan buttons */}
            <div className="border-t border-slate-100 dark:border-slate-800 pt-5 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
              <div className="flex items-center gap-4">
                <button
                  onClick={handleSaveGmailSettings}
                  disabled={gmailSaving}
                  className="flex items-center gap-2 bg-slate-900 dark:bg-slate-100 dark:text-slate-900 hover:bg-black dark:hover:bg-white disabled:opacity-50 text-white px-5 py-2.5 rounded-xl font-semibold text-sm transition-all active:scale-95"
                >
                  {gmailSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  {gmailSaving ? 'שומר...' : 'שמור הגדרות מייל'}
                </button>
                {gmailSaveMsg && <span className={`text-xs font-bold ${gmailSaveMsg.startsWith('✅') ? 'text-green-600' : 'text-red-600'}`}>{gmailSaveMsg}</span>}
              </div>

              <div className="flex items-center justify-end gap-3 border-t sm:border-t-0 sm:border-r border-slate-100 dark:border-slate-800 pt-5 sm:pt-0 sm:pr-6 w-full sm:w-auto">
                {gmailScanMsg && <span className={`text-xs font-bold text-left leading-tight ${gmailScanMsg.startsWith('✅') ? 'text-green-600' : 'text-red-600'}`}>{gmailScanMsg}</span>}
                <button
                   onClick={handleScanNow}
                   disabled={gmailScanning || !gmailConnected}
                   className="flex items-center gap-2 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50 border border-blue-200 dark:border-blue-800 disabled:opacity-50 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all active:scale-95 shrink-0"
                >
                   {gmailScanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                   סרוק דוחות עכשיו
                </button>
              </div>
            </div>

          </div>
        </div>

        {/* 4. Reprocess Advisory Card */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-xl flex items-center justify-center">
              <RefreshCw className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-slate-800 dark:text-slate-100 text-lg">רענן המלצות AI</h2>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">מחשב מחדש המלצות על בסיס הנתונים השמורים — ללא העלאת קבצים</p>
            </div>
          </div>
          <div className="p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <p className="text-sm text-slate-500 dark:text-slate-400">מושך נתוני שוק עדכניים ומריץ את יועץ ה-AI על הפורטפוליו הנוכחי.</p>
            <div className="flex flex-col items-start sm:items-end gap-2 shrink-0">
              <button
                onClick={handleReprocessAdvisory}
                disabled={isReprocessing}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2.5 rounded-xl font-semibold text-sm transition-all active:scale-95"
              >
                {isReprocessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                {isReprocessing ? 'מחשב...' : 'רענן המלצות'}
              </button>
              {reprocessMsg && (
                <p className={`text-xs font-medium ${reprocessMsg.startsWith('✅') ? 'text-green-600' : 'text-red-600'}`}>
                  {reprocessMsg}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* 5. Authorized Emails */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400 rounded-xl flex items-center justify-center">
                <Mail className="w-5 h-5" />
              </div>
              <h2 className="font-bold text-slate-800 dark:text-slate-100 text-lg">גישה נוספת מורשית</h2>
            </div>
          </div>
          <div className="p-6">
            <div className="space-y-2 mb-6">
              {(config?.extraAuthorizedEmails?.length ?? 0) === 0 ? (
                <p className="text-sm text-slate-400 dark:text-slate-500">אין משתמשים נוספים בעלי הרשאת גישה לתיק.</p>
              ) : (
                config?.extraAuthorizedEmails.map((email: string, i: number) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-lg text-sm" dir="ltr">
                    <div className="flex items-center gap-3">
                      <Mail className="w-4 h-4 text-slate-400 dark:text-slate-500 shrink-0" />
                      <span className="text-slate-700 dark:text-slate-300 font-medium">{email}</span>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Add new email form */}
            <div className="pt-5 border-t border-slate-100 dark:border-slate-800 flex gap-3">
              <input
                type="email"
                value={newEmail}
                onChange={e => setNewEmail(e.target.value)}
                placeholder="הכנס כתובת Google..."
                className="flex-1 border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 text-left focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm placeholder:text-slate-400 dark:placeholder:text-slate-600 text-slate-900 dark:text-slate-100"
                dir="ltr"
                onKeyDown={(e) => { if (e.key === 'Enter') handleAddEmail(); }}
              />
              <button
                onClick={handleAddEmail}
                disabled={!newEmail.includes('@') || addingEmail}
                className="bg-slate-900 dark:bg-slate-100 dark:text-slate-900 hover:bg-black dark:hover:bg-white text-white px-5 py-2.5 rounded-xl font-semibold text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed shrink-0 flex items-center gap-2"
              >
                {addingEmail ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : 'הוסף'}
              </button>
            </div>
          </div>
        </div>

        {/* 6. Cron Jobs Card */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center gap-3">
            <div className="w-9 h-9 bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 rounded-xl flex items-center justify-center">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-slate-800 dark:text-slate-100 text-lg">ניהול תהליכי רקע (Cron Jobs)</h2>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">הפעל, הפסק, או הרץ ידנית את תהליכי הרקע</p>
            </div>
          </div>
          
          <div className="p-6 space-y-4">
            {cronRunMsg && (
              <div className={`p-3 rounded-xl text-sm font-semibold mb-4 ${cronRunMsg.startsWith('✅') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                {cronRunMsg}
              </div>
            )}
            
            {/* Cron 1: Emails */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="flex-1">
                <p className="font-semibold text-slate-800 dark:text-slate-100 text-sm">סריקת דוחות ביטוח חדשים</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">מחפש מיילים מהכתובת המוגדרת, מחלץ ומנתח PDF בעזרת AI</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <button
                  onClick={() => {
                    const next = !cronFetchEmailsEnabled;
                    setCronFetchEmailsEnabled(next);
                    updateCronStatus('cron_fetch_emails_enabled', next);
                  }}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${cronFetchEmailsEnabled ? 'bg-green-500' : 'bg-slate-300 dark:bg-slate-600'}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${cronFetchEmailsEnabled ? '-translate-x-6' : '-translate-x-1'}`} />
                </button>
                <div className="w-px h-6 bg-slate-200 dark:bg-slate-700 mx-1"></div>
                <button
                  onClick={handleScanNow}
                  disabled={gmailScanning || !gmailConnected}
                  className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors"
                >
                  {gmailScanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 text-blue-500" />}
                  הרץ עכשיו
                </button>
              </div>
            </div>

            {/* Cron 2: Stocks */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="flex-1">
                <p className="font-semibold text-slate-800 dark:text-slate-100 text-sm">עדכון מחירי מניות ושערי המרה</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">עדכון יומי של מחירי תיק המניות (משולב Bizportal ו-Yahoo Finance)</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <button
                  onClick={() => {
                    const next = !cronStockPricesEnabled;
                    setCronStockPricesEnabled(next);
                    updateCronStatus('cron_stock_prices_enabled', next);
                  }}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${cronStockPricesEnabled ? 'bg-green-500' : 'bg-slate-300 dark:bg-slate-600'}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${cronStockPricesEnabled ? '-translate-x-6' : '-translate-x-1'}`} />
                </button>
                <div className="w-px h-6 bg-slate-200 dark:bg-slate-700 mx-1"></div>
                <button
                  onClick={handleRunStockPrices}
                  disabled={runningStockPrices}
                  className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors"
                >
                  {runningStockPrices ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 text-blue-500" />}
                  הרץ עכשיו
                </button>
              </div>
            </div>

            {/* Cron 3: Weekly Summary */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="flex-1">
                <p className="font-semibold text-slate-800 dark:text-slate-100 text-sm">סיכום מניות שבועי מבוסס AI</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">ניתוח והפקה אוטומטית של דוח השקעות שבועי ישירות למייל (Gemini)</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <button
                  onClick={() => {
                    const next = !cronWeeklySummaryEnabled;
                    setCronWeeklySummaryEnabled(next);
                    updateCronStatus('cron_weekly_summary_enabled', next);
                  }}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${cronWeeklySummaryEnabled ? 'bg-green-500' : 'bg-slate-300 dark:bg-slate-600'}`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${cronWeeklySummaryEnabled ? '-translate-x-6' : '-translate-x-1'}`} />
                </button>
                <div className="w-px h-6 bg-slate-200 dark:bg-slate-700 mx-1"></div>
                <button
                  onClick={handleRunWeeklySummary}
                  disabled={runningWeeklySummary}
                  className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors"
                >
                  {runningWeeklySummary ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 text-blue-500" />}
                  הרץ עכשיו
                </button>
              </div>
            </div>

            {/* Cron 4: Funder Yields */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800">
              <div className="flex-1">
                <p className="font-semibold text-slate-800 dark:text-slate-100 text-sm">עדכון תשואות חודשיות (Funder)</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">סריקתו של אתר פאנדר לעדכון ריבית דריבית בפוליסות ומשאבי השקעה אלטרנטיביים</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <button
                  onClick={handleRunFunderYields}
                  disabled={runningFunderYields}
                  className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors"
                >
                  {runningFunderYields ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 text-blue-500" />}
                  הרץ עכשיו
                </button>
              </div>
            </div>

          </div>
        </div>

        {/* 7. Theme / Appearance Card */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center gap-3">
            <div className="w-9 h-9 bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 rounded-xl flex items-center justify-center">
              {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
            </div>
            <div>
              <h2 className="font-bold text-slate-800 dark:text-slate-100 text-lg">מראה (עיצוב)</h2>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">בחר בין מצב בהיר לכהה</p>
            </div>
          </div>
          <div className="p-6">
            <div className="flex items-center justify-between p-1 bg-slate-100 dark:bg-slate-800 rounded-xl w-full max-w-[300px]">
              <button
                onClick={() => theme !== 'light' && toggleTheme()}
                className={clsx(
                  "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-semibold transition-all",
                  theme === 'light' 
                    ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm" 
                    : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
                )}
              >
                <Sun className="w-4 h-4" /> מצב בהיר
              </button>
              <button
                onClick={() => theme !== 'dark' && toggleTheme()}
                className={clsx(
                  "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-semibold transition-all",
                  theme === 'dark' 
                    ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm" 
                    : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
                )}
              >
                <Moon className="w-4 h-4" /> מצב כהה
              </button>
            </div>
          </div>
        </div>

        {/* 7. Danger Zone */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-red-200 dark:border-red-900/50 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-red-100 dark:border-red-900/30 bg-red-50/50 dark:bg-red-900/10 flex items-center gap-3">
            <div className="w-9 h-9 bg-red-100 dark:bg-red-900/50 text-red-600 dark:text-red-400 rounded-xl flex items-center justify-center">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h2 className="font-bold text-red-800 dark:text-red-400 text-lg">אזור מסוכן</h2>
          </div>
          <div className="p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="font-semibold text-slate-900 dark:text-slate-100">מחיקת המשפחה</p>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">מחיקה בלתי הפיכה של כל נתוני המשפחה ומשתמשיה</p>
              </div>
              <button
                onClick={() => setShowDeleteModal(true)}
                className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white px-5 py-2.5 rounded-xl font-semibold text-sm transition-all active:scale-95 shrink-0"
              >
                <Trash2 className="w-4 h-4" /> מחק משפחה
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ─── Delete Confirmation Modal ─── */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" dir="rtl">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="bg-red-50 dark:bg-red-900/20 p-6 border-b border-red-100 dark:border-red-900/30">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-red-100 dark:bg-red-900/50 rounded-xl flex items-center justify-center shrink-0">
                    <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-red-900 dark:text-red-100">מחיקת המשפחה</h3>
                    <p className="text-sm text-red-700 dark:text-red-300 mt-0.5">פעולה זו אינה ניתנת לביטול</p>
                  </div>
                </div>
                <button onClick={() => { setShowDeleteModal(false); setConfirmText(''); setDeleteError(null); }}
                  className="text-slate-400 hover:text-slate-600 transition-colors p-1">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="p-6 space-y-5">
              <p className="text-slate-700 dark:text-slate-300 text-sm leading-relaxed">
                פעולה זו תמחק לצמיתות את <strong>{householdName}</strong> ותנתק את כל המשתמשים המורשים.
                לא ניתן לשחזר את הנתונים.
              </p>

              <div>
                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
                  הקלד <span className="text-red-600 dark:text-red-400 font-bold">"{confirmNeeded}"</span> לאישור
                </label>
                <input
                  type="text"
                  value={confirmText}
                  onChange={e => setConfirmText(e.target.value)}
                  placeholder={confirmNeeded}
                  className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-3 text-right focus:ring-2 focus:ring-red-400 focus:border-red-400 outline-none transition-shadow placeholder:text-slate-300 dark:placeholder:text-slate-600 text-slate-900 dark:text-slate-100"
                  autoFocus
                />
              </div>

              {deleteError && (
                <p className="text-sm text-red-600 font-medium">{deleteError}</p>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => { setShowDeleteModal(false); setConfirmText(''); setDeleteError(null); }}
                  className="flex-1 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 px-4 py-3 rounded-xl font-semibold text-sm transition-colors"
                >
                  ביטול
                </button>
                <button
                  onClick={handleDeleteFamily}
                  disabled={confirmText !== confirmNeeded || deleting}
                  className="flex-1 bg-red-600 hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 py-3 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2"
                >
                  {deleting ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                  {deleting ? 'מוחק...' : 'מחק לצמיתות'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
