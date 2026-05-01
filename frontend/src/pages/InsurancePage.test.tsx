import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import InsurancePage from './InsurancePage';
import * as AuthContext from '../context/AuthContext';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('../components/PolicyUploadModal', () => ({
  default: ({ isOpen, onClose }: any) => (
    isOpen ? <div data-testid="policy-upload-modal"><button onClick={onClose}>Close Modal</button></div> : null
  )
}));

describe('InsurancePage Component', () => {
  const mockUser = { uid: 'user123', getIdToken: vi.fn().mockResolvedValue('token') };

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock Auth
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
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        portfolios: {
          user: {
            funds: [
              { id: '1', category: 'insurance', track_name: 'ביטוח רכב חובה', provider_name: 'הראל', monthly_deposit: 100 },
              { id: '2', category: 'insurance', track_name: 'ביטוח בריאות', provider_name: 'מגדל', monthly_deposit: 200 },
            ]
          }
        },
        action_items: []
      })
    });
  });

  const renderInsurancePage = () => {
    return render(
      <MemoryRouter>
        <InsurancePage />
      </MemoryRouter>
    );
  };

  it('renders insurance overview correctly', async () => {
    renderInsurancePage();
    
    expect(screen.getByText('ביטוחים')).toBeInTheDocument();
    
    await waitFor(() => {
      // Because default tab is רכב, we should see רכב fund but not בריאות fund
      expect(screen.getByText('ביטוח רכב חובה')).toBeInTheDocument();
      expect(screen.queryByText('ביטוח בריאות')).not.toBeInTheDocument();
    });
  });

  it('filters funds by tab', async () => {
    renderInsurancePage();
    
    await waitFor(() => {
      expect(screen.getByText('ביטוח רכב חובה')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('חיים ובריאות'));

    await waitFor(() => {
      expect(screen.queryByText('ביטוח רכב חובה')).not.toBeInTheDocument();
      expect(screen.getByText('ביטוח בריאות')).toBeInTheDocument();
    });
  });

  it('navigates to settings for generic upload', () => {
    renderInsurancePage();
    const uploadBtn = screen.getByText('העלאת מסמך / הר ביטוח');
    fireEvent.click(uploadBtn);
    expect(mockNavigate).toHaveBeenCalledWith('/settings');
  });

  it('opens PolicyUploadModal when clicking specific policy upload', async () => {
    renderInsurancePage();
    
    await waitFor(() => {
      expect(screen.getByText('ביטוח רכב חובה')).toBeInTheDocument();
    });

    const uploadBtn = screen.getByText('העלאת פוליסה');
    fireEvent.click(uploadBtn);

    expect(screen.getByTestId('policy-upload-modal')).toBeInTheDocument();
  });
});
