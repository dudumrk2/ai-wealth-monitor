import { X, TrendingUp, AlertCircle } from 'lucide-react';
import clsx from 'clsx';

interface Competitor {
  provider_name?: string;
  fund_name?: string;
  management_fee_accumulation?: number;
  yield_1yr?: number;
  yield_3yr?: number;
  yield_5yr?: number;
  sharpe_ratio?: number;
}

interface CompetitorModalProps {
  isOpen: boolean;
  onClose: () => void;
  product: any | null; // using any to match AssetTable's local Fund for now, or we can use the exact type
  productType?: string; // We'll pass `title` from AssetTable as productType
}

export default function CompetitorModal({ isOpen, onClose, product, productType }: CompetitorModalProps) {
  if (!isOpen || !product) return null;

  const competitors: Competitor[] = product.top_competitors || product.competitors || [];

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 }).format(val || 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose} dir="rtl">
      <div 
        className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
          <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100">
            השוואת מתחרים: {productType ? `${productType} - ` : ''}{product.track_name}
          </h2>
          <button 
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-800 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="overflow-x-auto">
            <table className="w-full text-right border-collapse">
              <thead>
                <tr className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-semibold text-sm">
                  <th className="p-4 rounded-tr-lg border-b border-white dark:border-slate-800">ספק / חברה</th>
                  <th className="p-4 border-b border-white dark:border-slate-800">יתרה (₪)</th>
                  <th className="p-4 border-b border-white dark:border-slate-800">דמי ניהול (צבירה)</th>
                  <th className="p-4 border-b border-white dark:border-slate-800">מדד שארפ</th>
                  <th className="p-4 border-b border-white dark:border-slate-800">תשואה 1Y</th>
                  <th className="p-4 border-b border-white dark:border-slate-800">תשואה 3Y</th>
                  <th className="p-4 rounded-tl-lg border-b border-white dark:border-slate-800">תשואה 5Y</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {/* User's Product */}
                <tr className="bg-blue-50/50 dark:bg-blue-900/20 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors border-2 border-blue-100 dark:border-blue-900/50 shadow-sm relative z-10">
                  <td className="p-4 font-bold text-blue-900 dark:text-blue-100 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                    {product.provider_name} (המוצר שלך)
                  </td>
                  <td className="p-4 font-medium text-blue-900 dark:text-blue-100 tabular-nums" dir="ltr">
                    {formatCurrency(product.balance)}
                  </td>
                  <td className="p-4 font-medium text-blue-900 dark:text-blue-100 tabular-nums" dir="ltr">
                    {product.management_fee_accumulation ?? '—'}%
                  </td>
                  <td className="p-4 font-medium text-blue-800/70 dark:text-blue-200/70 tabular-nums" dir="ltr">
                    {product.sharpe_ratio ? product.sharpe_ratio.toFixed(2) : '—'}
                  </td>
                  <td className="p-4">
                    <div className={clsx("inline-flex items-center gap-1 font-bold tabular-nums", product.yield_1yr > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-slate-600 dark:text-slate-400")} dir="ltr">
                      {product.yield_1yr > 0 && <TrendingUp className="w-3 h-3" />}
                      {product.yield_1yr ?? '—'}%
                    </div>
                  </td>
                  <td className="p-4">
                    <div className={clsx("inline-flex items-center gap-1 font-bold tabular-nums", product.yield_3yr > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-slate-600 dark:text-slate-400")} dir="ltr">
                      {product.yield_3yr > 0 && <TrendingUp className="w-3 h-3" />}
                      {product.yield_3yr ?? '—'}%
                    </div>
                  </td>
                  <td className="p-4">
                    <div className={clsx("inline-flex items-center gap-1 font-bold tabular-nums", (product.yield_5yr || 0) > 0 ? "text-emerald-600" : "text-slate-600")} dir="ltr">
                      {(product.yield_5yr || 0) > 0 && <TrendingUp className="w-3 h-3" />}
                      {product.yield_5yr ?? '—'}%
                    </div>
                  </td>
                </tr>

                {/* Spacing row */}
                <tr>
                  <td colSpan={7} className="p-2 bg-white dark:bg-slate-900"></td>
                </tr>

                {/* Header for Competitors */}
                <tr>
                  <td colSpan={7} className="p-4 font-bold text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/50 border-y border-slate-200 dark:border-slate-800">
                    מוצרים מתחרים מובילים באותו מסלול:
                  </td>
                </tr>

                {/* Competitors List */}
                {competitors.length > 0 ? (
                  competitors.map((comp, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                      <td className="p-4">
                        <div className="font-semibold text-slate-700 dark:text-slate-300">
                          {comp.provider_name || 'לא ידוע'}
                        </div>
                        {comp.fund_name && (
                          <div className="text-xs text-slate-400 font-normal mt-0.5 max-w-xs truncate" title={comp.fund_name}>
                            {comp.fund_name}
                          </div>
                        )}
                      </td>
                      <td className="p-4 text-slate-400 dark:text-slate-500 text-sm">
                        —
                      </td>
                      <td className="p-4 font-medium text-slate-700 dark:text-slate-300 tabular-nums" dir="ltr">
                        {comp.management_fee_accumulation ?? '—'}%
                      </td>
                      <td className="p-4 text-slate-700 dark:text-slate-300 font-medium tabular-nums" dir="ltr">
                        {comp.sharpe_ratio ? comp.sharpe_ratio.toFixed(2) : '—'}
                      </td>
                      <td className="p-4 text-slate-700 dark:text-slate-300 font-medium tabular-nums" dir="ltr">
                        {comp.yield_1yr ? `${comp.yield_1yr}%` : '—'}
                      </td>
                      <td className="p-4 text-slate-700 dark:text-slate-300 font-medium tabular-nums" dir="ltr">
                        {comp.yield_3yr ? `${comp.yield_3yr}%` : '—'}
                      </td>
                      <td className="p-4 text-slate-700 dark:text-slate-300 font-medium tabular-nums" dir="ltr">
                        {comp.yield_5yr ? `${comp.yield_5yr}%` : '—'}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="p-8 text-center bg-slate-50/50 dark:bg-slate-800/30 text-slate-500 dark:text-slate-400 rounded-b-lg">
                      <div className="flex flex-col items-center gap-3">
                        <AlertCircle className="w-8 h-8 text-slate-300 dark:text-slate-600" />
                        <span className="font-medium text-sm">לא נמצאו נתוני מתחרים למסלול זה.</span>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
