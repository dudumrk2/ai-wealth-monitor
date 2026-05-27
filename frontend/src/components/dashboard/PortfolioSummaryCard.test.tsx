import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PortfolioSummaryCard, { type SummaryRow } from './PortfolioSummaryCard';

// Mirror the recharts mock used in page tests
vi.mock('recharts', async () => {
  const Orig = await vi.importActual('recharts');
  return { ...Orig, ResponsiveContainer: ({ children }: any) => <div>{children}</div> };
});

const rows: SummaryRow[] = [
  { label: 'פנסיה', balance: 500000, color: 'blue-600', hex: '#2563eb' },
  { label: 'קרן השתלמות', balance: 200000, color: 'emerald-500', hex: '#10b981' },
];

describe('PortfolioSummaryCard', () => {
  it('renders the card title', () => {
    render(<PortfolioSummaryCard title="סיכום חיסכון" rows={rows} />);
    expect(screen.getByText('סיכום חיסכון')).toBeInTheDocument();
  });

  it('renders each row label', () => {
    render(<PortfolioSummaryCard title="X" rows={rows} />);
    expect(screen.getByText('פנסיה')).toBeInTheDocument();
    expect(screen.getByText('קרן השתלמות')).toBeInTheDocument();
  });

  it('displays the summed total', () => {
    render(<PortfolioSummaryCard title="X" rows={rows} />);
    // Total = 700,000 — appears at least once in the formatted output
    expect(screen.getAllByText(/700,000/).length).toBeGreaterThan(0);
  });

  it('renders percentage badge for each row', () => {
    render(<PortfolioSummaryCard title="X" rows={rows} />);
    // 500000/700000 ≈ 71%,  200000/700000 ≈ 29%
    expect(screen.getByText('71%')).toBeInTheDocument();
    expect(screen.getByText('29%')).toBeInTheDocument();
  });

  it('shows סה״כ total row when multiple rows', () => {
    render(<PortfolioSummaryCard title="X" rows={rows} />);
    expect(screen.getByText('סה״כ')).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('hides סה״כ row when only one row', () => {
    render(<PortfolioSummaryCard title="X" rows={[rows[0]]} />);
    expect(screen.queryByText('סה״כ')).not.toBeInTheDocument();
  });

  it('renders totalLabel when provided', () => {
    render(<PortfolioSummaryCard title="X" totalLabel="נכון ל-2024" rows={rows} />);
    expect(screen.getByText('נכון ל-2024')).toBeInTheDocument();
  });
});
