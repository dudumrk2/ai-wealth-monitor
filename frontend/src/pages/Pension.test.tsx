import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Pension from './Pension';
import * as AuthContext from '../context/AuthContext';

// Mock Recharts
vi.mock('recharts', async () => {
  const OriginalRecharts = await vi.importActual('recharts');
  return {
    ...OriginalRecharts,
    ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  };
});

describe('Pension Component', () => {
  const mockUser = {
    getIdToken: vi.fn().mockResolvedValue('mock-token'),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    
    // Mock the useAuth hook
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: mockUser as any,
      familyConfig: {
        householdName: 'Test Family',
        member1: { name: 'User1' },
        member2: { name: 'User2' }
      },
      signInWithGoogle: vi.fn(),
      signInWithDemo: vi.fn(),
      currentUser: mockUser as any,
      loading: false,
      logout: vi.fn(),
      hasCompletedOnboarding: true,
      completeOnboarding: vi.fn(),
      refreshFamily: vi.fn(),
    } as any);

    // Mock fetch
    globalThis.fetch = vi.fn();
  });

  const renderPension = () => {
    return render(
      <MemoryRouter>
        <Pension />
      </MemoryRouter>
    );
  };

  it('shows loading state initially', () => {
    // Keep fetch pending
    (globalThis.fetch as any).mockImplementation(() => new Promise(() => {}));
    
    renderPension();
    expect(screen.getByText('טוען ננתונים פיננסיים...')).toBeInTheDocument();
  });

  it('renders pension dashboard with data', async () => {
    const mockPortfolioData = {
      portfolios: {
        user: { funds: [{ balance: 10000, category: 'pension', monthly_deposit: 1000 }], alternative_investments: [] },
        spouse: { funds: [], alternative_investments: [] },
        joint: { 
          stock_investments: [], 
          total_family_wealth: 10000,
          asset_allocation_percentages: { stocks: 50, bonds: 50, cash_equivalents: 0 },
          provider_exposure: { "Provider A": 100 }
        }
      },
      action_items: []
    };

    // First call is to check inbox, second is portfolio data.
    // However, they run asynchronously.
    (globalThis.fetch as any).mockImplementation((url: string) => {
      if (url.includes('process-inbox')) {
        return Promise.resolve({ ok: true, json: async () => ({ results: [] }) });
      }
      if (url.includes('portfolio')) {
        return Promise.resolve({ ok: true, json: async () => mockPortfolioData });
      }
      return Promise.reject(new Error('not mocked'));
    });

    renderPension();

    await waitFor(() => {
      expect(screen.queryByText('טוען ננתונים פיננסיים...')).not.toBeInTheDocument();
    });

    expect(screen.getByText('סקירת תיק פנסיוני')).toBeInTheDocument();
    expect(screen.getByText('תצוגה משותפת')).toBeInTheDocument();
    expect(screen.getAllByText('User1').length).toBeGreaterThan(0);
    expect(screen.getAllByText('User2').length).toBeGreaterThan(0);
  });

  it('renders error state when fetch fails', async () => {
    (globalThis.fetch as any).mockImplementation((url: string) => {
      if (url.includes('portfolio')) {
        return Promise.resolve({ ok: false });
      }
      return Promise.resolve({ ok: true, json: async () => ({ results: [] }) });
    });

    renderPension();

    await waitFor(() => {
      expect(screen.getByText('אופס, משהו השתבש')).toBeInTheDocument();
    });
    
    expect(screen.getByText('אירעה שגיאה בטעינת הנתונים.')).toBeInTheDocument();
  });

  it('displays and updates last updated date per tab', async () => {
    const mockPortfolioData = {
      last_updated: '2026-01-01T00:00:00Z',
      portfolios: {
        user: { 
          last_updated: '2026-02-10T08:30:00Z',
          funds: [{ balance: 10000, category: 'pension', monthly_deposit: 1000 }], 
          alternative_investments: [] 
        },
        spouse: { 
          last_updated: '2026-03-20T12:00:00Z',
          funds: [{ balance: 20000, category: 'study', monthly_deposit: 500 }], 
          alternative_investments: [] 
        },
        joint: { 
          stock_investments: [], 
          total_family_wealth: 30000,
          asset_allocation_percentages: { stocks: 50, bonds: 50, cash_equivalents: 0 },
          provider_exposure: { "Provider A": 100 }
        }
      },
      action_items: []
    };

    (globalThis.fetch as any).mockImplementation((url: string) => {
      if (url.includes('process-inbox')) {
        return Promise.resolve({ ok: true, json: async () => ({ results: [] }) });
      }
      if (url.includes('portfolio')) {
        return Promise.resolve({ ok: true, json: async () => mockPortfolioData });
      }
      return Promise.reject(new Error('not mocked'));
    });

    renderPension();

    await waitFor(() => {
      expect(screen.queryByText('טוען ננתונים פיננסיים...')).not.toBeInTheDocument();
    });

    // In joint view initially, the latest date between user (Feb 10) and spouse (Mar 20) should be shown: 20/03/2026
    expect(screen.getByText('עדכון אחרון:')).toBeInTheDocument();
    expect(screen.getByText('20/03/2026')).toBeInTheDocument();

    // Switch to User1 tab
    const userTabButton = screen.getByRole('button', { name: 'User1' });
    fireEvent.click(userTabButton);

    // In User1 tab, date should be 10/02/2026
    expect(screen.getByText('10/02/2026')).toBeInTheDocument();

    // Switch to User2 tab
    const spouseTabButton = screen.getByRole('button', { name: 'User2' });
    fireEvent.click(spouseTabButton);

    // In User2 tab, date should be 20/03/2026
    expect(screen.getByText('20/03/2026')).toBeInTheDocument();
  });
});
