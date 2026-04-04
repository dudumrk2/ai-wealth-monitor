import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { doc, setDoc, serverTimestamp } from 'firebase/firestore';
import { db } from '../lib/firebase';
import { STORAGE_KEYS } from '../lib/storageKeys';
import { useAuth } from '../context/AuthContext';
import { Users, Plus, CheckCircle2, ChevronLeft, AlertCircle, Trash2, UserCircle2, AlertTriangle, ArrowRight } from 'lucide-react';
import FinancialProfileStep from '../components/onboarding/FinancialProfileStep';

interface FamilyMember {
  name: string;
  email: string;
  lastName?: string;
  idNumber?: string;
}

interface FinancialData {
  spouse1BirthYear: string;
  spouse2BirthYear: string;
  kidsCount: number;
  childrenBirthYears: string[];
  investmentGoal: string;
  riskTolerance: string;
}

export default function Onboarding() {
  const navigate = useNavigate();
  const { user, refreshFamily } = useAuth();
  
  // Multi-step state
  const [step, setStep] = useState(1);
  const [step1Data, setStep1Data] = useState<any>(null);
  
  // Step 1: PII Basic Fields (maintained for UI binding)
  const [householdName, setHouseholdName] = useState('');
  const [member1, setMember1] = useState<FamilyMember>({ name: '', email: '', lastName: '', idNumber: '' });
  const [member2, setMember2] = useState<FamilyMember>({ name: '', email: '', lastName: '', idNumber: '' });
  const [extraEmails, setExtraEmails] = useState<string[]>([]);
  
  // Step 2: Financial Data Persistence
  const [financialData, setFinancialData] = useState<Partial<FinancialData>>({});
  
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    const savedData = localStorage.getItem(STORAGE_KEYS.ONBOARDING_DRAFT);
    if (savedData) {
      try {
        const parsed = JSON.parse(savedData);
        if (parsed.step) setStep(parsed.step);
        if (parsed.step1Data) setStep1Data(parsed.step1Data);
        if (parsed.householdName) setHouseholdName(parsed.householdName);
        if (parsed.member1) setMember1(parsed.member1);
        if (parsed.member2) setMember2(parsed.member2);
        if (parsed.extraEmails) setExtraEmails(parsed.extraEmails);
        if (parsed.financialData) setFinancialData(parsed.financialData);
      } catch (e) {
        console.error('Error loading onboarding draft:', e);
      }
    } else if (user?.email) {
      setMember1(prev => ({ ...prev, email: user.email! }));
    }
    setIsLoaded(true);
  }, [user]);

  // Save to localStorage on change
  useEffect(() => {
    if (!isLoaded) return;
    const dataToSave = {
      step,
      step1Data,
      householdName,
      member1,
      member2,
      extraEmails,
      financialData
    };
    localStorage.setItem(STORAGE_KEYS.ONBOARDING_DRAFT, JSON.stringify(dataToSave));
  }, [step, step1Data, householdName, member1, member2, extraEmails, financialData, isLoaded]);

  const handleAddEmail = () => setExtraEmails([...extraEmails, '']);
  const handleExtraEmailChange = (index: number, value: string) => {
    const updated = [...extraEmails];
    updated[index] = value;
    setExtraEmails(updated);
  };
  const handleRemoveEmail = (index: number) => setExtraEmails(extraEmails.filter((_, i) => i !== index));

  const handleNextStep = () => {
    // Collect and save Step 1 payload before transitioning
    const effectiveLastName1 = member1.lastName?.trim() || householdName || 'ישראלי';
    const effectiveLastName2 = member2.lastName?.trim() || householdName || 'ישראלי';

    const payload1 = {
      householdName: householdName || 'המשפחה שלנו',
      member1: {
        name: member1.name || 'בעל/ת הבית',
        email: member1.email,
        lastName: effectiveLastName1,
        idNumber: member1.idNumber,
      },
      member2: {
        name: member2.name || 'בן/בת הזוג',
        email: member2.email,
        lastName: effectiveLastName2,
        idNumber: member2.idNumber,
      },
      extraAuthorizedEmails: extraEmails.filter(e => e.trim() !== ''),
    };

    setStep1Data(payload1);
    setStep(2);
    window.scrollTo(0, 0);
  };

  const handleBackStep = () => {
    setStep(1);
    window.scrollTo(0, 0);
  };

  const handleFinancialDataChange = useCallback((data: Partial<FinancialData>) => {
    setFinancialData(prev => {
      if (JSON.stringify(prev) === JSON.stringify(data)) return prev;
      return data;
    });
  }, []);

  const handleCompleteFinancialProfile = async (step2Data: any) => {
    if (!user) return;
    setSaving(true);
    setError(null);

    const finalPayload = {
      pii_data: step1Data,
      financial_profile: step2Data,
      createdAt: serverTimestamp(),
      updatedAt: serverTimestamp()
    };

    try {
      // Save directly to Firestore as requested
      const familyRef = doc(db, 'families', user.uid);
      await setDoc(familyRef, finalPayload);
      
      // Also link the user in the 'users' collection for proper mapping and future lookups
      const userRef = doc(db, 'users', user.uid);
      await setDoc(userRef, {
        familyId: user.uid,
        email: user.email,
        joinedAt: serverTimestamp(),
      }, { merge: true });
      
      // Update local storage and navigate
      localStorage.setItem(STORAGE_KEYS.ONBOARDING_DONE, 'true');
      localStorage.removeItem(STORAGE_KEYS.ONBOARDING_DRAFT);
      
      await refreshFamily(); // Sync context
      navigate('/dashboard');
    } catch (err: any) {
      console.error('Final save error:', err);
      setError('אירעה שגיאה בשמירת הנתונים. נסה שוב.');
      setSaving(false);
    }
  };

  const isValidStep1 = member1.name.trim() !== '' && member2.name.trim() !== '';

  if (!isLoaded) return null;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col items-center py-12 px-4 transition-colors duration-200">
      <div className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-3xl shadow-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
        
        {/* Header */}
        <div className="bg-gradient-to-l from-blue-600 to-blue-800 p-8 text-white relative overflow-hidden">
          <div className="absolute left-0 top-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 -translate-x-1/3 pointer-events-none"></div>
          <div className="relative z-10 flex items-center gap-4 mb-2">
            <div className="bg-white/20 p-3 rounded-2xl backdrop-blur-sm">
              <Users className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">{step === 1 ? 'הגדרת המשפחה' : 'פרופיל פיננסי'}</h1>
              <p className="text-blue-100 mt-1">
                {step === 1 ? 'שלב 1: פרטים בסיסיים והרשאות' : 'שלב 2: נתונים לתכנון פיננסי אישי'}
              </p>
            </div>
          </div>
          {/* Progress Indicator */}
          <div className="relative z-10 mt-6 flex gap-2">
             <div className={`h-1.5 rounded-full flex-1 transition-all ${step >= 1 ? 'bg-white' : 'bg-white/30'}`}></div>
             <div className={`h-1.5 rounded-full flex-1 transition-all ${step >= 2 ? 'bg-white' : 'bg-white/30'}`}></div>
          </div>
        </div>

        {step === 1 ? (
          <div className="p-8 space-y-8 animate-in fade-in slide-in-from-left-4 duration-500">
            {error && (
              <div className="flex items-start gap-3 p-4 bg-red-50 text-red-800 rounded-2xl border border-red-100">
                <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                <p className="text-sm font-medium">{error}</p>
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="family_name" className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">שם הבית / המשפחה (למשל: משפחת לוי)</label>
              <input
                id="family_name"
                type="text"
                name="family_name"
                placeholder='לדוגמה: משפחת לוי'
                value={householdName}
                onChange={e => setHouseholdName(e.target.value)}
                className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-shadow text-right placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-slate-100"
                autoComplete="family-name"
              />
            </div>

            <div className="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 rounded-2xl border border-blue-100 dark:border-blue-800/50">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <p className="text-sm">השמות שתזין כאן יופיעו כשמות הלשוניות בלוח הבקרה. חשבונות ה-Google המורשים יקבעו מי יכול להתחבר.</p>
            </div>

            <div className="border border-slate-200 dark:border-slate-800 rounded-2xl p-5 space-y-4 bg-slate-50/50 dark:bg-slate-800/30">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center">
                  <UserCircle2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                </div>
                <h3 className="font-bold text-slate-800 dark:text-slate-100">בן/בת משפחה ראשון/ה (אתה)</h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="fname1" className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">שם פרטי</label>
                  <input id="fname1" type="text" name="fname1" placeholder='לדוגמה: דוד' value={member1.name}
                    onChange={e => setMember1({ ...member1, name: e.target.value })}
                    className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-right placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-slate-100 text-sm"
                    autoComplete="given-name"
                  />
                </div>
                <div>
                  <label htmlFor="lname1" className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">שם משפחה (אופציונלי)</label>
                  <input id="lname1" type="text" name="lname1" placeholder='לדוגמה: ישראלי' value={member1.lastName || ''}
                    onChange={e => setMember1({ ...member1, lastName: e.target.value })}
                    className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-right placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-slate-100 text-sm"
                    autoComplete="family-name"
                  />
                </div>
                <div>
                  <label htmlFor="id1" className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">תעודת זהות</label>
                  <input id="id1" type="text" name="id1" placeholder='לדוגמה: 012345678' value={member1.idNumber || ''}
                    onChange={e => setMember1({ ...member1, idNumber: e.target.value })}
                    dir="ltr"
                    className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-left placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-slate-100 text-sm"
                  />
                </div>
                <div>
                  <label htmlFor="email1" className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">כתובת Google (אימייל)</label>
                  <input id="email1" type="email" name="email1" placeholder='david@gmail.com' value={member1.email}
                    onChange={e => setMember1({ ...member1, email: e.target.value })}
                    dir="ltr"
                    className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-left placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-slate-100 text-sm"
                    autoComplete="email"
                  />
                </div>
              </div>
            </div>

            <div className="border border-slate-200 dark:border-slate-800 rounded-2xl p-5 space-y-4 bg-slate-50/50 dark:bg-slate-800/30">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-emerald-100 dark:bg-emerald-900/50 flex items-center justify-center">
                  <UserCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                </div>
                <h3 className="font-bold text-slate-800 dark:text-slate-100">בן/בת משפחה שני/ה (בן/בת זוג)</h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="fname2" className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">שם פרטי</label>
                  <input id="fname2" type="text" name="fname2" placeholder='לדוגמה: מירי' value={member2.name}
                    onChange={e => setMember2({ ...member2, name: e.target.value })}
                    className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-right placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-slate-100 text-sm"
                    autoComplete="given-name"
                  />
                </div>
                <div>
                  <label htmlFor="lname2" className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">שם משפחה (אופציונלי)</label>
                  <input id="lname2" type="text" name="lname2" placeholder='לדוגמה: ישראלי' value={member2.lastName || ''}
                    onChange={e => setMember2({ ...member2, lastName: e.target.value })}
                    className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-right placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-slate-100 text-sm"
                    autoComplete="family-name"
                  />
                </div>
                <div>
                  <label htmlFor="id2" className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">תעודת זהות</label>
                  <input id="id2" type="text" name="id2" placeholder='לדוגמה: 012345678' value={member2.idNumber || ''}
                    onChange={e => setMember2({ ...member2, idNumber: e.target.value })}
                    dir="ltr"
                    className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-left placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-slate-100 text-sm"
                  />
                </div>
                <div>
                  <label htmlFor="email2" className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">כתובת Google (אימייל)</label>
                  <input id="email2" type="email" name="email2" placeholder='miri@gmail.com' value={member2.email}
                    onChange={e => setMember2({ ...member2, email: e.target.value })}
                    dir="ltr"
                    className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-shadow text-left placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-slate-100 text-sm"
                    autoComplete="email"
                  />
                </div>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300">גישה נוספת (ילדים / מטפל פיננסי)</label>
                <span className="text-xs text-slate-400 dark:text-slate-500">רשות</span>
              </div>
              <div className="space-y-3">
                {extraEmails.map((email, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="flex-1 relative">
                      <input type="email" placeholder='extra@gmail.com' value={email}
                        onChange={e => handleExtraEmailChange(i, e.target.value)}
                        dir="ltr"
                        className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none text-left placeholder:text-slate-400 dark:placeholder:text-slate-500 text-slate-900 dark:text-slate-100 text-sm"
                        autoComplete="email"
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

            <hr className="border-slate-200 dark:border-slate-800" />

            <div className="flex justify-between items-center">
              <p className="text-xs text-slate-400 dark:text-slate-500">ניתן לשנות הגדרות אלה בכל עת בעמוד ההגדרות</p>
              <button
                onClick={handleNextStep}
                disabled={!isValidStep1 || saving}
                className="flex items-center gap-2 bg-slate-900 dark:bg-slate-100 hover:bg-slate-800 dark:hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed text-white dark:text-slate-900 px-8 py-3.5 rounded-xl font-semibold transition-all transform active:scale-95 shadow-lg shadow-slate-900/20 dark:shadow-white/10"
              >
                המשך לשלב הבא
                <ChevronLeft className="w-4 h-4" />
              </button>
            </div>
          </div>
        ) : (
          <div className="animate-in fade-in slide-in-from-right-4 duration-500">
             <div className="px-8 pt-4">
                <button 
                  onClick={handleBackStep}
                  className="flex items-center gap-1 text-slate-500 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 text-sm font-medium transition-colors"
                >
                  <ArrowRight className="w-4 h-4" /> חזרה לשלב הקודם
                </button>
             </div>
             <FinancialProfileStep 
               onComplete={handleCompleteFinancialProfile}
               initialData={financialData}
               onDataChange={handleFinancialDataChange}
             />
             {saving && (
               <div className="fixed inset-0 bg-white/60 dark:bg-slate-950/60 backdrop-blur-sm z-50 flex flex-col items-center justify-center">
                 <div className="w-12 h-12 border-4 border-blue-600/30 border-t-blue-600 dark:border-blue-400/30 dark:border-t-blue-400 rounded-full animate-spin mb-4" />
                 <p className="text-blue-900 dark:text-blue-100 font-bold text-lg">שומר נתונים ומקים את לוח הבקרה...</p>
                 <p className="text-blue-600/70 dark:text-blue-300/70">זה ייקח רק כמה שניות</p>
               </div>
             )}
          </div>
        )}
      </div>
    </div>
  );
}
