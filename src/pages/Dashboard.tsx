import { useState, useMemo } from 'react';
import DashboardLayout from '../components/layout/DashboardLayout';
import ActionItems from '../components/dashboard/ActionItems';
import AssetTable from '../components/dashboard/AssetTable';
import PortfolioSummaryCard from '../components/dashboard/PortfolioSummaryCard';
import AlternativeInvestmentsTable from '../components/dashboard/AlternativeInvestmentsTable';
import type { SummaryRow } from '../components/dashboard/PortfolioSummaryCard';
import { MOCK_DATA } from '../data/mockData';
import { STORAGE_KEYS } from '../lib/storageKeys';
import type { Fund, FundCategory } from '../types/portfolio';
import { CATEGORY_LABELS } from '../types/portfolio';
import clsx from 'clsx';

type TabView = 'user' | 'spouse' | 'joint';

const fmt = (val: number) =>
  new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 }).format(val);

const CATEGORY_COLORS: Record<FundCategory, string> = {
  pension:              '#3b82f6', // blue
  managers:             '#ef4444', // red/pink (classic ביטוח color)
  study:                '#10b981', // emerald
  provident:            '#f59e0b', // amber
  investment_provident: '#8b5cf6', // purple
  stocks:               '#f97316', // orange
  alternative:          '#6366f1', // indigo
};

/** Build SummaryRow[] from a funds list, grouping by category. */
function buildRows(funds: Fund[], field: 'balance' | 'monthly_deposit'): SummaryRow[] {
  const map = new Map<FundCategory, number>();
  for (const f of funds) {
    map.set(f.category, (map.get(f.category) ?? 0) + (f[field] ?? 0));
  }
  return Array.from(map.entries())
    .filter(([, v]) => v > 0)
    .map(([cat, val]) => ({
      label: CATEGORY_LABELS[cat],
      balance: val,
      color: '',
      hex: CATEGORY_COLORS[cat],
    }));
}

