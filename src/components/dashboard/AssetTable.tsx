 import React from 'react'; 
import { ArrowUpRight, TrendingUp } from 'lucide-react';
import clsx from 'clsx';

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
}

interface AssetTableProps {
  title: string;
  funds: Fund[];
}

export default function AssetTable({ title, funds }: AssetTableProps) {
  
  if (!funds || funds.length === 0) {
    return null;
  }

  const formatCurrency = (val: number) => new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 }).format(val);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-6">
      <div className="p-5 border-b border-slate-100 flex items-center justify-between">
         <h3 className="font-bold text-lg text-slate-800">{title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-50/50 text-slate-500 text-xs uppercase tracking-wider">
              <th className="p-4 font-semibold border-b border-slate-200">Provider & Track</th>
              <th className="p-4 font-semibold border-b border-slate-200 text-right">Balance</th>
              <th className="p-4 font-semibold border-b border-slate-200 text-right">1Y Yield</th>
              <th className="p-4 font-semibold border-b border-slate-200 text-right">3Y Yield</th>
              <th className="p-4 font-semibold border-b border-slate-200 text-right">5Y Yield</th>
              <th className="p-4 font-semibold border-b border-slate-200 text-right">Mgmt Fee</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {funds.map((fund) => {
              const hasCompetitors = fund.top_competitors && fund.top_competitors.length > 0;
              
              return (
                <tr key={fund.id} className="hover:bg-slate-50/80 transition-colors group">
                  <td className="p-4">
                    <div className="font-semibold text-slate-900 group-hover:text-blue-600 transition-colors cursor-pointer flex items-center gap-2">
                       {fund.provider_name}
                       <ArrowUpRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                    <div className="text-sm text-slate-500">{fund.track_name}</div>
                  </td>
                  <td className="p-4 text-right font-medium text-slate-900">
                    {formatCurrency(fund.balance)}
                  </td>
                  
                  {/* Yield Columns */}
                  {[fund.yield_1yr, fund.yield_3yr, fund.yield_5yr].map((y, i) => (
                    <td key={i} className="p-4 text-right">
                      <div className={clsx("inline-flex items-center gap-1 font-medium", y > 0 ? "text-emerald-600" : "text-slate-600")}>
                        {y > 0 && <TrendingUp className="w-3 h-3" />}
                        {y}%
                      </div>
                    </td>
                  ))}
                  
                  <td className="p-4 text-right">
                     <div className="relative inline-flex items-center justify-end">
                       <span className={clsx("font-medium", hasCompetitors ? "text-amber-600" : "text-slate-600")}>
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
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
