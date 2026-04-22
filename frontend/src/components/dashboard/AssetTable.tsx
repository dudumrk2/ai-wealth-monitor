import { useState } from 'react';
import { ArrowUpLeft, TrendingUp } from 'lucide-react';
import clsx from 'clsx';
import CompetitorModal from './CompetitorModal';
import { Card, CardHeader, CardTitle } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { formatCurrency } from '../../utils/format';

interface Fund {
  id: string;
  provider_name: string;
  track_name: string;
  balance: number;
  yield_1yr: number;
  yield_3yr: number;
  yield_5yr: number;
  sharpe_ratio?: number;
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
      <Card className="p-6 mb-6">
        <h3 className="font-bold text-lg text-slate-800 dark:text-slate-100 mb-2">{title}</h3>
        <p className="text-sm text-slate-500 dark:text-slate-500">אין נתונים להצגה</p>
      </Card>
    );
  }

  const totalBalance = funds.reduce((s, f) => s + f.balance, 0);

  return (
    <Card className="mb-4 md:mb-6">
      <CardHeader className="flex flex-row items-center justify-between p-4 md:p-5">
        <CardTitle>{title}</CardTitle>
        {funds.length > 1 && (
          <span className="text-sm font-bold text-slate-500 dark:text-slate-500">
            סה״כ: <span className="text-slate-900 dark:text-slate-100 tabular-nums" dir="ltr">{formatCurrency(totalBalance)}</span>
          </span>
        )}
      </CardHeader>
      <div className="overflow-x-auto">
        <table className="w-full text-right border-collapse">
          <thead>
            <tr className="bg-slate-50/50 dark:bg-slate-800/50 text-slate-500 dark:text-slate-500 text-[10px] md:text-xs font-bold uppercase tracking-normal">
              <th className="p-2 md:p-4 border-b border-slate-200 dark:border-slate-800">ספק ומסלול</th>
              {ownerColumn && (
                <th className="p-2 md:p-4 border-b border-slate-200 dark:border-slate-800">שייך ל</th>
              )}
              <th className="p-2 md:p-4 border-b border-slate-200 dark:border-slate-800 text-left">יתרה</th>
              <th className="p-2 md:p-4 border-b border-slate-200 dark:border-slate-800 text-left">תשואה 1Y</th>
              <th className="p-2 md:p-4 border-b border-slate-200 dark:border-slate-800 text-left">תשואה 3Y</th>
              <th className="p-2 md:p-4 border-b border-slate-200 dark:border-slate-800 text-left">תשואה 5Y</th>
              <th className="p-2 md:p-4 border-b border-slate-200 dark:border-slate-800 text-left">מדד שארפ</th>
              <th className="p-2 md:p-4 border-b border-slate-200 dark:border-slate-800 text-left">דמי ניהול</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {funds.map((fund) => {
              const hasCompetitors = fund.top_competitors && fund.top_competitors.length > 0;

              return (
                <tr 
                  key={fund.id} 
                  className="hover:bg-slate-50/80 dark:hover:bg-slate-800 transition-colors group cursor-pointer hover:shadow-sm"
                  onClick={() => setSelectedFund(fund)}
                >
                  <td className="p-4">
                    <div className="font-semibold text-slate-900 dark:text-slate-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors cursor-pointer flex items-center gap-2">
                      {fund.provider_name}
                      <ArrowUpLeft className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                    <div className="text-sm text-slate-500 dark:text-slate-400">{fund.track_name}</div>
                  </td>

                  {ownerColumn && (
                    <td className="p-4">
                      {fund._owner ? (
                        <Badge variant="secondary">
                          {fund._owner}
                        </Badge>
                      ) : '—'}
                    </td>
                  )}

                  <td className="p-4 text-left font-medium text-slate-900 dark:text-slate-100 tabular-nums" dir="ltr">
                    {formatCurrency(fund.balance)}
                  </td>

                  {[fund.yield_1yr, fund.yield_3yr, fund.yield_5yr].map((y, i) => (
                    <td key={i} className="p-4 text-left">
                      <div className={clsx("inline-flex items-center gap-1 font-medium tabular-nums", y > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-slate-500 dark:text-slate-400")} dir="ltr">
                        {y > 0 && <TrendingUp className="w-3 h-3" />}
                        {y}%
                      </div>
                    </td>
                  ))}

                  <td className="p-4 text-left font-medium text-slate-500 dark:text-slate-400 tabular-nums" dir="ltr">
                    {fund.sharpe_ratio ? fund.sharpe_ratio.toFixed(2) : '—'}
                  </td>

                  <td className="p-4 text-left">
                    <div className="relative inline-flex items-center">
                      <span className={clsx("font-medium tabular-nums", hasCompetitors ? "text-amber-600 dark:text-amber-400" : "text-slate-600 dark:text-slate-400")} dir="ltr">
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
              <tr className="bg-slate-50 dark:bg-slate-900/50 border-t-2 border-slate-200 dark:border-slate-800">
                <td className="p-4 font-bold text-slate-700 dark:text-slate-300" colSpan={ownerColumn ? 2 : 1}>סה״כ</td>
                <td className="p-4 text-left font-bold text-slate-900 dark:text-slate-100 tabular-nums" dir="ltr">{formatCurrency(totalBalance)}</td>
                <td colSpan={5}></td>
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
    </Card>
  );
}
