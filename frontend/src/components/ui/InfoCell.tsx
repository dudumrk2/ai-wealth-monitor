import React from 'react';

interface InfoCellProps {
  label: string;
  value: React.ReactNode;
  icon?: React.ReactNode;
  subtext?: string;
  valueClassName?: string;
}

export function InfoCell({ label, value, icon, subtext, valueClassName = 'text-slate-700 dark:text-slate-300 font-semibold' }: InfoCellProps) {
  return (
    <div className="bg-slate-50 dark:bg-slate-800/60 rounded-xl px-4 py-3">
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-1 flex items-center gap-1">
        {icon && <span className="text-slate-400">{icon}</span>}
        {label}
      </p>
      <p className={`text-sm ${valueClassName}`}>
        {value}
      </p>
      {subtext && (
        <p className="text-xs font-medium text-slate-500 mt-1">
          {subtext}
        </p>
      )}
    </div>
  );
}