/** Loads family member names from localStorage. */
function useFamilyConfig() {
  return useMemo(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEYS.FAMILY_CONFIG);
      if (raw) {
        const config = JSON.parse(raw);
        return {
          member1Name: config.member1?.name || 'התיק שלי',
          member2Name: config.member2?.name || 'בן/בת הזוג',
          householdName: config.householdName || 'המשפחה',
        };
      }
    } catch { /* ignore */ }
    return { member1Name: 'התיק שלי', member2Name: 'בן/בת הזוג', householdName: 'המשפחה' };
  }, []);
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabView>('joint');
  const { member1Name, member2Name, householdName } = useFamilyConfig();

  const userFunds    = MOCK_DATA.portfolios.user.funds;
  const spouseFunds  = MOCK_DATA.portfolios.spouse.funds;
  const jointStocks  = MOCK_DATA.portfolios.joint.stock_investments as Fund[];
  const altInvest    = MOCK_DATA.portfolios.user.alternative_investments;
  const joint        = MOCK_DATA.portfolios.joint;


  const renderTabContent = () => {
    switch (activeTab) {

      // ─── Individual: Member 1 ──────────────────────────────────────────
      case 'user': {
        const balanceRows  = buildRows(userFunds, 'balance');
        const monthlyRows  = buildRows(userFunds.filter(f => f.monthly_deposit > 0), 'monthly_deposit');

        // Group funds by category for separate tables
        const categories = [...new Set(userFunds.map(f => f.category))];

        return (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Two summary cards side by side */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <PortfolioSummaryCard
                title={`סר החשבון שצברת`}
                rows={balanceRows}
                variant="balance"
              />
              <PortfolioSummaryCard
                title="סר ההפקדות החודשי"
                rows={monthlyRows}
                variant="monthly"
              />
            </div>

            {/* Fund tables per category */}
            {categories.map(cat => {
              const catFunds = userFunds.filter(f => f.category === cat);
              return (
                <AssetTable
                  key={cat}
                  title={CATEGORY_LABELS[cat]}
                  funds={catFunds}
                />
              );
            })}

            {/* Alternative investments */}
            {altInvest.length > 0 && <AlternativeInvestmentsTable items={altInvest} />}
          </div>
        );
      }

      // ─── Individual: Member 2 ──────────────────────────────────────────
      case 'spouse': {
        const balanceRows  = buildRows(spouseFunds, 'balance');
        const monthlyRows  = buildRows(spouseFunds.filter(f => f.monthly_deposit > 0), 'monthly_deposit');
        const categories   = [...new Set(spouseFunds.map(f => f.category))];

        return (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <PortfolioSummaryCard
                title="סר החשבון שצברת"
                rows={balanceRows}
                variant="balance"
              />
              <PortfolioSummaryCard
                title="סר ההפקדות החודשי"
                rows={monthlyRows}
                variant="monthly"
              />
            </div>
            {categories.map(cat => (
              <AssetTable
                key={cat}
                title={CATEGORY_LABELS[cat]}
                funds={spouseFunds.filter(f => f.category === cat)}
              />
            ))}
          </div>
        );
      }

      // ─── Joint View ────────────────────────────────────────────────────
      case 'joint':
      default: {
        const allFundsForSummary = [...userFunds, ...spouseFunds, ...jointStocks];
        const balanceRows = buildRows(allFundsForSummary, 'balance');
        const monthlyRows = buildRows(
          allFundsForSummary.filter(f => f.monthly_deposit > 0),
          'monthly_deposit'
        );

        // Group all joint funds by category (for separate tables)
        const jointUserFunds   = userFunds.map(f  => ({ ...f, _owner: member1Name }));
        const jointSpouseFunds = spouseFunds.map(f => ({ ...f, _owner: member2Name }));
        const categories = [...new Set([...userFunds, ...spouseFunds].map(f => f.category))];

        return (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">

            {/* Two summary cards side by side */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <PortfolioSummaryCard
                title={`סר החשבון המשפחתי — ${householdName}`}
                rows={balanceRows}
                variant="balance"
              />
              <PortfolioSummaryCard
                title="סר ההפקדות החודשיות"
                rows={monthlyRows}
                variant="monthly"
              />
            </div>

            {/* Total wealth hero card */}
            <div className="bg-slate-900 text-white p-8 rounded-3xl shadow-xl relative overflow-hidden">
              <div className="absolute left-0 bottom-0 w-64 h-64 bg-blue-500/20 rounded-full blur-3xl translate-x-1/2 translate-y-1/2 pointer-events-none"></div>
              <p className="text-slate-400 text-sm font-medium mb-1">עושר משפחתי מאוחד — {householdName}</p>
              <h2 className="text-3xl font-bold tracking-tight mb-4 tabular-nums" dir="ltr">
                {fmt(joint.total_family_wealth)}
              </h2>
              <div className="flex gap-3 flex-wrap">
                <div className="flex items-center gap-2 bg-white/10 rounded-full px-3 py-1 text-sm">
                  <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                  <span className="text-slate-300">{member1Name}</span>
                </div>
                <div className="flex items-center gap-2 bg-white/10 rounded-full px-3 py-1 text-sm">
                  <div className="w-2 h-2 bg-emerald-400 rounded-full"></div>
                  <span className="text-slate-300">{member2Name}</span>
                </div>
              </div>
            </div>

            {/* Per-category aggregated tables — owner column shows who has what */}
            {categories.map(cat => {
              const catFunds = [
                ...jointUserFunds.filter(f => f.category === cat),
                ...jointSpouseFunds.filter(f => f.category === cat),
              ];
              if (catFunds.length === 0) return null;
              return (
                <AssetTable
                  key={cat}
                  title={`${CATEGORY_LABELS[cat]} — כלל המשפחה`}
                  funds={catFunds}
                  ownerColumn={catFunds.some(f => f._owner)}
                />
              );
            })}

            {/* Stock portfolio — joint only */}
            {jointStocks.length > 0 && (
              <AssetTable title="תיק מניות משפחתי" funds={jointStocks} />
            )}

            {/* Alternative investments — joint only */}
            {altInvest.length > 0 && <AlternativeInvestmentsTable items={altInvest} />}

            {/* Asset allocation & provider exposure */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white p-6 rounded-2xl border border-slate-200">
                <h3 className="font-bold text-slate-800 mb-4 text-lg">פיזור נכסים</h3>
                <div className="space-y-4">
                  {[
                    { label: 'מניות', pct: joint.asset_allocation_percentages.stocks, color: 'bg-blue-600' },
                    { label: 'אג״ח', pct: joint.asset_allocation_percentages.bonds, color: 'bg-emerald-500' },
                    { label: 'מזומן ושווי מזומן', pct: joint.asset_allocation_percentages.cash_equivalents, color: 'bg-amber-400' },
                  ].map(({ label, pct, color }) => (
                    <div key={label}>
                      <div className="flex justify-between text-sm font-semibold mb-1.5">
                        <span className="text-slate-600">{label}</span>
                        <span className="text-slate-900">{pct}%</span>
                      </div>
                      <div className="w-full bg-slate-100 rounded-full h-2.5">
                        <div className={`${color} h-2.5 rounded-full`} style={{ width: `${pct}%` }}></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white p-6 rounded-2xl border border-slate-200">
                <h3 className="font-bold text-slate-800 mb-4 text-lg">חשיפה לספקים</h3>
                <div className="space-y-3">
                  {Object.entries(joint.provider_exposure).map(([provider, value]) => (
                    <div key={provider} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg text-sm font-semibold">
                      <span className="text-slate-700">{provider}</span>
                      <span className="text-slate-900">{value as number}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        );
      }
    }
  };

  return (
    <DashboardLayout>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">סקירת נכסים</h1>
        <p className="text-slate-500 mt-1">עקוב, נתח ומטב את עתיד משפחתך.</p>
      </div>

      <div className="flex flex-col xl:flex-row gap-8">
        <div className="flex-1 min-w-0">
          <div className="bg-slate-200/50 p-1 rounded-xl inline-flex mb-6 overflow-x-auto max-w-full">
            {([
              { id: 'joint',  label: 'תצוגה משותפת' },
              { id: 'user',   label: member1Name },
              { id: 'spouse', label: member2Name },
            ] as const).map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={clsx(
                  "px-6 py-2.5 rounded-lg text-sm font-bold transition-all whitespace-nowrap",
                  activeTab === tab.id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
                )}>
                {tab.label}
              </button>
            ))}
          </div>
          {renderTabContent()}
        </div>

        <div className="xl:w-80 shrink-0">
          <ActionItems />
        </div>
      </div>
    </DashboardLayout>
  );
}


