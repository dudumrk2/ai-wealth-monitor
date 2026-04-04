/**
 * AlternativeInvestmentsTable
 * Full-featured table for alternative investments with:
 *  - Start date + end date columns
 *  - Monthly deposit column
 *  - "+" button to add new assets via an inline modal form
 */
import { useState } from 'react';
import type { AlternativeInvestment } from '../../types/portfolio';
import { Plus, X, Trash2, TrendingUp, Calendar } from 'lucide-react';
import clsx from 'clsx';

const fmt = (val: number) =>
  new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 }).format(val);

const fmtDate = (d: string) => {
  if (!d || isNaN(Date.parse(d))) return d; // free-text like "נזיל יומי"
  return new Date(d).toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' });
};

// ─── Add New Asset Form (modal) ───────────────────────────────────────────────

interface NewAssetForm {
  name: string;
  description: string;
  balance: string;
  monthly_deposit: string;
  expected_yearly_yield: string;
  start_date: string;
  end_date: string;
}

const EMPTY_FORM: NewAssetForm = {
  name: '',
  description: '',
  balance: '',
  monthly_deposit: '',
  expected_yearly_yield: '',
  start_date: new Date().toISOString().slice(0, 10),
  end_date: '',
};

interface ModalProps {
  onSave: (item: AlternativeInvestment) => void;
  onClose: () => void;
}

