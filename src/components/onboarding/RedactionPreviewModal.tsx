import { X, Eye, ShieldCheck, Loader2 } from 'lucide-react';

interface RedactionPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  images: string[];
  onConfirm: () => void;
  isProcessing: boolean;
}

export default function RedactionPreviewModal({
  isOpen,
  onClose,
  images,
  onConfirm,
  isProcessing
}: RedactionPreviewModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-slate-900/60 backdrop-blur-md transition-opacity" 
        onClick={onClose}
      />

      {/* Modal Content */}
      <div className="relative w-full max-w-5xl bg-white rounded-3xl shadow-2xl border border-white/20 overflow-hidden flex flex-col h-[90vh]">
        
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-slate-50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-600 rounded-xl shadow-lg shadow-blue-600/20">
              <ShieldCheck className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900">תצוגה מקדימה של השחרת נתונים</h2>
              <p className="text-sm text-slate-500">גלול למטה כדי לוודא שכל העמודים הושחרו בהצלחה</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-slate-200 rounded-full transition-colors"
          >
            <X className="w-6 h-6 text-slate-400" />
          </button>
        </div>

        {/* Body - Scrollable Image List */}
        <div className="flex-1 overflow-y-auto bg-slate-100 p-8 space-y-8 custom-scrollbar">
          {images.length > 0 ? (
            <div className="flex flex-col items-center gap-12 w-full">
              {images.map((img, idx) => (
                <div key={idx} className="relative w-full max-w-3xl">
                  <div className="absolute -top-6 right-0 text-xs font-bold text-slate-400 bg-white/50 px-3 py-1 rounded-full backdrop-blur-sm">
                    עמוד {idx + 1}
                  </div>
                  <img 
                    src={`data:image/png;base64,${img}`}
                    alt={`Redacted page ${idx + 1}`}
                    className="w-full rounded-xl shadow-2xl ring-1 ring-slate-200 bg-white"
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-400">
              <Eye className="w-12 h-12 opacity-20" />
              <p>לא נמצאו דפים לעיבוד</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 bg-white border-t border-slate-100 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 text-slate-500">
            <Eye className="w-4 h-4" />
            <span className="text-xs">המידע נשאר על המחשב שלך עד לאישור השליחה</span>
          </div>
          
          <div className="flex gap-4">
            <button
              onClick={onClose}
              className="px-6 py-2.5 text-slate-600 hover:bg-slate-50 rounded-xl font-semibold transition-colors"
            >
              ביטול
            </button>
            <button
              onClick={onConfirm}
              disabled={isProcessing || images.length === 0}
              className="px-8 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl font-bold shadow-lg shadow-blue-600/20 flex items-center gap-2 transition-all transform active:scale-95"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  מעבד ניתוח...
                </>
              ) : (
                'אשר ושלח לניתוח בינה מלאכותית'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
