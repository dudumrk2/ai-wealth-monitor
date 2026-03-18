import { useState } from 'react';
import { X, Eye, ShieldCheck, Loader2, FileText, ChevronLeft, ChevronRight } from 'lucide-react';

export interface FilePreviewGroup {
  filename: string;
  images: string[];
}

interface RedactionPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  fileGroups: FilePreviewGroup[];
  onConfirm: () => void;
  isProcessing: boolean;
}

export default function RedactionPreviewModal({
  isOpen,
  onClose,
  fileGroups,
  onConfirm,
  isProcessing
}: RedactionPreviewModalProps) {
  const [activeTab, setActiveTab] = useState(0);

  if (!isOpen) return null;

  const hasImages = fileGroups.some(g => g.images.length > 0);
  const activeGroup = fileGroups[activeTab];
  const totalFiles = fileGroups.length;

  // Short display name for tab (trim leading underscores, limit length)
  const shortName = (name: string) => {
    const clean = name.replace(/^_+/, '');
    return clean.length > 28 ? clean.slice(0, 26) + '…' : clean;
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/60 backdrop-blur-md transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-5xl bg-white rounded-3xl shadow-2xl border border-white/20 overflow-hidden flex flex-col h-[90vh]">

        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex items-center justify-between bg-slate-50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-600 rounded-xl shadow-lg shadow-blue-600/20">
              <ShieldCheck className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900">תצוגה מקדימה של השחרת נתונים</h2>
              <p className="text-sm text-slate-500">
                {hasImages
                  ? 'ודא שכל הנתונים האישיים הושחרו לפני שליחה לניתוח'
                  : `נמצאו ${totalFiles} קבצים שעברו השחרה — לחץ אישור לשליחה לניתוח`}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full transition-colors">
            <X className="w-6 h-6 text-slate-400" />
          </button>
        </div>

        {/* File Tabs — only shown when multiple files */}
        {totalFiles > 1 && (
          <div className="flex items-center gap-1 px-6 pt-4 bg-white shrink-0 border-b border-slate-100 pb-0">
            {fileGroups.map((g, i) => (
              <button
                key={i}
                onClick={() => setActiveTab(i)}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-t-xl border-b-2 transition-all whitespace-nowrap ${
                  activeTab === i
                    ? 'border-blue-600 text-blue-600 bg-blue-50'
                    : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
                }`}
              >
                <FileText className="w-4 h-4 shrink-0" />
                <span dir="rtl">{shortName(g.filename)}</span>
                {g.images.length > 0 && (
                  <span className="text-xs bg-slate-200 text-slate-600 rounded-full px-2 py-0.5">
                    {g.images.length} עמ׳
                  </span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto bg-slate-100 p-8 custom-scrollbar">
          {hasImages && activeGroup?.images.length > 0 ? (
            <div className="flex flex-col items-center gap-12 w-full">
              {/* File label for single-file view */}
              {totalFiles === 1 && (
                <div className="flex items-center gap-2 self-start">
                  <FileText className="w-4 h-4 text-blue-500" />
                  <span className="text-sm font-medium text-slate-600" dir="rtl">{fileGroups[0].filename}</span>
                </div>
              )}
              {activeGroup.images.map((img, idx) => (
                <div key={idx} className="relative w-full max-w-3xl">
                  <div className="absolute -top-6 right-0 text-xs font-bold text-slate-400 bg-white/70 px-3 py-1 rounded-full backdrop-blur-sm">
                    עמוד {idx + 1} מתוך {activeGroup.images.length}
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
            /* No images — show file list summary */
            <div className="flex flex-col items-center justify-center h-full gap-6 text-slate-600">
              <div className="p-4 bg-blue-50 rounded-2xl">
                <ShieldCheck className="w-14 h-14 text-blue-500" />
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-slate-800 mb-1">נמצאו {totalFiles} קבצים חדשים</p>
                <p className="text-sm text-slate-500">הקבצים עברו עיבוד והשחרת מידע אישי בהצלחה.</p>
              </div>
              <div className="w-full max-w-md space-y-2">
                {fileGroups.map((g, i) => (
                  <div key={i} className="flex items-center gap-3 p-3 bg-white rounded-xl border border-slate-200 shadow-sm">
                    <FileText className="w-5 h-5 text-blue-500 shrink-0" />
                    <span className="text-sm font-medium text-slate-700 truncate" dir="rtl">{g.filename}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 bg-white border-t border-slate-100 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 text-slate-500">
            <Eye className="w-4 h-4" />
            <span className="text-xs">המידע נשאר על המחשב שלך עד לאישור השליחה</span>
          </div>

          {/* Tab prev/next for quick keyboard-style nav */}
          <div className="flex gap-3 items-center">
            {totalFiles > 1 && hasImages && (
              <div className="flex items-center gap-1 text-sm text-slate-500">
                <button
                  onClick={() => setActiveTab(i => Math.max(0, i - 1))}
                  disabled={activeTab === 0}
                  className="p-1 rounded-lg hover:bg-slate-100 disabled:opacity-30 transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
                <span className="min-w-[4rem] text-center font-medium">
                  {activeTab + 1} / {totalFiles}
                </span>
                <button
                  onClick={() => setActiveTab(i => Math.min(totalFiles - 1, i + 1))}
                  disabled={activeTab === totalFiles - 1}
                  className="p-1 rounded-lg hover:bg-slate-100 disabled:opacity-30 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
              </div>
            )}

            <button
              onClick={onClose}
              className="px-6 py-2.5 text-slate-600 hover:bg-slate-50 rounded-xl font-semibold transition-colors"
            >
              ביטול
            </button>
            <button
              onClick={onConfirm}
              disabled={isProcessing}
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
