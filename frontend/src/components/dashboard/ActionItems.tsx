import { useState, useEffect } from 'react';
import { CheckCircle2, Circle, AlertTriangle, Info, Zap } from 'lucide-react';
import clsx from 'clsx';
import type { ActionItem } from '../../types/portfolio';

interface ActionItemsProps {
  items: ActionItem[];
}

export default function ActionItems({ items: initialItems = [] }: ActionItemsProps) {
  const [items, setItems] = useState<ActionItem[]>(initialItems);
  const [selectedItem, setSelectedItem] = useState<ActionItem | null>(null);

  useEffect(() => {
    setItems(initialItems);
  }, [initialItems]);

  const toggleItem = (id: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevents modal from opening when clicking checkbox
    setItems(items.map(item =>
      item.id === id ? { ...item, is_completed: !item.is_completed } : item
    ));
  };

  const pending = items.filter(i => !i.is_completed).length;

  return (
    <>
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
           <h2 className="font-bold text-lg text-slate-800 flex items-center gap-2">
              פעולות נדרשות לשיפור התיק
              {pending > 0 && (
                <span className="bg-blue-100 text-blue-700 text-xs py-0.5 px-2.5 rounded-full font-bold">
                  {pending} ממתינות
                </span>
              )}
           </h2>
        </div>

        <div className="p-0 max-h-[600px] overflow-y-auto custom-scrollbar">
          {items.length === 0 ? (
            <div className="p-8 text-center text-slate-500">
               <CheckCircle2 className="w-10 h-10 mx-auto mb-3 text-emerald-400" />
               <p>הכל מעודכן! אין פעולות ממתינות.</p>
            </div>
          ) : (
            <div className="flex flex-col">
              {items.map((item, index) => {
                return (
                  <div
                    key={item.id}
                    id={`action-item-${item.id}`}
                    className={clsx(
                      "group flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-slate-50 transition-colors",
                      index !== items.length - 1 && "border-b border-slate-100",
                      item.is_completed && "opacity-60 bg-slate-50/50"
                    )}
                    onClick={() => setSelectedItem(item)}
                  >
                    <button 
                      className={clsx("shrink-0 transition-colors", item.is_completed ? "text-emerald-500" : "text-slate-300 group-hover:text-blue-500")}
                      onClick={(e) => toggleItem(item.id, e)}
                    >
                      {item.is_completed ? <CheckCircle2 className="w-6 h-6" /> : <Circle className="w-6 h-6" />}
                    </button>

                    <div className="flex-1 min-w-0">
                      <h3 className={clsx("font-bold text-base truncate", item.is_completed ? "text-slate-500 line-through" : "text-slate-900")}>
                        {item.title}
                      </h3>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {selectedItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
             onClick={() => setSelectedItem(null)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl overflow-hidden" 
               onClick={e => e.stopPropagation()} dir="rtl">
            <div className="p-6 border-b border-slate-100 flex items-start justify-between">
               <div className="flex items-center gap-3">
                 <button 
                    className={clsx("shrink-0 transition-colors", selectedItem.is_completed ? "text-emerald-500" : "text-slate-300 hover:text-blue-500")}
                    onClick={(e) => toggleItem(selectedItem.id, e)}
                 >
                   {selectedItem.is_completed ? <CheckCircle2 className="w-7 h-7" /> : <Circle className="w-7 h-7" />}
                 </button>
                 <h2 className={clsx("font-bold text-xl", selectedItem.is_completed ? "line-through text-slate-500" : "text-slate-900")}>
                   {selectedItem.title}
                 </h2>
               </div>
               <button onClick={() => setSelectedItem(null)} className="text-slate-400 hover:text-slate-600 p-1">
                 <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                   <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                 </svg>
               </button>
            </div>
            
            <div className="p-6 space-y-6">
               {(selectedItem.problem_explanation || selectedItem.action_required) ? (
                 <>
                   {selectedItem.problem_explanation && (
                     <div>
                       <h4 className="font-bold text-red-600 flex items-center gap-2 mb-2">
                         <AlertTriangle className="w-5 h-5" />
                         הסבר בעיה
                       </h4>
                       <p className="text-slate-700 leading-relaxed bg-red-50/50 p-4 rounded-xl border border-red-100">
                         {selectedItem.problem_explanation}
                       </p>
                     </div>
                   )}
                   {selectedItem.action_required && (
                     <div>
                       <h4 className="font-bold text-blue-600 flex items-center gap-2 mb-2">
                         <Zap className="w-5 h-5" />
                         מה צריך לעשות
                       </h4>
                       <p className="text-slate-700 leading-relaxed bg-blue-50/50 p-4 rounded-xl border border-blue-100">
                         {selectedItem.action_required}
                       </p>
                     </div>
                   )}
                 </>
               ) : (
                 // Fallback for older data that only has 'description'
                 <div>
                   <h4 className="font-bold text-slate-800 flex items-center gap-2 mb-2">
                     <Info className="w-5 h-5 text-blue-500" />
                     פירוט ההמלצה
                   </h4>
                   <p className="text-slate-700 leading-relaxed bg-slate-50 p-4 rounded-xl border border-slate-100">
                     {selectedItem.description}
                   </p>
                 </div>
               )}
            </div>

            <div className="p-4 bg-slate-50 border-t border-slate-100 flex justify-end">
              <button 
                onClick={() => setSelectedItem(null)}
                className="px-6 py-2 bg-slate-900 text-white rounded-lg font-medium hover:bg-slate-800 transition-colors"
              >
                סגור
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
