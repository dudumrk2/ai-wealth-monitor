import { useState } from 'react';
import { ArrowUpLeft, TrendingUp } from 'lucide-react';
import clsx from 'clsx';
import CompetitorModal from './CompetitorModal';

interface Fund {
  id: string;
  provider_name: string;
  track_name: string;
  balance: number;
  yield_1yr: number;
  yield_3yr: number;
  yield_5yr: number;
  management_fee_accumulation: number;
  top_competitors?: any[];
  _owner?: string; // used in joint aggregated view
}

interface AssetTableProps {
  title: string;
  funds: Fund[];
  /** When true, shows an extra "שייך ל" column with the owner name (joint view) */
  ownerColumn?: boolean;
}

export default function AssetTable({ title, funds, ownerColumn = false }: AssetTableProps) {
  const [selectedFund, setSelectedFund] = useState<Fund | null>(null);

  if (!funds || funds.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h3 className="font-bold text-lg text-slate-800 mb-2">{title}</h3>
        <p className="text-sm text-slate-400">אין נתונים להצגה</p>
      </div>
    );
  }

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 }).format(val);

  const totalBalance = funds.reduce((s, f) => s + f.balance, 0);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-2">
      <div className="p-5 border-b border-slate-100 flex items-center justify-between">
        <h3 className="font-bold text-lg text-slate-800">{title}</h3>
        {funds.length > 1 && (
          <span className="text-sm font-semibold text-slate-500">
            סה״כ: <span className="text-slate-900 tabular-nums" dir="ltr">{formatCurrency(totalBalance)}</span>
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-right border-collapse">
          <thead>
            <tr className="bg-slate-50/50 text-slate-500 text-xs uppercase tracking-wider">
              <th className="p-4 font-semibold border-b border-slate-200">ספק ומסלול</th>
              {ownerColumn && (
                <th className="p-4 font-semibold border-b border-slate-200">שייך ל</th>
              )}
              <th className="p-4 font-semibold border-b border-slate-200 text-left">יתרה</th>
              <th className="p-4 font-semibold border-b border-slate-200 text-left">תשואה 1Y</th>
              <th className="p-4 font-semibold border-b border-slate-200 text-left">תשואה 3Y</th>
              <th className="p-4 font-semibold border-b border-slate-200 text-left">תשואה 5Y</th>
              <th className="p-4 font-semibold border-b border-slate-200 text-left">דמי ניהול</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {funds.map((fund) => {
              const hasCompetitors = fund.top_competitors && fund.top_competitors.length > 0;

              return (
                <tr 
                  key={fund.id} 
                  className="hover:bg-slate-50/80 transition-colors group cursor-pointer hover:shadow-sm"
                  onClick={() => setSelectedFund(fund)}
                >
                  <td className="p-4">
                    <div className="font-semibold text-slate-900 group-hover:text-blue-600 transition-colors cursor-pointer flex items-center gap-2">
                      {fund.provider_name}
                      <ArrowUpLeft className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                    <div className="text-sm text-slate-500">{fund.track_name}</div>
                  </td>

                  {ownerColumn && (
                    <td className="p-4">
                      {fund._owner ? (
                        <span className="text-xs font-semibold bg-slate-100 text-slate-600 px-2.5 py-1 rounded-full">
                          {fund._owner}
                        </span>
                      ) : '—'}
                    </td>
                  )}

                  <td className="p-4 text-left font-medium text-slate-900 tabular-nums" dir="ltr">
                    {formatCurrency(fund.balance)}
                  </td>

                  {[fund.yield_1yr, fund.yield_3yr, fund.yield_5yr].map((y, i) => (
                    <td key={i} className="p-4 text-left">
                      <div className={clsx("inline-flex items-center gap-1 font-medium tabular-nums", y > 0 ? "text-emerald-600" : "text-slate-500")} dir="ltr">
                        {y > 0 && <TrendingUp className="w-3 h-3" />}
                        {y}%
                      </div>
                    </td>
                  ))}

                  <td className="p-4 text-left">
                    <div className="relative inline-flex items-center">
                      <span className={clsx("font-medium tabular-nums", hasCompetitors ? "text-amber-600" : "text-slate-600")} dir="ltr">
                        {fund.management_fee_accumulation}%
                      </span>
                      {hasCompetitors && (
                        <span className="absolute -top-1 -right-2 flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
          {funds.length > 1 && (
            <tfoot>
              <tr className="bg-slate-50 border-t-2 border-slate-200">
                <td className="p-4 font-bold text-slate-700" colSpan={ownerColumn ? 2 : 1}>סה״כ</td>
                <td className="p-4 text-left font-bold text-slate-900 tabular-nums" dir="ltr">{formatCurrency(totalBalance)}</td>
                <td colSpan={4}></td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      <CompetitorModal 
        isOpen={!!selectedFund} 
        onClose={() => setSelectedFund(null)} 
        product={selectedFund}
        productType={title}
      />
    </div>
  );
}
