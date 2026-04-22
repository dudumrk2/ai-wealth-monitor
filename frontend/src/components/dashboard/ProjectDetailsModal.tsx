import {
  X,
  Building2,
  Calendar,
  Clock,
  TrendingUp,
  CheckCircle2,
  Pencil,
  Trash2,
  FileText,
  User,
  DollarSign,
  ArrowUpRight,
} from 'lucide-react';
import type { AltProject } from '../../types/alternative';
import { formatCurrency, formatPercent } from '../../utils/format';
import { getMonthsElapsed } from '../../utils/date';
import { InfoCell } from '../ui/InfoCell';

interface ProjectDetailsModalProps {
  project: AltProject;
  onClose: () => void;
  onEdit?: (project: AltProject) => void;
  onDelete?: (project: AltProject) => void;
}

/** Add N months to a date string (YYYY-MM-DD or YYYY-MM), return YYYY-MM */
function addMonths(dateStr: string, months: number): string {
  const d = new Date(dateStr);
  d.setMonth(d.getMonth() + months);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function formatMonthLabel(yyyyMm: string): string {
  const [y, m] = yyyyMm.split('-');
  const date = new Date(Number(y), Number(m) - 1, 1);
  return date.toLocaleDateString('he-IL', { month: 'long', year: 'numeric' });
}

export default function ProjectDetailsModal({
  project,
  onClose,
  onEdit,
  onDelete,
}: ProjectDetailsModalProps) {
  const isExited = project.status === 'Exited';
  const monthsElapsed = getMonthsElapsed(project.startDate);
  const progressPct = Math.min(
    100,
    Math.max(0, (monthsElapsed / project.durationMonths) * 100)
  );
  const expectedEndDate = addMonths(project.startDate, project.durationMonths);
  const realizedProfit = isExited && project.finalAmount
    ? project.finalAmount - project.originalAmount
    : null;
  const realizedProfitPct = realizedProfit && project.originalAmount > 0
    ? (realizedProfit / project.originalAmount) * 100
    : null;

  const totalExpectedProfit = project.originalAmount * (project.expectedReturn / 100) * (project.durationMonths / 12);
  const currentAccruedProfit = (project.originalAmount * (project.expectedReturn / 100)) * (Math.max(0, monthsElapsed) / 12);
  const estimatedCurrentValue = project.originalAmount + currentAccruedProfit;

  const handleEdit = () => {
    if (onEdit) {
      onEdit(project);
    } else {
      console.log('[ProjectDetailsModal] Edit clicked for project:', project.id);
      alert('עריכת פרויקט — תכונה בפיתוח');
    }
  };

  const handleDelete = () => {
    if (onDelete) {
      onDelete(project);
    } else {
      console.log('[ProjectDetailsModal] Delete clicked for project:', project.id);
      if (window.confirm(`האם למחוק את הפרויקט "${project.name}"?`)) {
        alert('מחיקת פרויקט — תכונה בפיתוח');
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
      dir="rtl"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white dark:bg-slate-900 rounded-2xl w-full max-w-xl shadow-2xl flex flex-col overflow-hidden animate-modal-slide-up">

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100 dark:border-slate-800 bg-gradient-to-l from-emerald-50 dark:from-emerald-950/40 to-white dark:to-slate-900">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-100 dark:bg-emerald-900/50 rounded-xl flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100 leading-tight">
                {project.name}
              </h2>
              <div className="flex items-center gap-2 mt-0.5">
                <p className="text-xs text-slate-500 dark:text-slate-400">{project.developer}</p>
                {isExited ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-xs font-semibold rounded-full border border-slate-200 dark:border-slate-700">
                    <CheckCircle2 className="w-3 h-3" /> אקזיט
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400 text-xs font-semibold rounded-full">
                    פעיל
                  </span>
                )}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* ── Body ── */}
        <div className="p-6 space-y-5 overflow-y-auto max-h-[70vh]">

          {/* Info Grid */}
          <div className="grid grid-cols-2 gap-3">
            <InfoCell
              icon={<DollarSign className="w-4 h-4" />}
              label="סכום השקעה"
              value={formatCurrency(project.originalAmount, project.currency)}
              valueClassName="text-slate-800 dark:text-slate-100 font-bold"
            />
            <InfoCell
              icon={<TrendingUp className="w-4 h-4 text-emerald-500" />}
              label="תשואה שנתית צפויה"
              value={formatPercent(project.expectedReturn)}
              valueClassName="text-emerald-600 dark:text-emerald-400 font-bold"
            />
            <InfoCell
              icon={<Calendar className="w-4 h-4" />}
              label="תאריך התחלה"
              value={new Date(project.startDate).toLocaleDateString('he-IL', { year: 'numeric', month: 'long', day: 'numeric' })}
            />
            <InfoCell
              icon={<Clock className="w-4 h-4" />}
              label="משך משוער"
              value={`${project.durationMonths} חודשים`}
            />
            <InfoCell
              icon={<Calendar className="w-4 h-4 text-slate-400" />}
              label="תאריך יציאה צפוי"
              value={formatMonthLabel(expectedEndDate)}
            />
            <InfoCell
              icon={<User className="w-4 h-4" />}
              label="יזם"
              value={project.developer}
            />
            {!isExited && (
              <>
                <InfoCell
                  icon={<TrendingUp className="w-4 h-4 text-indigo-500" />}
                  label="רווח צפוי (סה״כ)"
                  value={formatCurrency(totalExpectedProfit, project.currency)}
                  valueClassName="text-indigo-600 dark:text-indigo-400 font-bold"
                />
                <InfoCell
                  icon={<DollarSign className="w-4 h-4 text-blue-500" />}
                  label="שווי משוער (כולל צבירה)"
                  value={formatCurrency(estimatedCurrentValue, project.currency)}
                  valueClassName="text-blue-600 dark:text-blue-400 font-bold"
                />
              </>
            )}
          </div>

          {/* ── Timeline Progress ── */}
          <div className="bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" />
                התקדמות זמן
              </span>
              <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
                {Math.max(0, monthsElapsed)} / {project.durationMonths} חודשים
              </span>
            </div>
            <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2.5 overflow-hidden mb-2">
              <div
                className={`h-2.5 rounded-full transition-all duration-700 ${
                  isExited ? 'bg-slate-400' : progressPct >= 100 ? 'bg-amber-500' : 'bg-emerald-500'
                }`}
                style={{ width: `${Math.min(100, Math.max(0, progressPct))}%` }}
              />
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {isExited
                ? `הפרויקט הסתיים ב-${project.actualExitDate ?? expectedEndDate}`
                : progressPct >= 100
                ? 'חלף המועד הצפוי — ממתין לסיום'
                : `חלפו ${Math.max(0, monthsElapsed)} חודשים מתוך ${project.durationMonths} המתוכננים`}
            </p>
          </div>

          {/* ── Exit Results (if exited) ── */}
          {isExited && project.finalAmount != null && (
            <div className="rounded-xl border border-emerald-200 dark:border-emerald-800 overflow-hidden">
              <div className="bg-gradient-to-l from-emerald-600 to-teal-600 px-4 py-3">
                <p className="text-white font-bold text-sm tracking-wide">✅ תוצאות האקזיט</p>
              </div>
              <div className="bg-emerald-50/50 dark:bg-emerald-950/30 divide-y divide-emerald-100 dark:divide-emerald-900/50">
                <div className="px-4 py-3.5 flex items-start justify-between gap-4">
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">סכום החזר בפועל</p>
                  <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
                    {formatCurrency(project.finalAmount, project.currency)}
                  </p>
                </div>
                {realizedProfit !== null && (
                  <div className="px-4 py-3.5 flex items-start justify-between gap-4">
                    <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">רווח ממומש</p>
                    <div className="text-left">
                      <p className={`text-lg font-bold ${realizedProfit >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-500'}`}>
                        {realizedProfit >= 0 ? '+' : ''}{formatCurrency(realizedProfit, project.currency)}
                      </p>
                      {realizedProfitPct !== null && (
                        <p className="text-xs text-slate-500 dark:text-slate-400 text-left">
                          ({realizedProfitPct >= 0 ? '+' : ''}{realizedProfitPct.toFixed(1)}%)
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Document Viewer Button ── */}
          {project.pdfUrl && (
            <a
              href={project.pdfUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-center gap-2 w-full px-4 py-3 bg-slate-50 dark:bg-slate-800/60 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-semibold text-slate-700 dark:text-slate-300 transition-all group"
            >
              <FileText className="w-4 h-4 text-indigo-500 group-hover:scale-110 transition-transform" />
              📄 צפה במצגת הפרויקט
              <ArrowUpRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-500 transition-colors" />
            </a>
          )}
        </div>

        {/* ── Footer / Actions ── */}
        <div className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/30 flex items-center justify-between gap-3 rounded-b-2xl">
          <div className="flex gap-2">
            <button
              onClick={handleEdit}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-700 transition-all active:scale-95"
            >
              <Pencil className="w-4 h-4" />
              עריכה
            </button>
            <button
              onClick={handleDelete}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-red-600 dark:text-red-400 bg-white dark:bg-slate-800 border border-red-200 dark:border-red-900/50 rounded-xl hover:bg-red-50 dark:hover:bg-red-950/30 transition-all active:scale-95"
            >
              <Trash2 className="w-4 h-4" />
              מחיקה
            </button>
          </div>
          <button
            onClick={onClose}
            className="px-5 py-2 text-sm font-semibold text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
          >
            סגור
          </button>
        </div>
      </div>


    </div>
  );
}
