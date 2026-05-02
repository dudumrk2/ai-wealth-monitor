import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import StocksDashboard from './StocksDashboard';
import * as AuthContext from '../context/AuthContext';

// Mock Recharts
vi.mock('recharts', async () => {
  const OriginalRecharts = await vi.importActual('recharts');
  return {
    ...OriginalRecharts,
    ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  };
});

// Mock Components
vi.mock('../components/dashboard/AdvisorChat', () => ({
  AdvisorChat: () => <div data-testid="advisor-chat" />
}));

vi.mock('../components/stocks/ManualStockModal', () => ({
  default: ({ isOpen, onClose }: any) => (isOpen ? <div data-testid="manual-stock-modal"><button onClick={onClose}>Close</button></div> : null)
}));

describe('StocksDashboard Component', () => {
  const mockUser = { uid: 'user123', getIdToken: vi.fn().mockResolvedValue('token') };

  beforeEach(() => {
    vi.clearAllMocks();
    
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: mockUser as any,
      familyConfig: {},
      signInWithGoogle: vi.fn(),
      signInWithDemo: vi.fn(),
      currentUser: mockUser as any,
      loading: false,
      logout: vi.fn(),
      hasCompletedOnboarding: true,
      completeOnboarding: vi.fn(),
      refreshFamily: vi.fn(),
    } as any);

    // Mock fetch for portfolio and fx-rate
    globalThis.fetch = vi.fn((url: string | Request | URL) => {
      const urlStr = url.toString();
      if (urlStr.includes('fx-rate')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ rate: 3.5, date: '2023-10-01', cached: false })
        });
      }
      if (urlStr.includes('portfolio')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              stocks: [
                { id: '1', symbol: 'AAPL', name: 'Apple', sector: 'technology', currency: 'USD', qty: 10, totalValueOriginal: 1500, dailyPnlOriginal: 10, totalPnlOriginal: 200, dailyChangePercent: 0.5, totalReturnPercent: 15 },
                { id: '2', symbol: 'MSFT', name: 'Microsoft', sector: 'technology', currency: 'USD', qty: 5, totalValueOriginal: 1500, dailyPnlOriginal: -5, totalPnlOriginal: 100, dailyChangePercent: -0.2, totalReturnPercent: 10 }
              ]
            }
          })
        });
      }
      return Promise.reject(new Error('not mocked'));
    }) as any;
  });

  const renderDashboard = () => {
    return render(
      <MemoryRouter>
        <StocksDashboard />
      </MemoryRouter>
    );
  };

  it('renders dashboard with stocks and fx rate', async () => {
    renderDashboard();

    expect(screen.getByText('תיק מניות')).toBeInTheDocument();

    await waitFor(() => {
      // Apple and Microsoft appear in both desktop table and mobile cards
      expect(screen.getAllByText('Apple').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Microsoft').length).toBeGreaterThan(0);
    });

    expect(screen.getByText(/שער המרה: 1\$/)).toBeInTheDocument();
  });

  it('opens manual stock modal', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getAllByText('Apple').length).toBeGreaterThan(0);
    });

    const addBtn = screen.getByText('הוספת נייר');
    fireEvent.click(addBtn);

    expect(screen.getByTestId('manual-stock-modal')).toBeInTheDocument();
  });

  it('can sort the table', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getAllByText('Apple').length).toBeGreaterThan(0);
    });

    // Table rows: header + 2 data rows visible in desktop table
    const tableRows = screen.getAllByRole('row');
    expect(tableRows.length).toBeGreaterThan(2);
    
    // Sort by name
    const sortBtn = screen.getByText('שם / סימבול');
    fireEvent.click(sortBtn); // ascending
    fireEvent.click(sortBtn); // descending
    // Just making sure it doesn't crash on sorting
  });
});
