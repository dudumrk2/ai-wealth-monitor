import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { Card, CardHeader, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';

const fmt = (val: number) =>
  new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 }).format(val);

export interface SummaryRow {
  label: string;
  balance: number;
  color: string;
  hex: string;
}

interface Props {
  title: string;
  totalLabel?: string;
  rows: SummaryRow[];
  variant?: 'balance' | 'monthly';
}

function DonutChart({ rows, variant = 'balance' }: { rows: SummaryRow[]; variant?: 'balance' | 'monthly' }) {
  const total = rows.reduce((s, row) => s + row.balance, 0);
  if (total === 0) return null;

  const isMonthly = variant === 'monthly';
  const chartData = rows.filter(r => r.balance > 0);

  return (
    <div className="w-[100px] h-[100px] md:w-[120px] md:h-[120px] shrink-0 relative">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          {isMonthly && (
            <Pie
              data={[{ value: 1 }]}
              cx="50%"
              cy="50%"
              innerRadius="75%"
              outerRadius="95%"
              fill="transparent"
              stroke="#e2e8f0"
              strokeWidth={1}
              strokeDasharray="4 2"
              dataKey="value"
              isAnimationActive={false}
              opacity={0.5}
            />
          )}
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius="65%"
            outerRadius="95%"
            paddingAngle={chartData.length > 1 ? 2 : 0}
            dataKey="balance"
            stroke="none"
            animationBegin={0}
            animationDuration={1200}
            animationEasing="ease-out"
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.hex} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      
      {/* Center Label */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none pb-1">
        <span className="text-[10px] md:text-xs font-bold text-slate-800 dark:text-slate-100 font-sans">
          {isMonthly ? '₪/חו' : '%'}
        </span>
      </div>
    </div>
  );
}

export default function PortfolioSummaryCard({ title, totalLabel, rows, variant = 'balance' }: Props) {
  const total = rows.reduce((s, r) => s + r.balance, 0);
  const activeRows = rows.filter(r => r.balance > 0);
  const isMonthly = variant === 'monthly';

  return (
    <Card className="mb-0">
      {/* Header */}
      <CardHeader className="flex flex-row items-center justify-between gap-4 p-4 md:p-6 border-b border-slate-100 dark:border-slate-800">
        <div className="min-w-0">
          <p className="text-sm font-bold text-slate-500 dark:text-slate-500 mb-0.5 truncate">{title}</p>
          {totalLabel && <p className="text-xs text-slate-400 dark:text-slate-500 mb-1">{totalLabel}</p>}
          <p className="text-xl md:text-3xl font-bold text-slate-900 dark:text-slate-100 tabular-nums truncate" dir="ltr">{fmt(total)}</p>
        </div>
        <DonutChart rows={activeRows} variant={variant} />
      </CardHeader>

      {/* Table */}
      <CardContent className="p-4">
        <p className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-3">
          {isMonthly ? 'התפלגות ההפקדה החודשית לפי סוג מוצר' : 'התפלגות החשבון לפי סוג מוצר'}
        </p>
        <table className="w-full text-right text-sm border-collapse">
          <thead>
            <tr className="text-xs text-slate-400 dark:text-slate-500 font-semibold">
              <th className="pb-2 font-semibold">סוג מוצר</th>
              <th className="pb-2 text-left font-semibold">{isMonthly ? 'הפקדה' : 'צבירה'}</th>
              <th className="pb-2 text-left font-semibold w-16">חלק יחסי</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50 dark:divide-slate-800">
            {activeRows.map((row) => {
              const pct = total > 0 ? Math.round((row.balance / total) * 100) : 0;
              return (
                <tr key={row.label}>
                  <td className="py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: row.hex }} />
                      <span className="font-medium text-slate-700 dark:text-slate-300">{row.label}</span>
                    </div>
                  </td>
                  <td className="py-2.5 text-left font-semibold text-slate-800 dark:text-slate-100 tabular-nums" dir="ltr">
                    {fmt(row.balance)}
                  </td>
                  <td className="py-2.5 text-left">
                    <Badge 
                      variant="default"
                      style={{ backgroundColor: row.hex }}
                    >
                      {pct}%
                    </Badge>
                  </td>
                </tr>
              );
            })}
          </tbody>
          {activeRows.length > 1 && (
            <tfoot>
              <tr className="border-t-2 border-slate-200 dark:border-slate-800">
                <td className="pt-2 font-bold text-slate-700 dark:text-slate-300">סה״כ</td>
                <td className="pt-2 text-left font-bold text-slate-900 dark:text-slate-100 tabular-nums" dir="ltr">{fmt(total)}</td>
                <td className="pt-2 text-left">
                  <Badge variant="secondary" className="bg-slate-700 dark:bg-slate-800 text-white">100%</Badge>
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </CardContent>
    </Card>
  );
}
