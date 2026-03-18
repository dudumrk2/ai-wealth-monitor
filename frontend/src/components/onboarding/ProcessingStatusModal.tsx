import { Loader2, CheckCircle2, ChevronRight, XCircle } from 'lucide-react';

export type ProcessingStatus = 'loading' | 'success' | 'error';

interface ProcessingStatusModalProps {
  isOpen: boolean;
  status: ProcessingStatus;
  resultsSummary?: {
    filesCount: number;
    fundsFound: number;
  };
  error?: string;
  onClose: () => void;
  onProceed: () => void;
}

export default function ProcessingStatusModal({
  isOpen,
  status,
  resultsSummary,
  error,
  onClose,
  onProceed
}: ProcessingStatusModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-2xl overflow-hidden border border-slate-200">
        <div className="p-8 text-center">

          {/* Status Icon */}
          <div className="flex justify-center mb-6">
            {status === 'loading' && (
              <div className="relative">
                <div className="absolute inset-0 bg-blue-100 rounded-full animate-ping opacity-25"></div>
                <div className="relative bg-blue-50 p-5 rounded-full border-4 border-white shadow-sm">
                  <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
                </div>
              </div>
            )}
            {status === 'success' && (
              <div className="bg-emerald-50 p-5 rounded-full border-4 border-white shadow-sm">
                <CheckCircle2 className="w-10 h-10 text-emerald-600" />
              </div>
            )}
            {status === 'error' && (
              <div className="bg-red-50 p-5 rounded-full border-4 border-white shadow-sm">
                <XCircle className="w-10 h-10 text-red-600" />
              </div>
            )}
          </div>

          {/* Title */}
          <h2 className="text-2xl font-bold text-slate-900 mb-2">
            {status === 'loading' && 'מנתח נתונים בבינה מלאכותית...'}
            {status === 'success' && 'הניתוח הושלם בהצלחה!'}
            {status === 'error' && 'משהו השתבש'}
          </h2>

          {/* Message */}
          <p className="text-slate-500 mb-8 px-4">
            {status === 'loading' && 'זה עשוי לקחת כ-20 שניות. אנחנו מחלצים את כל המידע הפיננסי מהדוחות שלך.'}
            {status === 'success' && `עיבדנו ${resultsSummary?.filesCount} קבצים ומצאנו ${resultsSummary?.fundsFound} קופות וקרנות חדשות.`}
            {status === 'error' && (error || 'אירעה שגיאה במהלך הניתוח. אנא בדוק את הלוגים בשרת ונסה שוב.')}
          </p>

          {/* Action Buttons */}
          <div className="space-y-3">
            {status === 'success' && (
              <button
                onClick={onProceed}
                className="w-full flex items-center justify-center gap-2 bg-slate-900 hover:bg-slate-800 text-white py-4 rounded-2xl font-bold transition-all transform active:scale-95 shadow-lg shadow-slate-900/20"
              >
                המשך לדשבורד
                <ChevronRight className="w-5 h-5 rotate-180" />
              </button>
            )}
            {status === 'error' && (
              <button
                onClick={onClose}
                className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 py-4 rounded-2xl font-bold transition-all"
              >
                סגור ונסה שוב
              </button>
            )}
            {status === 'loading' && (
              <div className="py-4 text-xs font-semibold text-slate-400 animate-pulse">
                אנא המתן, לא לסגור את החלון...
              </div>
            )}
          </div>
        </div>

        {/* Footer Brand */}
        <div className="bg-slate-50 py-4 border-t border-slate-100 text-center">
          <p className="text-[10px] text-slate-400 font-medium uppercase tracking-widest">Powered by claude-sonnet-4-6</p>
        </div>
      </div>
    </div>
  );
}
