import React, { useState } from 'react';
import { X, Building2, Shield, UploadCloud, File as FileIcon, CheckCircle } from 'lucide-react';
import type { AltProject, LeveragedPolicy } from '../../types/alternative';

interface AddAlternativeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: AltProject | LeveragedPolicy, type: 'real_estate' | 'policy', file: File | null) => void;
  editData?: { item: AltProject | LeveragedPolicy; type: 'real_estate' | 'policy' } | null;
}

type TabType = 'real_estate' | 'policy';

export default function AddAlternativeModal({ isOpen, onClose, onSave, editData }: AddAlternativeModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>('real_estate');

  // Real Estate State
  const [projectName, setProjectName] = useState('');
  const [developer, setDeveloper] = useState('');
  const [currency, setCurrency] = useState('ILS');
  const [originalAmount, setOriginalAmount] = useState<string>('');
  const [startDate, setStartDate] = useState('');
  const [durationMonths, setDurationMonths] = useState<string>('');
  const [expectedReturn, setExpectedReturn] = useState<string>('');
  const [status, setStatus] = useState<'Active' | 'Exited'>('Active');
  const [actualExitDate, setActualExitDate] = useState('');
  const [finalAmount, setFinalAmount] = useState<string>('');

  // Policy State
  const [policyNumber, setPolicyNumber] = useState('');
  const [policyName, setPolicyName] = useState('');
  const [funderLink, setFunderLink] = useState('');
  const [currentBalance, setCurrentBalance] = useState<string>('');
  const [baseMonth, setBaseMonth] = useState('');
  const [balloonLoanAmount, setBalloonLoanAmount] = useState<string>('');
  const [interestRate, setInterestRate] = useState<string>('');
  const [initialDepositAmount, setInitialDepositAmount] = useState<string>('');
  const [initialRepaymentDate, setInitialRepaymentDate] = useState('');

  // Shared file state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Pre-fill or reset state when modal opens
  React.useEffect(() => {
    if (!isOpen) return;

    if (editData) {
      const { item, type } = editData;
      setActiveTab(type);
      setSelectedFile(null);

      if (type === 'real_estate') {
        const p = item as AltProject;
        setProjectName(p.name || '');
        setDeveloper(p.developer || '');
        setCurrency(p.currency || 'ILS');
        setOriginalAmount(String(p.originalAmount ?? ''));
        // startDate may be "YYYY-MM-DD" – month input needs "YYYY-MM"
        setStartDate(p.startDate ? p.startDate.slice(0, 7) : '');
        setDurationMonths(String(p.durationMonths ?? ''));
        setExpectedReturn(String(p.expectedReturn ?? ''));
        setStatus(p.status || 'Active');
        setActualExitDate(p.actualExitDate || '');
        setFinalAmount(p.finalAmount != null ? String(p.finalAmount) : '');
        // clear policy fields
        setPolicyNumber(''); setPolicyName(''); setFunderLink('');
        setCurrentBalance(''); setBaseMonth(''); setBalloonLoanAmount('');
        setInterestRate(''); setInitialDepositAmount(''); setInitialRepaymentDate('');
      } else {
        const pol = item as LeveragedPolicy;
        setPolicyNumber(pol.policyNumber || '');
        setPolicyName(pol.name || '');
        setFunderLink(pol.funderLink || '');
        setCurrentBalance(String(pol.currentBalance ?? ''));
        setBaseMonth(pol.baseMonth || '');
        setBalloonLoanAmount(String(pol.balloonLoanAmount ?? ''));
        setInterestRate(String(pol.interestRate ?? ''));
        setInitialDepositAmount(String(pol.initialDepositAmount ?? ''));
        setInitialRepaymentDate(pol.initialRepaymentDate || '');
        // clear project fields
        setProjectName(''); setDeveloper(''); setCurrency('ILS');
        setOriginalAmount(''); setStartDate(''); setDurationMonths('');
        setExpectedReturn(''); setStatus('Active'); setActualExitDate(''); setFinalAmount('');
      }
    } else {
      // Reset all fields for a new item
      setActiveTab('real_estate');
      setProjectName(''); setDeveloper(''); setCurrency('ILS');
      setOriginalAmount(''); setStartDate(''); setDurationMonths('');
      setExpectedReturn(''); setStatus('Active'); setActualExitDate(''); setFinalAmount('');
      setPolicyNumber(''); setPolicyName(''); setFunderLink('');
      setCurrentBalance(''); setBaseMonth(''); setBalloonLoanAmount('');
      setInterestRate(''); setInitialDepositAmount(''); setInitialRepaymentDate('');
      setSelectedFile(null);
    }
  }, [isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const isEditing = !!editData;

  const handleSave = () => {
    const existingId = editData?.item.id;
    if (activeTab === 'real_estate') {
      const data: AltProject = {
        ...(existingId ? { id: existingId } : {}),
        name: projectName,
        developer,
        currency,
        originalAmount: Number(originalAmount) || 0,
        startDate,
        durationMonths: Number(durationMonths) || 0,
        expectedReturn: Number(expectedReturn) || 0,
        status,
        ...(status === 'Exited' && {
          actualExitDate,
          finalAmount: Number(finalAmount) || 0,
        }),
      };
      onSave(data, 'real_estate', selectedFile);
    } else {
      const data: LeveragedPolicy = {
        ...(existingId ? { id: existingId } : {}),
        policyNumber,
        name: policyName,
        funderLink,
        currentBalance: Number(currentBalance) || 0,
        baseMonth,
        balloonLoanAmount: Number(balloonLoanAmount) || 0,
        interestRate: Number(interestRate) || 0,
        initialDepositAmount: Number(initialDepositAmount) || 0,
        initialRepaymentDate,
      };
      onSave(data, 'policy', selectedFile);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm" dir="rtl">
      <div className="bg-white dark:bg-slate-900 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-xl flex flex-col">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between p-6 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">
          <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100">
            {isEditing ? 'עריכת נכס אלטרנטיבי' : 'הוספת נכס אלטרנטיבי'}
          </h2>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded-lg transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 flex-1 space-y-6">
          {/* Tabs */}
          <div className="flex p-1 space-x-1 space-x-reverse bg-slate-100 dark:bg-slate-800/50 rounded-xl">
            <button
              onClick={() => setActiveTab('real_estate')}
              disabled={isEditing}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium rounded-lg transition-all ${
                activeTab === 'real_estate'
                  ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              } ${isEditing ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Building2 className="w-4 h-4" />
              פרויקט נדל"ן
            </button>
            <button
              onClick={() => setActiveTab('policy')}
              disabled={isEditing}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium rounded-lg transition-all ${
                activeTab === 'policy'
                  ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              } ${isEditing ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Shield className="w-4 h-4" />
              פוליסת חיסכון ממונפת
            </button>
          </div>

          {/* Real Estate Fields */}
          {activeTab === 'real_estate' && (
            <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">שם הפרויקט</label>
                  <input
                    type="text"
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                    placeholder="לדוגמה: מגדל העמק צפון"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">יזם</label>
                  <input
                    type="text"
                    value={developer}
                    onChange={(e) => setDeveloper(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">סכום השקעה</label>
                  <div className="relative">
                    <input
                      type="number"
                      value={originalAmount}
                      onChange={(e) => setOriginalAmount(e.target.value)}
                      className="w-full pl-20 pr-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                      dir="ltr"
                    />
                    <select
                      value={currency}
                      onChange={(e) => setCurrency(e.target.value)}
                      className="absolute left-0 top-0 bottom-0 px-3 bg-slate-100 dark:bg-slate-700 border-r border-slate-200 dark:border-slate-600 rounded-l-xl text-slate-700 dark:text-slate-300 outline-none"
                    >
                      <option value="ILS">₪</option>
                      <option value="USD">$</option>
                      <option value="EUR">€</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">חודש התחלה</label>
                  <input
                    type="month"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">משך משוער (בחודשים)</label>
                  <input
                    type="number"
                    value={durationMonths}
                    onChange={(e) => setDurationMonths(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">תשואה שנתית צפויה (%)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={expectedReturn}
                    onChange={(e) => setExpectedReturn(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                    dir="ltr"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">סטטוס פרויקט</label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value as 'Active' | 'Exited')}
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                >
                  <option value="Active">פעיל (Active)</option>
                  <option value="Exited">הושלם (Exited)</option>
                </select>
              </div>

              {status === 'Exited' && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-800 animate-in fade-in">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">תאריך יציאה בפועל</label>
                    <input
                      type="date"
                      value={actualExitDate}
                      onChange={(e) => setActualExitDate(e.target.value)}
                      className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">סכום יציאה (חזרה)</label>
                    <input
                      type="number"
                      value={finalAmount}
                      onChange={(e) => setFinalAmount(e.target.value)}
                      className="w-full px-4 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Policy Fields */}
          {activeTab === 'policy' && (
            <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">מספר פוליסה (חובה)</label>
                  <input
                    type="text"
                    value={policyNumber}
                    onChange={(e) => setPolicyNumber(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                    placeholder="לדוגמה: 12345678"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">שם הפוליסה</label>
                  <input
                    type="text"
                    value={policyName}
                    onChange={(e) => setPolicyName(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                    placeholder="לדוגמה: הכשרה בסט אינווסט"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">סכום הפקדה ראשוני (₪)</label>
                  <input
                    type="number"
                    value={initialDepositAmount}
                    onChange={(e) => setInitialDepositAmount(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">חודש החזר ראשוני</label>
                  <input
                    type="month"
                    value={initialRepaymentDate}
                    onChange={(e) => setInitialRepaymentDate(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">יתרה נוכחית (₪)</label>
                  <input
                    type="number"
                    value={currentBalance}
                    onChange={(e) => setCurrentBalance(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">חודש בסיס (YYYY-MM)</label>
                  <input
                    type="month"
                    value={baseMonth}
                    onChange={(e) => setBaseMonth(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">סכום הלוואת בלון (₪)</label>
                  <input
                    type="number"
                    value={balloonLoanAmount}
                    onChange={(e) => setBalloonLoanAmount(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">ריבית פריים פחות (%)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={interestRate}
                    onChange={(e) => setInterestRate(e.target.value)}
                    className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-slate-100"
                    placeholder="לדוגמה: 0.5"
                    dir="ltr"
                  />
                </div>
              </div>
            </div>
          )}

          {/* PDF Dropzone (Visual Only) */}
          <div className="border border-dashed border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 rounded-2xl p-6 text-center cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors relative">
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            {!selectedFile ? (
              <div className="flex flex-col items-center gap-2 pointer-events-none">
                <div className="w-12 h-12 bg-white dark:bg-slate-700 rounded-full flex items-center justify-center text-blue-500 shadow-sm mb-2">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <p className="font-semibold text-slate-800 dark:text-slate-200">גרור ושחרר מסמכי פוליסה/פרויקט לכאן</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">אנחנו תומכים בקבצי PDF עד 10MB</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 bg-green-50 dark:bg-green-900/30 rounded-full flex items-center justify-center text-green-600 dark:text-green-400 shadow-sm mb-2">
                  <CheckCircle className="w-6 h-6" />
                </div>
                <div>
                  <p className="font-semibold text-green-700 dark:text-green-500 flex items-center gap-2 justify-center">
                    <FileIcon className="w-4 h-4" /> {selectedFile.name}
                  </p>
                  <p className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 cursor-pointer mt-2 z-10 relative" onClick={(e) => { e.stopPropagation(); setSelectedFile(null); }}>
                    הסר קובץ
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/30 rounded-b-2xl flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-5 py-2.5 text-sm font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
          >
            ביטול
          </button>
          <button
            onClick={handleSave}
            className="px-6 py-2.5 text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-sm transition-all focus:ring-4 focus:ring-blue-500/20 active:scale-95"
          >
            {isEditing ? 'שמור שינויים' : 'שמור נכס'}
          </button>
        </div>
      </div>
    </div>
  );
}
