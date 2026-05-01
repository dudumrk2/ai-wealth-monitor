import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import AltInvestmentsDashboard from './AltInvestmentsDashboard';
import * as AuthContext from '../context/AuthContext';

// Mock Modal Components
vi.mock('../components/dashboard/AddAlternativeModal', () => ({
  default: ({ isOpen, onClose }: any) => (isOpen ? <div data-testid="add-alt-modal"><button onClick={onClose}>Close</button></div> : null)
}));
vi.mock('../components/dashboard/PolicyDetailsModal', () => ({
  default: ({ onClose }: any) => (<div data-testid="policy-details-modal"><button onClick={onClose}>Close</button></div>)
}));
vi.mock('../components/dashboard/ProjectDetailsModal', () => ({
  default: ({ onClose }: any) => (<div data-testid="project-details-modal"><button onClick={onClose}>Close</button></div>)
}));

describe('AltInvestmentsDashboard Component', () => {
  const mockUser = { uid: 'user123', getIdToken: vi.fn().mockResolvedValue('token') };

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock Auth
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: mockUser as any,
      familyConfig: {
        householdName: 'Test Family',
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
    global.fetch = vi.fn((url: string | Request | URL) => {
      const urlStr = url.toString();
      if (urlStr.includes('alternatives/projects')) {
        return Promise.resolve({
          ok: true,
          json: async () => ([
            { id: '1', name: 'Test Project', status: 'Active', originalAmount: 100000, expectedReturn: 10, startDate: '2023-01-01', durationMonths: 24, currency: 'ILS', developer: 'Dev A' },
            { id: '2', name: 'Exited Project', status: 'Exited', originalAmount: 50000, expectedReturn: 8, startDate: '2022-01-01', durationMonths: 12, currency: 'ILS', finalAmount: 55000, actualExitDate: '2023-01-01' }
          ])
        });
      }
      if (urlStr.includes('alternatives/leveraged-policies')) {
        return Promise.resolve({
          ok: true,
          json: async () => ([
            { id: '1', name: 'Test Policy', currentBalance: 200000, balloonLoanAmount: 100000, initialDepositAmount: 150000 }
          ])
        });
      }
      return Promise.reject(new Error('not mocked'));
    }) as any;
  });

  const renderDashboard = () => {
    return render(
      <MemoryRouter>
        <AltInvestmentsDashboard />
      </MemoryRouter>
    );
  };

  it('renders dashboard with active projects and policies', async () => {
    renderDashboard();
    
    expect(screen.getByText('השקעות אלטרנטיביות')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
      expect(screen.queryByText('Exited Project')).not.toBeInTheDocument();
      expect(screen.getByText('Test Policy')).toBeInTheDocument();
    });
  });

  it('toggles exited projects view', async () => {
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });

    const toggle = screen.getByText('הצג הסתיימו');
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(screen.getByText('Exited Project')).toBeInTheDocument();
      // Should also see active projects depending on how the filter works, but we check for exited
    });
  });

  it('opens add asset modal', async () => {
    renderDashboard();
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });

    const addBtn = screen.getByText('הוסף נכס');
    fireEvent.click(addBtn);

    expect(screen.getByTestId('add-alt-modal')).toBeInTheDocument();
  });

  it('opens policy details modal on click', async () => {
    renderDashboard();
    
    await waitFor(() => {
      expect(screen.getByText('Test Policy')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Test Policy'));
    
    expect(screen.getByTestId('policy-details-modal')).toBeInTheDocument();
  });

  it('opens project details modal on click', async () => {
    renderDashboard();
    
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Test Project'));
    
    expect(screen.getByTestId('project-details-modal')).toBeInTheDocument();
  });
});
