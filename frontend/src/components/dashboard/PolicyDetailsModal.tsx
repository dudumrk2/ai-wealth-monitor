import React from 'react';
import {
  X,
  Shield,
  ExternalLink,
  Calendar,
  Wallet,
  TrendingDown,
  Pencil,
  Trash2,
  AlertTriangle,
  Percent,
  BarChart3,
  FileText,
  ArrowUpRight,
} from 'lucide-react';
import type { LeveragedPolicy } from '../../types/alternative';

interface PolicyDetailsModalProps {
  policy: LeveragedPolicy;
  currentPrimeRate: number;
  onClose: () => void;
  onEdit?: (policy: LeveragedPolicy) => void;
  onDelete?: (policy: LeveragedPolicy) => void;
}

const formatCurrency = (amount: number) =>
  new Intl.NumberFormat('he-IL', {
    style: 'currency',
    currency: 'ILS',
    maximumFractionDigits: 0,
  }).format(amount);

const formatPercent = (value: number) =>
  `${value.toFixed(2)}%`;

export default function PolicyDetailsModal({
  policy,
  currentPrimeRate,
  onClose,
  onEdit,
  onDelete,
}: PolicyDetailsModalProps) {
  // --- Financial Math ---
  // policy.interestRate stores the SUBTRACTED margin (e.g., 0.5 means Prime - 0.5%)
  const margin = policy.interestRate ?? 0;
  const actualInterestRate = Math.max(0, currentPrimeRate - margin);
  const loanAmount = policy.balloonLoanAmount ?? 0;
  const annualCostILS = loanAmount * (actualInterestRate / 100);
  const monthlyCostILS = annualCostILS / 12;

  const ltvPct = policy.currentBalance > 0
    ? Math.min(100, Math.round((loanAmount / policy.currentBalance) * 100))
    : 0;
  const isHighRisk = ltvPct > 70;

  // Margin label e.g. "פריים - 0.50%"
  const marginLabel = margin > 0
    ? `פריים - ${margin.toFixed(2)}%`
    : margin < 0
    ? `פריים + ${Math.abs(margin).toFixed(2)}%`
    : 'פריים';

  const handleEdit = () => {
    if (onEdit) {
      onEdit(policy);
    } else {
      console.log('[PolicyDetailsModal] Edit clicked for policy:', policy.id);
      alert('עריכת פוליסה — תכונה בפיתוח');
    }
  };

  const handleDelete = () => {
    if (onDelete) {
      onDelete(policy);
    } else {
      console.log('[PolicyDetailsModal] Delete clicked for policy:', policy.id);
      if (window.confirm(`האם למחוק את הפוליסה "${policy.name}"?`)) {
        alert('מחיקת פוליסה — תכונה בפיתוח');
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
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100 dark:border-slate-800 bg-gradient-to-l from-indigo-50 dark:from-indigo-950/40 to-white dark:to-slate-900">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-100 dark:bg-indigo-900/50 rounded-xl flex items-center justify-center text-indigo-600 dark:text-indigo-400 shrink-0">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100 leading-tight">
                {policy.name}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                פוליסה #{policy.policyNumber}
              </p>
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
              icon={<Wallet className="w-4 h-4" />}
              label="שווי קופה נוכחי"
              value={formatCurrency(policy.currentBalance)}
              valueClass="text-slate-800 dark:text-slate-100 font-bold"
            />
            <InfoCell
              icon={<TrendingDown className="w-4 h-4 text-red-500" />}
              label="הלוואת בלון"
              value={formatCurrency(loanAmount)}
              valueClass="text-red-600 dark:text-red-400 font-bold"
            />
            <InfoCell
              icon={<Calendar className="w-4 h-4" />}
              label="חודש בסיס"
              value={policy.baseMonth || '—'}
            />
            <InfoCell
              icon={<Percent className="w-4 h-4" />}
              label="ריבית מינוף"
              value={marginLabel}
              valueClass="text-indigo-600 dark:text-indigo-400 font-semibold"
            />
            {policy.funderLink && (
              <div className="col-span-2">
                <a
                  href={policy.funderLink}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  קישור לפאנדר
                </a>
              </div>
            )}
          </div>

          {/* LTV Bar */}
          <div className="bg-slate-50 dark:bg-slate-800/60 rounded-xl p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                <BarChart3 className="w-3.5 h-3.5" />
                חשיפה (LTV)
              </span>
              <span className={`text-xs font-bold ${isHighRisk ? 'text-red-500' : 'text-slate-700 dark:text-slate-300'}`}>
                {ltvPct}%
                {isHighRisk && (
                  <span className="mr-1.5 inline-flex items-center gap-0.5 text-red-500">
                    <AlertTriangle className="w-3 h-3" /> גבוה
                  </span>
                )}
              </span>
            </div>
            <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2.5 overflow-hidden">
              <div
                className={`h-2.5 rounded-full transition-all duration-700 ${isHighRisk ? 'bg-red-500' : 'bg-indigo-500'}`}
                style={{ width: `${ltvPct}%` }}
              />
            </div>
          </div>

          {/* ── Cost of Leverage Section ── */}
          <div className="rounded-xl border border-indigo-200 dark:border-indigo-800 overflow-hidden">
            {/* Section header */}
            <div className="bg-gradient-to-l from-indigo-600 to-violet-600 px-4 py-3">
              <p className="text-white font-bold text-sm tracking-wide">📊 עלות המינוף (Cost of Leverage)</p>
            </div>

            <div className="bg-indigo-50/50 dark:bg-indigo-950/30 divide-y divide-indigo-100 dark:divide-indigo-900/50">
              {/* Actual Interest Rate */}
              <div className="px-4 py-3.5 flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">ריבית בפועל</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    מבוסס על פריים עדכני: {formatPercent(currentPrimeRate)}
                  </p>
                </div>
                <div className="text-left shrink-0">
                  <p className="text-xl font-extrabold text-indigo-600 dark:text-indigo-400" dir="ltr">
                    {formatPercent(actualInterestRate)}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 text-left">{marginLabel}</p>
                </div>
              </div>

              {/* Annual Run-Rate */}
              <div className="px-4 py-3.5 flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">קצב עלות שנתית (Run-Rate)</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    {formatCurrency(loanAmount)} × {formatPercent(actualInterestRate)}
                  </p>
                </div>
                <p className="text-lg font-bold text-red-600 dark:text-red-400 shrink-0">
                  {formatCurrency(annualCostILS)}
                </p>
              </div>

              {/* Monthly Cost */}
              <div className="px-4 py-3.5 flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">עלות חודשית נגזרת</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    עלות שנתית ÷ 12
                  </p>
                </div>
                <p className="text-lg font-bold text-orange-600 dark:text-orange-400 shrink-0">
                  {formatCurrency(monthlyCostILS)}
                </p>
              </div>
            </div>
          </div>

          {/* ── Document Viewer Button ── */}
          {policy.pdfUrl && (
            <a
              href={policy.pdfUrl}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-center gap-2 w-full px-4 py-3 bg-slate-50 dark:bg-slate-800/60 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-semibold text-slate-700 dark:text-slate-300 transition-all group"
            >
              <FileText className="w-4 h-4 text-indigo-500 group-hover:scale-110 transition-transform" />
              📄 צפה במסמך הפוליסה
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

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes modal-slide-up {
          from { opacity: 0; transform: translateY(16px) scale(0.98); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        .animate-modal-slide-up {
          animation: modal-slide-up 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
      ` }} />
    </div>
  );
}

// ── Small helper sub-component ──
function InfoCell({
  icon,
  label,
  value,
  valueClass = 'text-slate-700 dark:text-slate-300 font-semibold',
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="bg-slate-50 dark:bg-slate-800/60 rounded-xl px-4 py-3">
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-1 flex items-center gap-1">
        {icon && <span className="text-slate-400">{icon}</span>}
        {label}
      </p>
      <p className={`text-sm ${valueClass}`}>{value}</p>
    </div>
  );
}