function AddAssetModal({ onSave, onClose }: ModalProps) {
  const [form, setForm] = useState<NewAssetForm>(EMPTY_FORM);

  const set = (key: keyof NewAssetForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm(prev => ({ ...prev, [key]: e.target.value }));

  const isValid = form.name.trim() !== '' && form.balance.trim() !== '' && Number(form.balance) > 0;

  const handleSave = () => {
    const item: AlternativeInvestment = {
      id: `alt_${Date.now()}`,
      name: form.name.trim(),
      description: form.description.trim(),
      balance: Number(form.balance.replace(/[^\d.-]/g, '')),
      monthly_deposit: Number(form.monthly_deposit.replace(/[^\d.-]/g, '')) || 0,
      expected_yearly_yield: Number(form.expected_yearly_yield) || 0,
      start_date: form.start_date || new Date().toISOString().slice(0, 10),
      end_date: form.end_date || 'ללא הגבלה',
    };
    onSave(item);
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" dir="rtl">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-200">

        {/* Modal Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-indigo-100 dark:bg-indigo-900/30 rounded-xl flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <h3 className="font-bold text-slate-900 dark:text-slate-100 text-lg">הוספת נכס חדש</h3>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <div className="p-5 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">שם הנכס *</label>
            <input type="text" value={form.name} onChange={set('name')}
              placeholder='לדוגמה: דירה להשכרה, קרן כספית...'
              className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 text-right focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm transition-shadow placeholder:text-slate-300 dark:placeholder:text-slate-600 text-slate-900 dark:text-slate-100"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">תיאור</label>
            <input type="text" value={form.description} onChange={set('description')}
              placeholder='פרטים נוספים על הנכס'
              className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 text-right focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm transition-shadow placeholder:text-slate-300 dark:placeholder:text-slate-600 text-slate-900 dark:text-slate-100"
            />
          </div>

          {/* Balance + yield side by side */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">שווי נכס (₪) *</label>
              <input type="number" value={form.balance} onChange={set('balance')}
                placeholder="0"
                className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm text-slate-900 dark:text-slate-100"
                dir="ltr"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">תשואה שנתית (%)</label>
              <input type="number" step="0.1" value={form.expected_yearly_yield} onChange={set('expected_yearly_yield')}
                placeholder="0.0"
                className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm text-slate-900 dark:text-slate-100"
                dir="ltr"
              />
            </div>
          </div>

          {/* Monthly deposit */}
          <div>
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">הפקדה / הכנסה חודשית (₪)</label>
            <input type="number" value={form.monthly_deposit} onChange={set('monthly_deposit')}
              placeholder="0"
              className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm text-slate-900 dark:text-slate-100"
              dir="ltr"
            />
          </div>

          {/* Date range */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1 flex items-center gap-1">
                <Calendar className="w-3 h-3" /> תאריך התחלה
              </label>
              <input type="date" value={form.start_date} onChange={set('start_date')}
                className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-3 py-2.5 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm text-slate-900 dark:text-slate-100"
                dir="ltr"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1 flex items-center gap-1">
                <Calendar className="w-3 h-3" /> תאריך סיום
              </label>
              <input type="date" value={form.end_date} onChange={set('end_date')}
                placeholder="ריק = ללא הגבלה"
                className="w-full border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 rounded-xl px-3 py-2.5 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm placeholder:text-slate-300 dark:placeholder:text-slate-600 text-slate-900 dark:text-slate-100"
                dir="ltr"
              />
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">ריק = ללא הגבלה</p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-3 p-5 border-t border-slate-100 dark:border-slate-800">
          <button onClick={onClose}
            className="flex-1 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 px-4 py-3 rounded-xl font-semibold text-sm transition-colors">
            ביטול
          </button>
          <button onClick={handleSave} disabled={!isValid}
            className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 py-3 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2">
            <Plus className="w-4 h-4" /> הוסף נכס
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Table Component ─────────────────────────────────────────────────────

interface Props {
  items: AlternativeInvestment[];
}

export default function AlternativeInvestmentsTable({ items: initialItems }: Props) {
  const [items, setItems] = useState<AlternativeInvestment[]>(initialItems);
  const [showModal, setShowModal] = useState(false);

  const handleAdd = (item: AlternativeInvestment) => {
    setItems(prev => [...prev, item]);
    setShowModal(false);
  };

  const handleDelete = (id: string) => {
    setItems(prev => prev.filter(i => i.id !== id));
  };

  const totalBalance = items.reduce((s, i) => s + i.balance, 0);
  const totalMonthly = items.reduce((s, i) => s + (i.monthly_deposit || 0), 0);

  return (
    <>
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">

        {/* Table Header */}
        <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <h3 className="font-bold text-lg text-slate-800 dark:text-slate-100">השקעות אלטרנטיביות</h3>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-all active:scale-95 shadow-sm shadow-indigo-200"
          >
            <Plus className="w-4 h-4" /> הוסף נכס
          </button>
        </div>

        {/* Empty state */}
        {items.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-14 h-14 mx-auto bg-slate-100 dark:bg-slate-800 rounded-2xl flex items-center justify-center mb-4">
              <TrendingUp className="w-7 h-7 text-slate-400 dark:text-slate-600" />
            </div>
            <p className="text-slate-500 dark:text-slate-400 font-semibold mb-1">אין נכסים אלטרנטיביים</p>
            <p className="text-slate-400 text-sm mb-5">הוסף נכסים כגון נדל״ן, קרנות כספיות, פיקדונות ועוד</p>
            <button onClick={() => setShowModal(true)}
              className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-all">
              <Plus className="w-4 h-4" /> הוסף נכס ראשון
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-800 text-slate-500 dark:text-slate-400 text-xs font-bold uppercase tracking-wider">
                  <th className="px-5 py-3">שם הנכס</th>
                  <th className="px-4 py-3 text-left">שווי</th>
                  <th className="px-4 py-3 text-left">הכנסה חודשית</th>
                  <th className="px-4 py-3 text-left">תשואה</th>
                  <th className="px-4 py-3 text-left">תאריך התחלה</th>
                  <th className="px-4 py-3 text-left">תאריך סיום</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50 dark:divide-slate-800">
                {items.map((item) => (
                  <tr key={item.id}
                    className={clsx('group hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors')}>
                    <td className="px-5 py-4">
                      <p className="font-semibold text-slate-900 dark:text-slate-100">{item.name}</p>
                      {item.description && (
                        <p className="text-xs text-slate-400 mt-0.5 max-w-xs">{item.description}</p>
                      )}
                    </td>
                    <td className="px-4 py-4 text-left tabular-nums font-bold text-slate-800 dark:text-slate-100" dir="ltr">
                      {fmt(item.balance)}
                    </td>
                    <td className="px-4 py-4 text-left tabular-nums" dir="ltr">
                      {item.monthly_deposit > 0 ? (
                        <span className="text-emerald-700 dark:text-emerald-400 font-semibold">{fmt(item.monthly_deposit)}</span>
                      ) : (
                        <span className="text-slate-400 dark:text-slate-500">—</span>
                      )}
                    </td>
                    <td className="px-4 py-4 text-left">
                      <span className={clsx(
                        'font-bold text-sm',
                        item.expected_yearly_yield >= 5 ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-600 dark:text-slate-400'
                      )}>
                        {item.expected_yearly_yield > 0 ? `${item.expected_yearly_yield}%` : '—'}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-left text-slate-600 dark:text-slate-400 text-xs font-medium" dir="ltr">
                      {fmtDate(item.start_date)}
                    </td>
                    <td className="px-4 py-4 text-left text-slate-600 dark:text-slate-400 text-xs font-medium" dir="ltr">
                      {fmtDate(item.end_date)}
                    </td>
                    <td className="px-4 py-4">
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-300 dark:text-slate-600 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-all"
                        title="מחק נכס"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>

              {/* Totals row */}
              {items.length > 1 && (
                <tfoot>
                  <tr className="border-t-2 border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-800/80 font-bold">
                    <td className="px-5 py-3 text-slate-700 dark:text-slate-300">סה״כ</td>
                    <td className="px-4 py-3 text-left tabular-nums text-slate-900 dark:text-slate-100" dir="ltr">{fmt(totalBalance)}</td>
                    <td className="px-4 py-3 text-left tabular-nums text-emerald-700 dark:text-emerald-400" dir="ltr">
                      {totalMonthly > 0 ? fmt(totalMonthly) : '—'}
                    </td>
                    <td colSpan={4}></td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
      </div>

      {showModal && (
        <AddAssetModal onSave={handleAdd} onClose={() => setShowModal(false)} />
      )}
    </>
  );
}
