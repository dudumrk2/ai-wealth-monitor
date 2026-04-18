import { AlertTriangle, CheckCircle, FileText, Upload } from 'lucide-react';

export interface Policy {
  id: string;
  provider: string;
  policy_name: string;
  monthly_premium: number;
  expiration_date: string;
  source_document_url?: string | null;
}

interface PolicyCardProps {
  policy: Policy;
  onUploadRequest: (policyId: string) => void;
}

export default function PolicyCard({ policy, onUploadRequest }: PolicyCardProps) {
  const hasDocument = !!policy.source_document_url;

  return (
    <div className="relative bg-slate-800 text-slate-200 border border-slate-700 rounded-xl p-5 shadow-sm flex flex-col gap-4 font-sans text-right" dir="rtl">
      {/* Badge / Header Area */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex flex-col">
          <h3 className="text-lg font-bold text-white">{policy.policy_name}</h3>
          <span className="text-sm text-slate-400">{policy.provider}</span>
        </div>
        
        {/* State B vs State A Badge */}
        {hasDocument ? (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>נתונים מלאים</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-medium">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>חסר מסמך מלא</span>
          </div>
        )}
      </div>

      {/* Middle row: Cost and Expiration (Grid) */}
      <div className="grid grid-cols-2 gap-4 bg-slate-900/50 p-3 rounded-lg border border-slate-700/50">
        <div className="flex flex-col">
          <span className="text-xs text-slate-400 mb-1">עלות חודשית</span>
          <span className="font-semibold text-white">
            ₪{policy.monthly_premium.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-xs text-slate-400 mb-1">תוקף פוליסה</span>
          <span className="font-semibold text-white">{policy.expiration_date || 'לא הוגדר'}</span>
        </div>
      </div>

      {/* Footer / Action Area */}
      <div className="mt-2 flex flex-col gap-2">
        {hasDocument ? (
          <button
            onClick={() => window.open(policy.source_document_url!, '_blank', 'noopener,noreferrer')}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 px-4 rounded-lg transition-colors text-sm"
          >
            <FileText className="w-4 h-4" />
            <span>צפה במסמך המקור</span>
          </button>
        ) : (
          <div className="flex flex-col gap-1.5">
            <button
              onClick={() => onUploadRequest(policy.id)}
              className="w-full flex items-center justify-center gap-2 bg-transparent hover:bg-slate-700/50 text-slate-300 border border-slate-600 font-medium py-2.5 px-4 rounded-lg transition-colors text-sm"
            >
              <Upload className="w-4 h-4" />
              <span>השלם פרטים (העלה פוליסה)</span>
            </button>
            <p className="text-xs text-center text-slate-400 px-2 leading-tight">
              העלאת הפוליסה המלאה תאפשר ל-AI לענות על שאלות מורכבות.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
