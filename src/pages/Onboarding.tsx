import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { STORAGE_KEYS } from '../lib/storageKeys';
import { createFamily } from '../lib/familyService';
import { useAuth } from '../context/AuthContext';
import { Users, Plus, CheckCircle2, ChevronLeft, AlertCircle, Trash2, UserCircle2, AlertTriangle } from 'lucide-react';

interface FamilyMember {
  name: string;
  email: string;
  lastName?: string;
  idNumber?: string;
}

export default function Onboarding() {
  const navigate = useNavigate();
  const { user, refreshFamily } = useAuth();
  const [householdName, setHouseholdName] = useState('');
  const [member1, setMember1] = useState<FamilyMember>({ name: '', email: '', lastName: '', idNumber: '' });
  const [member2, setMember2] = useState<FamilyMember>({ name: '', email: '', lastName: '', idNumber: '' });
  const [extraEmails, setExtraEmails] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    const savedData = localStorage.getItem(STORAGE_KEYS.ONBOARDING_DRAFT);
    if (savedData) {
      try {
        const parsed = JSON.parse(savedData);
        if (parsed.householdName) setHouseholdName(parsed.householdName);
        if (parsed.member1) setMember1(parsed.member1);
        if (parsed.member2) setMember2(parsed.member2);
        if (parsed.extraEmails) setExtraEmails(parsed.extraEmails);
      } catch (e) {
        console.error('Error loading onboarding draft:', e);
      }
    }
    setIsLoaded(true);
  }, []);

  // Save to localStorage on change
  useEffect(() => {
    if (!isLoaded) return;
    const dataToSave = {
      householdName,
      member1,
      member2,
      extraEmails
    };
    localStorage.setItem(STORAGE_KEYS.ONBOARDING_DRAFT, JSON.stringify(dataToSave));
  }, [householdName, member1, member2, extraEmails, isLoaded]);

  const handleAddEmail = () => setExtraEmails([...extraEmails, '']);
  const handleExtraEmailChange = (index: number, value: string) => {
    const updated = [...extraEmails];
    updated[index] = value;
    setExtraEmails(updated);
  };
  const handleRemoveEmail = (index: number) => setExtraEmails(extraEmails.filter((_, i) => i !== index));

  const handleCompleteSetup = async () => {
    setSaving(true);
    setError(null);

    const config = {
      householdName: householdName || 'המשפחה שלנו',
      member1: {
        name: member1.name || 'בעל/ת הבית',
        email: member1.email,
        lastName: member1.lastName,
        idNumber: member1.idNumber,
      },
      member2: {
        name: member2.name || 'בן/בת הזוג',
        email: member2.email,
        lastName: member2.lastName,
        idNumber: member2.idNumber,
      },
      extraAuthorizedEmails: extraEmails.filter(e => e.trim() !== ''),
      completedAt: new Date().toISOString(),
    };

    try {
      await createFamily(user!.uid, config);
      await refreshFamily(); // update AuthContext in-memory state
      localStorage.removeItem(STORAGE_KEYS.ONBOARDING_DRAFT); // Clear draft after success
      navigate('/dashboard');
    } catch (err: any) {
      if (err?.message === 'USER_ALREADY_IN_FAMILY' || err?.message === 'EMAIL_ALREADY_IN_FAMILY') {
        // User already has a family — just go to dashboard
        localStorage.setItem(STORAGE_KEYS.ONBOARDING_DONE, 'true');
        navigate('/dashboard');
      } else {
        console.error('createFamily error:', err);
        setError('אירעה שגיאה בשמירת ההגדרות. נסה שוב.');
        setSaving(false);
      }
    }
  };

  const isValid = member1.name.trim() !== '' && member2.name.trim() !== '';

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center py-12 px-4">
      <div className="w-full max-w-2xl bg-white rounded-3xl shadow-xl border border-slate-200 overflow-hidden">

        {/* Header */}
        <div className="bg-gradient-to-l from-blue-600 to-blue-800 p-8 text-white relative overflow-hidden">
          <div className="absolute left-0 top-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 -translate-x-1/3 pointer-events-none"></div>
          <div className="relative z-10 flex items-center gap-4 mb-5">
            <div className="bg-white/20 p-3 rounded-2xl backdrop-blur-sm">
              <Users className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">הגדרת המשפחה</h1>
              <p className="text-blue-100 mt-1">הגדר את שמות בני הבית שיופיעו בלוח הבקרה</p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-8 space-y-8">

          {/* Error banner */}
          {error && (
            <div className="flex items-start gap-3 p-4 bg-red-50 text-red-800 rounded-2xl border border-red-100">
              <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
              <p className="text-sm font-medium">{error}</p>
            </div>
          )}

          {/* Household Name */}
          <div className="space-y-2">
            <label className="block text-sm font-semibold text-slate-700 mb-2">שם הבית / המשפחה</label>
            <input
              type="text"
              placeholder='לדוגמה: משפחת לוי'
              value={householdName}
              onChange={e => setHouseholdName(e.target.value)}
              className="w-full border border-slate-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-shadow text-right placeholder:text-slate-400"
            />
          </div>

          {/* Security note */}
          <div className="flex items-start gap-3 p-4 bg-blue-50 text-blue-800 rounded-2xl border border-blue-100">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <p className="text-sm">השמות שתזין כאן יופיעו כשמות הלשוניות בלוח הבקרה. חשבונות ה-Google המורשים יקבעו מי יכול להתחבר.</p>
          </div>

          {/* Member 1 */}
          <div className="border border-slate-200 rounded-2xl p-5 space-y-4 bg-slate-50/50">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-blue-100 flex items-center justify-center">
                <UserCircle2 className="w-5 h-5 text-blue-600" />
              </div>
              <h3 className="font-bold text-slate-800">בן/בת משפחה ראשון/ה (אתה)</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1.5">שם פרטי (לתצוגה בלוח הבקרה)</label>
                <input type="text" placeholder='לדוגמה: דוד' value={member1.name}
                  onChange={e => setMember1({ ...member1, name: e.target.value })}
                  className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-right placeholder:text-slate-400 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1.5">שם משפחה</label>
                <input type="text" placeholder='לדוגמה: ישראלי' value={member1.lastName || ''}
                  onChange={e => setMember1({ ...member1, lastName: e.target.value })}
                  className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-right placeholder:text-slate-400 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1.5">תעודת זהות</label>
                <input type="text" placeholder='לדוגמה: 012345678' value={member1.idNumber || ''}
                  onChange={e => setMember1({ ...member1, idNumber: e.target.value })}
                  dir="ltr"
                  className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-left placeholder:text-slate-400 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1.5">כתובת Google (אימייל)</label>
                <input type="email" placeholder='david@gmail.com' value={member1.email}
                  onChange={e => setMember1({ ...member1, email: e.target.value })}
                  dir="ltr"
                  className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-left placeholder:text-slate-400 text-sm"
                />
              </div>
            </div>
          </div>

          {/* Member 2 */}
          <div className="border border-slate-200 rounded-2xl p-5 space-y-4 bg-slate-50/50">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center">
                <UserCircle2 className="w-5 h-5 text-emerald-600" />
              </div>
              <h3 className="font-bold text-slate-800">בן/בת משפחה שני/ה (בן/בת זוג)</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1.5">שם פרטי (לתצוגה בלוח הבקרה)</label>
                <input type="text" placeholder='לדוגמה: מירי' value={member2.name}
                  onChange={e => setMember2({ ...member2, name: e.target.value })}
                  className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-right placeholder:text-slate-400 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1.5">שם משפחה</label>
                <input type="text" placeholder='לדוגמה: ישראלי' value={member2.lastName || ''}
                  onChange={e => setMember2({ ...member2, lastName: e.target.value })}
                  className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-right placeholder:text-slate-400 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1.5">תעודת זהות</label>
                <input type="text" placeholder='לדוגמה: 012345678' value={member2.idNumber || ''}
                  onChange={e => setMember2({ ...member2, idNumber: e.target.value })}
                  dir="ltr"
                  className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-left placeholder:text-slate-400 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1.5">כתובת Google (אימייל)</label>
                <input type="email" placeholder='miri@gmail.com' value={member2.email}
                  onChange={e => setMember2({ ...member2, email: e.target.value })}
                  dir="ltr"
                  className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-left placeholder:text-slate-400 text-sm"
                />
              </div>
            </div>
          </div>

          {/* Additional authorized emails */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="block text-sm font-semibold text-slate-700">גישה נוספת (ילדים / מטפל פיננסי)</label>
              <span className="text-xs text-slate-400">רשות</span>
            </div>
            <div className="space-y-3">
              {extraEmails.map((email, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="flex-1 relative">
                    <input type="email" placeholder='extra@gmail.com' value={email}
                      onChange={e => handleExtraEmailChange(i, e.target.value)}
                      dir="ltr"
                      className="w-full border border-slate-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none text-left placeholder:text-slate-400 text-sm"
                    />
                    {email && <CheckCircle2 className="absolute left-3 top-3 w-4 h-4 text-emerald-500" />}
                  </div>
                  <button onClick={() => handleRemoveEmail(i)} className="p-2 text-slate-400 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
            <button onClick={handleAddEmail} className="mt-3 flex items-center gap-2 text-sm font-semibold text-blue-600 hover:text-blue-700 transition-colors">
              <Plus className="w-4 h-4" /> הוסף גישה נוספת
            </button>
          </div>

          <hr className="border-slate-200" />

          {/* Submit */}
          <div className="flex justify-between items-center">
            <p className="text-xs text-slate-400">ניתן לשנות הגדרות אלה בכל עת בעמוד ההגדרות</p>
            <button
              onClick={handleCompleteSetup}
              disabled={!isValid || saving}
              className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed text-white px-8 py-3.5 rounded-xl font-semibold transition-all transform active:scale-95 shadow-lg shadow-slate-900/20"
            >
              {saving ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <ChevronLeft className="w-4 h-4" />
              )}
              {saving ? 'שומר...' : 'סיום הגדרה'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
