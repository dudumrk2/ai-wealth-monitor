import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import DashboardPage from './DashboardPage';
import * as AuthContext from '../context/AuthContext';

// Mock Recharts to avoid ResizeObserver and actual rendering issues in JSDOM
vi.mock('recharts', async () => {
  const OriginalRecharts = await vi.importActual('recharts');
  return {
    ...OriginalRecharts,
    ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  };
});

// Mock CopilotChat
vi.mock('../components/CopilotChat', () => ({
  CopilotChat: () => <div data-testid="copilot-chat" />
}));

describe('DashboardPage', () => {
  const mockUser = {
    getIdToken: vi.fn().mockResolvedValue('mock-token'),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Clear portfolio cache so stale-while-revalidate doesn't suppress error states in tests
    sessionStorage.clear();
    
    // Mock the useAuth hook
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: mockUser as any,
      signInWithGoogle: vi.fn(),
      signInWithDemo: vi.fn(),

      familyConfig: null,
      loading: false,
      logout: vi.fn(),
      familyId: null,
      refreshFamily: vi.fn(),
    });

    // Mock fetch
    globalThis.fetch = vi.fn();
  });

  const renderDashboard = () => {
    return render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );
  };

  it('shows loading state initially', () => {
    // Keep fetch pending
    (globalThis.fetch as any).mockImplementation(() => new Promise(() => {}));
    
    renderDashboard();
    expect(screen.getByText('טוען נתונים פיננסיים...')).toBeInTheDocument();
  });

  it('renders dashboard with portfolio data', async () => {
    const mockPortfolioData = {
      portfolios: {
        user: { funds: [{ balance: 10000, category: 'pension' }], alternative_investments: [] },
        spouse: { funds: [], alternative_investments: [] },
        joint: { stock_investments: [], total_family_wealth: 10000 }
      },
      stock_portfolio_summary: { total_value: 0, daily_return: 0 },
      action_items: []
    };

    (globalThis.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockPortfolioData
    });

    renderDashboard();

    await waitFor(() => {
      expect(screen.queryByText('טוען נתונים פיננסיים...')).not.toBeInTheDocument();
    });

    expect(screen.getByText('דשבורד משפחתי')).toBeInTheDocument();
    expect(screen.getByText('יתרת פנסיה')).toBeInTheDocument();
    expect(screen.getAllByText(/10,000/).length).toBeGreaterThan(0);
    expect(screen.getByTestId('copilot-chat')).toBeInTheDocument();
  });

  it('renders error state when fetch fails', async () => {
    (globalThis.fetch as any).mockResolvedValueOnce({
      ok: false,
    });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('אופס, משהו השתבש')).toBeInTheDocument();
    });
    
    expect(screen.getByText('אירעה שגיאה בטעינת הנתונים.')).toBeInTheDocument();
  });
});
