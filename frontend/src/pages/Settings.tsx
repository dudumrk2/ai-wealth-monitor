import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { deleteFamily, addAuthorizedEmail } from '../lib/familyService';
import { STORAGE_KEYS } from '../lib/storageKeys';
import { Trash2, AlertTriangle, Users, UserCircle2, Mail, Shield, ChevronRight, X, RefreshCw, Loader2 } from 'lucide-react';
import UploadSection from '../components/dashboard/UploadSection';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function Settings() {
  const navigate = useNavigate();
  const { user, familyConfig, familyId } = useAuth();

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
    <div className="min-h-screen bg-slate-50">

      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between sticky top-0 z-20 shadow-sm">
        <button
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-2 text-slate-600 hover:text-slate-900 font-medium text-sm transition-colors"
        >
          <ChevronRight className="w-4 h-4" /> חזרה ללוח הבקרה
        </button>
        <h1 className="font-bold text-slate-800 text-lg">הגדרות</h1>
        <div className="w-24" /> {/* spacer */}
      </div>

      <div className="max-w-2xl mx-auto py-10 px-4 space-y-6">

        {/* PDF Upload Card */}
        {user && <UploadSection user={user} onSuccess={() => {}} />}

        {/* Reprocess Advisory Card */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
              <RefreshCw className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-slate-800 text-lg">רענן המלצות AI</h2>
              <p className="text-xs text-slate-400 mt-0.5">מחשב מחדש המלצות על בסיס הנתונים השמורים — ללא העלאת קבצים</p>
            </div>
          </div>
          <div className="p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <p className="text-sm text-slate-500">מושך נתוני שוק עדכניים ומריץ את יועץ ה-AI על הפורטפוליו הנוכחי.</p>
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


        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
              <Users className="w-5 h-5" />
            </div>
            <h2 className="font-bold text-slate-800 text-lg">פרטי המשפחה</h2>
          </div>
          <div className="p-6 space-y-4">
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">שם הבית</p>
              <p className="text-lg font-bold text-slate-900">{config?.householdName || '—'}</p>
            </div>
            {config?.member1 && (
              <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-xl">
                <UserCircle2 className="w-5 h-5 text-blue-500 shrink-0" />
                <div>
                  <p className="font-semibold text-slate-800 text-sm">{config.member1.name}</p>
                  <p className="text-xs text-slate-500" dir="ltr">{config.member1.email || '—'}</p>
                </div>
              </div>
            )}
            {config?.member2 && (
              <div className="flex items-center gap-3 p-3 bg-emerald-50 rounded-xl">
                <UserCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                <div>
                  <p className="font-semibold text-slate-800 text-sm">{config.member2.name}</p>
                  <p className="text-xs text-slate-500" dir="ltr">{config.member2.email || '—'}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Authorized Emails */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-slate-50 text-slate-600 rounded-xl flex items-center justify-center">
                <Mail className="w-5 h-5" />
              </div>
              <h2 className="font-bold text-slate-800 text-lg">גישה נוספת מורשית</h2>
            </div>
          </div>
          <div className="p-6">
            <div className="space-y-2 mb-6">
              {(config?.extraAuthorizedEmails?.length ?? 0) === 0 ? (
                <p className="text-sm text-slate-400">אין משתמשים נוספים בעלי הרשאת גישה לתיק.</p>
              ) : (
                config?.extraAuthorizedEmails.map((email: string, i: number) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-100 rounded-lg text-sm" dir="ltr">
                    <div className="flex items-center gap-3">
                      <Mail className="w-4 h-4 text-slate-400 shrink-0" />
                      <span className="text-slate-700 font-medium">{email}</span>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Add new email form */}
            <div className="pt-5 border-t border-slate-100 flex gap-3">
              <input
                type="email"
                value={newEmail}
                onChange={e => setNewEmail(e.target.value)}
                placeholder="הכנס כתובת Google..."
                className="flex-1 border border-slate-300 rounded-xl px-4 py-2.5 text-left focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm placeholder:text-slate-400"
                dir="ltr"
                onKeyDown={(e) => { if (e.key === 'Enter') handleAddEmail(); }}
              />
              <button
                onClick={handleAddEmail}
                disabled={!newEmail.includes('@') || addingEmail}
                className="bg-slate-900 hover:bg-black text-white px-5 py-2.5 rounded-xl font-semibold text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed shrink-0 flex items-center gap-2"
              >
                {addingEmail ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : 'הוסף'}
              </button>
            </div>
          </div>
        </div>

        {/* Account Info */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-slate-100 flex items-center gap-3">
            <div className="w-9 h-9 bg-slate-50 text-slate-600 rounded-xl flex items-center justify-center">
              <Shield className="w-5 h-5" />
            </div>
            <h2 className="font-bold text-slate-800 text-lg">חשבון Google</h2>
          </div>
          <div className="p-6 flex items-center gap-4">
            <img
              src={user?.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(user?.email || 'U')}&background=3b82f6&color=fff`}
              className="w-12 h-12 rounded-full border border-slate-200"
              alt="פרופיל"
            />
            <div>
              <p className="font-semibold text-slate-900">{user?.displayName || 'משתמש'}</p>
              <p className="text-sm text-slate-500" dir="ltr">{user?.email}</p>
            </div>
          </div>
        </div>

        {/* Danger Zone */}
        <div className="bg-white rounded-2xl border border-red-200 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-red-100 bg-red-50/50 flex items-center gap-3">
            <div className="w-9 h-9 bg-red-100 text-red-600 rounded-xl flex items-center justify-center">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h2 className="font-bold text-red-800 text-lg">אזור מסוכן</h2>
          </div>
          <div className="p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="font-semibold text-slate-900">מחיקת המשפחה</p>
                <p className="text-sm text-slate-500 mt-0.5">מחיקה בלתי הפיכה של כל נתוני המשפחה ומשתמשיה</p>
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
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="bg-red-50 p-6 border-b border-red-100">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-red-100 rounded-xl flex items-center justify-center shrink-0">
                    <AlertTriangle className="w-5 h-5 text-red-600" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-red-900">מחיקת המשפחה</h3>
                    <p className="text-sm text-red-700 mt-0.5">פעולה זו אינה ניתנת לביטול</p>
                  </div>
                </div>
                <button onClick={() => { setShowDeleteModal(false); setConfirmText(''); setDeleteError(null); }}
                  className="text-slate-400 hover:text-slate-600 transition-colors p-1">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="p-6 space-y-5">
              <p className="text-slate-700 text-sm leading-relaxed">
                פעולה זו תמחק לצמיתות את <strong>{householdName}</strong> ותנתק את כל המשתמשים המורשים.
                לא ניתן לשחזר את הנתונים.
              </p>

              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  הקלד <span className="text-red-600 font-bold">"{confirmNeeded}"</span> לאישור
                </label>
                <input
                  type="text"
                  value={confirmText}
                  onChange={e => setConfirmText(e.target.value)}
                  placeholder={confirmNeeded}
                  className="w-full border border-slate-300 rounded-xl px-4 py-3 text-right focus:ring-2 focus:ring-red-400 focus:border-red-400 outline-none transition-shadow placeholder:text-slate-300"
                  autoFocus
                />
              </div>

              {deleteError && (
                <p className="text-sm text-red-600 font-medium">{deleteError}</p>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => { setShowDeleteModal(false); setConfirmText(''); setDeleteError(null); }}
                  className="flex-1 border border-slate-300 text-slate-700 hover:bg-slate-50 px-4 py-3 rounded-xl font-semibold text-sm transition-colors"
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
