import { useState } from 'react';
import { MOCK_DATA } from '../../data/mockData';
import { CheckCircle2, Circle, AlertTriangle, Info, Zap } from 'lucide-react';
import clsx from 'clsx';
import type { Severity, ActionItem } from '../../types/portfolio';

export default function ActionItems() {
  const [items, setItems] = useState<ActionItem[]>(MOCK_DATA.action_items);

  const toggleItem = (id: string) => {
    setItems(items.map(item =>
      item.id === id ? { ...item, is_completed: !item.is_completed } : item
    ));
  };

  const getSeverityConfig = (severity: Severity) => {
    switch (severity) {
      case 'high':   return { icon: AlertTriangle, color: 'text-red-500',   bg: 'bg-red-50',   border: 'border-red-100' };
      case 'medium': return { icon: Zap,           color: 'text-amber-500', bg: 'bg-amber-50', border: 'border-amber-100' };
      default:       return { icon: Info,          color: 'text-blue-500',  bg: 'bg-blue-50',  border: 'border-blue-100' };
    }
  };

  const pending = items.filter(i => !i.is_completed).length;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden sticky top-24">
      <div className="p-5 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
         <h2 className="font-bold text-lg text-slate-800 flex items-center gap-2">
            פעולות נדרשות
            {pending > 0 && (
              <span className="bg-blue-100 text-blue-700 text-xs py-0.5 px-2.5 rounded-full font-bold">
                {pending} ממתינות
              </span>
            )}
         </h2>
      </div>

      <div className="p-3">
        {items.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
             <CheckCircle2 className="w-10 h-10 mx-auto mb-3 text-emerald-400" />
             <p>הכל מעודכן! אין פעולות ממתינות.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => {
              const { icon: Icon, color, bg, border } = getSeverityConfig(item.severity);

              return (
                <div
                  key={item.id}
                  id={`action-item-${item.id}`}
                  className={clsx(
                    "relative group rounded-xl p-4 border transition-all cursor-pointer hover:shadow-md",
                    item.is_completed ? "bg-slate-50 border-slate-200 opacity-60" : `${bg} ${border}`
                  )}
                  onClick={() => toggleItem(item.id)}
                >
                  <div className="flex gap-4">
                    <button className={clsx("mt-1 shrink-0 transition-colors", item.is_completed ? "text-emerald-500" : "text-slate-300 group-hover:text-blue-500")}>
                      {item.is_completed ? <CheckCircle2 className="w-6 h-6" /> : <Circle className="w-6 h-6" />}
                    </button>

                    <div className="flex-1">
                      <div className="flex gap-2 items-center mb-1">
                        {!item.is_completed && <Icon className={clsx("w-4 h-4 shrink-0", color)} />}
                        <h3 className={clsx("font-semibold text-sm", item.is_completed ? "text-slate-500 line-through" : "text-slate-900")}>
                          {item.title}
                        </h3>
                      </div>
                      <p className={clsx("text-sm leading-relaxed", item.is_completed ? "text-slate-400" : "text-slate-600")}>
                        {item.description}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
