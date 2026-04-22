import { useState, useEffect } from 'react';
import { X, Plus, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { useAuth } from '../../context/AuthContext';
import type { StockHolding } from '../../types/stocks';
import { API_URL } from '../../lib/api';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  initialData?: StockHolding | null;
}

export default function ManualStockModal({ isOpen, onClose, onSuccess, initialData }: Props) {
  const { user } = useAuth();
  const [isCash, setIsCash] = useState(false);
  const [symbol, setSymbol] = useState('');
  const [name, setName] = useState('');
  const [qty, setQty] = useState('');
  const [avgCost, setAvgCost] = useState('');
  const [currency, setCurrency] = useState('ILS'); // Cash often ILS
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && initialData) {
      const isInitialCash = initialData.sector === 'cash';
      setIsCash(isInitialCash);
      setSymbol(initialData.symbol);
      setName(initialData.name);
      setQty((initialData.qty ?? initialData.shares ?? '').toString());
      setAvgCost((initialData.avgCostPrice ?? '').toString());
      setCurrency(initialData.currency || 'ILS');
    } else if (isOpen) {
      // reseting state for new entry
      setIsCash(false);
      setSymbol('');
      setName('');
      setQty('');
      setAvgCost('');
      setCurrency('ILS');
    }
  }, [isOpen, initialData]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;
    setLoading(true);
    setError(null);

    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`${API_URL}/api/portfolio/stock/manual`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          symbol: isCash ? (initialData ? initialData.symbol : 'CASH') : symbol,
          name,
          qty: parseFloat(qty),
          avgCostPrice: isCash ? 1.0 : parseFloat(avgCost),
          currency,
          is_cash: isCash,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'שגיאה בשמירת הנייר');
      }

      onSuccess();
      onClose();
      // Reset
      setSymbol('');
      setName('');
      setQty('');
      setAvgCost('');
      setIsCash(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose} dir="rtl">
      <div 
        className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-md flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-slate-800">
          <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <Plus className="w-5 h-5 text-blue-500" />
            {initialData ? 'עדכון נייר/מזומן' : 'הוספת נייר ערך ידני'}
          </h2>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-full transition-colors">
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Type Toggle */}
          <div className="flex p-1 bg-slate-100 dark:bg-slate-800 rounded-xl mb-4">
            <button
              type="button"
              onClick={() => setIsCash(false)}
              className={clsx(
                "flex-1 py-2 text-xs font-bold rounded-lg transition-all font-sans",
                !isCash
                  ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
              )}
            >
              ניירות ערך
            </button>
            <button
              type="button"
              onClick={() => setIsCash(true)}
              className={clsx(
                "flex-1 py-2 text-xs font-bold rounded-lg transition-all font-sans",
                isCash
                  ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
              )}
            >
              מזומן
            </button>
          </div>

          {!isCash && (
            <div>
              <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5 font-sans">סמל נייר (Ticker)</label>
              <input
                type="text" required={!isCash}
                disabled={!!initialData && !isCash}
                value={symbol}
                onChange={e => setSymbol(e.target.value.toUpperCase())}
                placeholder="E.g. AAPL or 5138409"
                className={clsx(
                  "w-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500 transition-all text-slate-900 dark:text-slate-100 font-sans",
                  !!initialData && !isCash && "opacity-50 cursor-not-allowed bg-slate-50 dark:bg-slate-800"
                )}
                dir="ltr"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5 font-sans">{isCash ? 'תיאור (למשל: עו"ש פועלים)' : 'שם הנייר'}</label>
            <input
              type="text" required
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder={isCash ? 'תיאור או שם חשבון' : 'שם החברה או הקרן'}
              className="w-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500 transition-all text-slate-900 dark:text-slate-100 text-right font-sans"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5 font-sans">{isCash ? 'סכום (Balance)' : 'כמות (Units)'}</label>
              <input
                type="number" step="any" required
                value={qty}
                onChange={e => setQty(e.target.value)}
                className="w-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500 transition-all text-slate-900 dark:text-slate-100 text-center font-sans"
              />
            </div>
            {!isCash && (
              <div>
                <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5 font-sans">מחיר קנייה ממוצע</label>
                <input
                  type="number" step="any" required={!isCash}
                  value={avgCost}
                  onChange={e => setAvgCost(e.target.value)}
                  className="w-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-blue-500 transition-all text-slate-900 dark:text-slate-100 text-center font-sans"
                />
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5 font-sans">מטבע</label>
            <div className="flex p-1 bg-slate-100 dark:bg-slate-800 rounded-xl">
              {['USD', 'ILS'].map(cur => (
                <button
                  key={cur}
                  type="button"
                  onClick={() => setCurrency(cur)}
                  className={clsx(
                    "flex-1 py-2 text-xs font-bold rounded-lg transition-all font-sans",
                    currency === cur 
                      ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm" 
                      : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
                  )}
                >
                  {cur === 'USD' ? 'דולר ($)' : 'שקל (₪)'}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-900/30 rounded-xl text-xs text-red-600 dark:text-red-400 font-sans">
              {error}
            </div>
          )}

          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold py-3 rounded-xl shadow-lg shadow-blue-500/20 transition-all active:scale-95 flex items-center justify-center gap-2 font-sans"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {initialData ? 'שמור עדכון' : 'הוסף'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
