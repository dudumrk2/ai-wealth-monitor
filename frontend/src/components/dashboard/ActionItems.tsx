import { useState, useEffect } from 'react';
import { CheckCircle2, Circle, AlertTriangle, Info, Zap } from 'lucide-react';
import clsx from 'clsx';
import type { ActionItem, Severity } from '../../types/portfolio';
import { Card, CardHeader, CardTitle } from '../ui/Card';
import { Badge } from '../ui/Badge';

interface ActionItemsProps {
  items: ActionItem[];
  onRefreshAI?: () => void;
  title?: string;
  className?: string;
  member1Name?: string;
  member2Name?: string;
}

const PRIORITY_DOT: Record<Severity, string> = {
  high:   'bg-red-500',
  medium: 'bg-amber-400',
  low:    'bg-emerald-500',
};
const PRIORITY_BORDER: Record<Severity, string> = {
  high:   'border-l-4 border-red-500',
  medium: 'border-l-4 border-amber-400',
  low:    'border-l-4 border-emerald-500',
};

export default function ActionItems({ 
  items: initialItems = [], 
  onRefreshAI, 
  title = "פעולות נדרשות לשיפור התיק", 
  className,
  member1Name = "חבר 1",
  member2Name = "חבר 2"
}: ActionItemsProps) {
  const [items, setItems] = useState<ActionItem[]>(initialItems);
  const [selectedItem, setSelectedItem] = useState<ActionItem | null>(null);
  const [mobileTab, setMobileTab] = useState<'user' | 'spouse' | 'shared'>('shared');

  useEffect(() => {
    setItems(initialItems);
  }, [initialItems]);

  const userItems = items.filter(i => i.owner === 'user' || !i.owner);
  const spouseItems = items.filter(i => i.owner === 'spouse');
  const sharedItems = items.filter(i => i.owner === 'shared');

  useEffect(() => {
    if (userItems.length > 0) setMobileTab('user');
    else if (spouseItems.length > 0) setMobileTab('spouse');
    else if (sharedItems.length > 0) setMobileTab('shared');
  }, [items.length]); // Only reset when count changes to avoid flickering during local state toggles

  const toggleItem = (id: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevents modal from opening when clicking checkbox
    setItems(items.map(item =>
      item.id === id ? { ...item, is_completed: !item.is_completed } : item
    ));
  };


  const renderItem = (item: ActionItem) => (
    <div
      key={item.id}
      id={`action-item-${item.id}`}
      className={clsx(
        "group flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors",
        "border-b border-slate-100 dark:border-slate-800",
        item.severity ? PRIORITY_BORDER[item.severity] : '',
        item.is_completed && "opacity-60 bg-slate-50/50 dark:bg-slate-800/50"
      )}
      onClick={() => setSelectedItem(item)}
    >
      <button 
        className={clsx("shrink-0 transition-colors", item.is_completed ? "text-emerald-500" : "text-slate-300 group-hover:text-blue-500")}
        onClick={(e) => toggleItem(item.id, e)}
      >
        {item.is_completed ? <CheckCircle2 className="w-6 h-6" /> : <Circle className="w-6 h-6" />}
      </button>

      <div className="flex-1 min-w-0 flex items-center gap-2">
        {item.severity && <span className={clsx("w-2 h-2 rounded-full shrink-0", PRIORITY_DOT[item.severity])} />}
        <h3 className={clsx("font-bold text-base truncate", item.is_completed ? "text-slate-500 dark:text-slate-500 line-through" : "text-slate-900 dark:text-slate-100")}>
          {item.title}
        </h3>
      </div>
      

    </div>
  );

  const getSortedItems = (itemsList: ActionItem[]) => {
    const priorityScore: Record<string, number> = { high: 3, medium: 2, low: 1 };
    return [...itemsList].sort((a, b) => (priorityScore[b.severity || 'low'] || 0) - (priorityScore[a.severity || 'low'] || 0));
  };

  const allSortedItems = getSortedItems(items);

  return (
    <>
      <Card className={className}>
        <CardHeader className="flex flex-row items-center justify-between gap-2 p-4 md:p-5 border-b border-slate-100 dark:border-slate-800/60">
            <CardTitle className="text-base md:text-xl font-black text-slate-800 dark:text-slate-100 truncate flex-1">
              {title}
            </CardTitle>
            
            <div className="shrink-0">
              {onRefreshAI && (
                <button 
                  onClick={onRefreshAI}
                  className="flex items-center justify-center gap-1.5 text-[10px] md:text-xs font-bold text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-all bg-blue-50 dark:bg-blue-900/30 px-3 py-2 rounded-xl border border-blue-100 dark:border-blue-800 active:scale-95"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span className="hidden xs:inline">רענן המלצות</span>
                  <span className="xs:hidden text-[9px]">רענן</span>
                </button>
              )}
            </div>
        </CardHeader>

        <div className="p-0 max-h-[600px] overflow-y-auto custom-scrollbar">
          {items.length === 0 ? (
            <div className="p-8 text-center text-slate-500 dark:text-slate-400">
               <CheckCircle2 className="w-10 h-10 mx-auto mb-3 text-emerald-400" />
               <p>הכל מעודכן! אין פעולות ממתינות.</p>
            </div>
          ) : (
            <>
              {/* Desktop View */}
              <div className="hidden md:flex flex-col">
                {(userItems.length > 0 || spouseItems.length > 0) && (
                  <div className={clsx("grid", userItems.length > 0 && spouseItems.length > 0 ? "grid-cols-2" : "grid-cols-1")}>
                    {userItems.length > 0 && (
                      <div className={clsx(spouseItems.length > 0 && "border-l border-slate-100 dark:border-slate-800/60")}>
                        <div className="px-5 py-2 bg-slate-50 dark:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/60 sticky top-0 z-10 backdrop-blur-sm">
                          <span className="text-[11px] font-black text-slate-500 dark:text-slate-400 uppercase tracking-widest flex items-center gap-2">
                            <span>👤</span> {member1Name}
                          </span>
                        </div>
                        {getSortedItems(userItems).map(renderItem)}
                      </div>
                    )}
                    {spouseItems.length > 0 && (
                      <div>
                        <div className="px-5 py-2 bg-slate-50 dark:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/60 sticky top-0 z-10 backdrop-blur-sm">
                          <span className="text-[11px] font-black text-slate-500 dark:text-slate-400 uppercase tracking-widest flex items-center gap-2">
                            <span>👤</span> {member2Name}
                          </span>
                        </div>
                        {getSortedItems(spouseItems).map(renderItem)}
                      </div>
                    )}
                  </div>
                )}
                {sharedItems.length > 0 && (
                  <div className={clsx((userItems.length > 0 || spouseItems.length > 0) && "border-t border-slate-100 dark:border-slate-800/60")}>
                    <div className="px-5 py-2 bg-slate-50 dark:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/60 sticky top-0 z-10 backdrop-blur-sm">
                      <span className="text-[11px] font-black text-slate-500 dark:text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <span>🔗</span> משותף
                      </span>
                    </div>
                    <div className={clsx("grid", sharedItems.length > 1 ? "grid-cols-2" : "grid-cols-1")}>
                      {getSortedItems(sharedItems).map((item, idx) => (
                        <div key={item.id} className={clsx("border-slate-100 dark:border-slate-800", sharedItems.length > 1 && idx % 2 === 0 && "border-l")}>
                          {renderItem(item)}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="md:hidden flex flex-col">
                {(() => {
                  const activeTabs = [
                    userItems.length > 0,
                    spouseItems.length > 0,
                    sharedItems.length > 0
                  ].filter(Boolean).length;
                  
                  if (activeTabs === 0) return null;
                  
                  return (
                    <div className={clsx(
                      "grid p-1 mx-4 mt-4 rounded-xl bg-slate-100 dark:bg-slate-800/50",
                      activeTabs === 1 ? "grid-cols-1" : activeTabs === 2 ? "grid-cols-2" : "grid-cols-3"
                    )}>
                      {userItems.length > 0 && (
                      <button
                        onClick={() => setMobileTab('user')}
                        className={clsx(
                          "px-2 py-1.5 text-[10px] font-bold rounded-lg transition-all truncate",
                          mobileTab === 'user' ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm" : "text-slate-500"
                        )}
                      >
                        {member1Name}
                      </button>
                    )}
                    {spouseItems.length > 0 && (
                      <button
                        onClick={() => setMobileTab('spouse')}
                        className={clsx(
                          "px-2 py-1.5 text-[10px] font-bold rounded-lg transition-all truncate",
                          mobileTab === 'spouse' ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm" : "text-slate-500"
                        )}
                      >
                        {member2Name}
                      </button>
                    )}
                    {sharedItems.length > 0 && (
                      <button
                        onClick={() => setMobileTab('shared')}
                        className={clsx(
                          "px-2 py-1.5 text-[10px] font-bold rounded-lg transition-all truncate",
                          mobileTab === 'shared' ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm" : "text-slate-500"
                        )}
                      >
                        משותף
                      </button>
                    )}
                  </div>
                  );
                })()}
                <div className="mt-2 border-t border-slate-100 dark:border-slate-800/60">
                  {mobileTab === 'user' && getSortedItems(userItems).map(renderItem)}
                  {mobileTab === 'spouse' && getSortedItems(spouseItems).map(renderItem)}
                  {mobileTab === 'shared' && getSortedItems(sharedItems).map(renderItem)}
                </div>
              </div>
            </>
          )}
        </div>
      </Card>

      {selectedItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
             onClick={() => setSelectedItem(null)}>
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200" 
               onClick={e => e.stopPropagation()} dir="rtl">
            <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-start justify-between">
               <div className="flex items-center gap-3">
                 <button 
                    className={clsx("shrink-0 transition-colors", selectedItem.is_completed ? "text-emerald-500" : "text-slate-300 hover:text-blue-500")}
                    onClick={(e) => toggleItem(selectedItem.id, e)}
                 >
                   {selectedItem.is_completed ? <CheckCircle2 className="w-7 h-7" /> : <Circle className="w-7 h-7" />}
                 </button>
                                   <h2 className={clsx("font-bold text-xl", selectedItem.is_completed ? "line-through text-slate-500" : "text-slate-900 dark:text-slate-100")}>
                   {selectedItem.title}
                 </h2>
               </div>
               <button onClick={() => setSelectedItem(null)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 p-1">
                 <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                   <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                 </svg>
               </button>
            </div>
            
            <div className="p-6 space-y-6 overflow-y-auto flex-1 custom-scrollbar">
               {(selectedItem.problem_explanation || selectedItem.action_required) ? (
                 <>
                   {selectedItem.problem_explanation && (
                     <div>
                                               <h4 className="font-bold text-red-600 dark:text-red-400 flex items-center gap-2 mb-2">
                         <AlertTriangle className="w-5 h-5" />
                         הסבר בעיה
                       </h4>
                       <p className="text-slate-700 dark:text-slate-300 leading-relaxed bg-red-50/50 dark:bg-red-900/10 p-4 rounded-xl border border-red-100 dark:border-red-900/30">
                         {selectedItem.problem_explanation}
                       </p>
                     </div>
                   )}
                   {selectedItem.action_required && (
                     <div>
                                               <h4 className="font-bold text-blue-600 dark:text-blue-400 flex items-center gap-2 mb-2">
                         <Zap className="w-5 h-5" />
                         מה צריך לעשות
                       </h4>
                       <p className="text-slate-700 dark:text-slate-300 leading-relaxed bg-blue-50/50 dark:bg-blue-900/10 p-4 rounded-xl border border-blue-100 dark:border-blue-900/30">
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

            <div className="p-4 bg-slate-50 dark:bg-slate-800/50 border-t border-slate-100 dark:border-slate-800 flex justify-end">
              <button 
                onClick={() => setSelectedItem(null)}
                className="px-6 py-2 bg-slate-900 dark:bg-blue-600 text-white rounded-lg font-medium hover:bg-slate-800 dark:hover:bg-blue-700 transition-colors"
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
