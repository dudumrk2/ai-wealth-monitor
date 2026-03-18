/**
 * PortfolioSummaryCard
 * Shows either total accumulated balance or total monthly deposits
 * with a donut chart and a category breakdown table.
 */

const fmt = (val: number) =>
  new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 }).format(val);

export interface SummaryRow {
  label: string;
  balance: number;
  color: string; // tailwind (unused visually, kept for API compat)
  hex: string;   // hex color for SVG and badge
}

interface Props {
  title: string;
  /** Main number label, e.g. "סר החשבון" or "סה"כ הפקדות חודשיות" */
  totalLabel?: string;
  rows: SummaryRow[];
  /** When true renders a dashed-ring style donut (for monthly view) */
  variant?: 'balance' | 'monthly';
}

// ─── SVG Donut Chart ─────────────────────────────────────────────────────────

function DonutChart({ rows, variant = 'balance' }: { rows: SummaryRow[]; variant?: 'balance' | 'monthly' }) {
  const size = 120;
  const cx = size / 2;
  const cy = size / 2;
  const R = 47;
  const r = 30;

  const total = rows.reduce((s, row) => s + row.balance, 0);
  if (total === 0) return null;

  let startAngle = -Math.PI / 2;

  const segments = rows
    .filter(row => row.balance > 0)
    .map(row => {
      const fraction = row.balance / total;
      const sweep = fraction * 2 * Math.PI;
      const endAngle = startAngle + sweep;
      const largeArc = sweep > Math.PI ? 1 : 0;

      const x1  = cx + R * Math.cos(startAngle);
      const y1  = cy + R * Math.sin(startAngle);
      const x2  = cx + R * Math.cos(endAngle);
      const y2  = cy + R * Math.sin(endAngle);
      const xi1 = cx + r * Math.cos(endAngle);
      const yi1 = cy + r * Math.sin(endAngle);
      const xi2 = cx + r * Math.cos(startAngle);
      const yi2 = cy + r * Math.sin(startAngle);

      const d = [
        `M ${x1} ${y1}`,
        `A ${R} ${R} 0 ${largeArc} 1 ${x2} ${y2}`,
        `L ${xi1} ${yi1}`,
        `A ${r} ${r} 0 ${largeArc} 0 ${xi2} ${yi2}`,
        'Z',
      ].join(' ');

      startAngle = endAngle;
      return { d, hex: row.hex };
    });

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
      {/* Background ring for monthly variant */}
      {variant === 'monthly' && (
        <circle cx={cx} cy={cy} r={(R + r) / 2} fill="none" stroke="#e2e8f0"
          strokeWidth={R - r + 2} strokeDasharray="4 2" opacity={0.5} />
      )}
      {segments.map((seg, i) => (
        <path key={i} d={seg.d} fill={seg.hex} stroke="white" strokeWidth="1.5" />
      ))}
      {/* Center label */}
      <text x={cx} y={cy + 4} textAnchor="middle" fontSize="10"
        fontWeight="700" fill="#1e293b" fontFamily="system-ui">
        {variant === 'monthly' ? '₪/חו' : '%'}
      </text>
    </svg>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function PortfolioSummaryCard({ title, totalLabel, rows, variant = 'balance' }: Props) {
  const total = rows.reduce((s, r) => s + r.balance, 0);
  const activeRows = rows.filter(r => r.balance > 0);

  const isMonthly = variant === 'monthly';

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-6 flex items-center justify-between gap-4 border-b border-slate-100">
        <div>
          <p className="text-sm font-semibold text-slate-500 mb-0.5">{title}</p>
          {totalLabel && <p className="text-xs text-slate-400 mb-1">{totalLabel}</p>}
          <p className="text-3xl font-bold text-slate-900 tabular-nums" dir="ltr">{fmt(total)}</p>
        </div>
        <DonutChart rows={activeRows} variant={variant} />
      </div>

      {/* Table */}
      <div className="p-4">
        <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
          {isMonthly ? 'התפלגות ההפקדה החודשית לפי סוג מוצר' : 'התפלגות החשבון לפי סוג מוצר'}
        </p>
        <table className="w-full text-right text-sm border-collapse">
          <thead>
            <tr className="text-xs text-slate-400 font-semibold">
              <th className="pb-2 font-semibold">סוג מוצר</th>
              <th className="pb-2 text-left font-semibold">{isMonthly ? 'הפקדה' : 'צבירה'}</th>
              <th className="pb-2 text-left font-semibold w-16">חלק יחסי</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {activeRows.map((row) => {
              const pct = total > 0 ? Math.round((row.balance / total) * 100) : 0;
              return (
                <tr key={row.label}>
                  <td className="py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: row.hex }} />
                      <span className="font-medium text-slate-700">{row.label}</span>
                    </div>
                  </td>
                  <td className="py-2.5 text-left font-semibold text-slate-800 tabular-nums" dir="ltr">
                    {fmt(row.balance)}
                  </td>
                  <td className="py-2.5 text-left">
                    <span className="inline-block text-xs font-bold px-2 py-0.5 rounded-full text-white"
                      style={{ backgroundColor: row.hex }}>
                      {pct}%
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
          {activeRows.length > 1 && (
            <tfoot>
              <tr className="border-t-2 border-slate-200">
                <td className="pt-2 font-bold text-slate-700">סה״כ</td>
                <td className="pt-2 text-left font-bold text-slate-900 tabular-nums" dir="ltr">{fmt(total)}</td>
                <td className="pt-2 text-left">
                  <span className="inline-block text-xs font-bold px-2 py-0.5 rounded-full bg-slate-700 text-white">100%</span>
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
