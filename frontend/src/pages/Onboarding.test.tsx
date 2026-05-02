import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Onboarding from './Onboarding';
import * as AuthContext from '../context/AuthContext';
import * as FirestoreModule from 'firebase/firestore';

// Mock the navigate function
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock Firebase
vi.mock('../lib/firebase', () => ({
  db: {}
}));

// Mock Firestore functions
vi.mock('firebase/firestore', () => ({
  doc: vi.fn(),
  setDoc: vi.fn(),
  serverTimestamp: vi.fn(),
}));

// Mock FinancialProfileStep
vi.mock('../components/onboarding/FinancialProfileStep', () => ({
  default: ({ onComplete, onDataChange }: any) => (
    <div data-testid="financial-profile-step">
      <button onClick={() => onComplete({ test: 'data' })}>Complete Step 2</button>
      <button onClick={() => onDataChange({ test: 'data' })}>Change Data</button>
    </div>
  )
}));

describe('Onboarding Component', () => {
  const mockUser = { uid: 'user123', email: 'test@example.com' };
  const mockRefreshFamily = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock the useAuth hook
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: mockUser as any,
      refreshFamily: mockRefreshFamily,
      signInWithGoogle: vi.fn(),
      signInWithDemo: vi.fn(),

      familyConfig: null,
      loading: false,
      logout: vi.fn(),
      familyId: null,
    });

    // Mock localStorage
    vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {});
    window.scrollTo = vi.fn();
  });

  const renderOnboarding = () => {
    return render(
      <MemoryRouter>
        <Onboarding />
      </MemoryRouter>
    );
  };

  it('renders step 1 correctly', () => {
    renderOnboarding();
    
    expect(screen.getByText('הגדרת המשפחה')).toBeInTheDocument();
    expect(screen.getByText('שלב 1: פרטים בסיסיים והרשאות')).toBeInTheDocument();
    expect(screen.getByLabelText(/שם הבית \/ המשפחה/)).toBeInTheDocument();
  });

  it('handles transitioning to step 2', async () => {
    renderOnboarding();

    // Both member1 and member2 have שם פרטי fields, so use getAllByRole
    const nameInputs = screen.getAllByRole('textbox', { name: /שם פרטי/i });
    
    // Fill first member
    fireEvent.change(nameInputs[0], { target: { value: 'User1' } });
    // Fill second member
    fireEvent.change(nameInputs[1], { target: { value: 'User2' } });

    const nextButton = screen.getByText('המשך לשלב הבא');
    expect(nextButton).not.toBeDisabled();
    
    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(screen.getByTestId('financial-profile-step')).toBeInTheDocument();
    });
    
    expect(screen.getByText('פרופיל פיננסי')).toBeInTheDocument();
  });

  it('completes onboarding and navigates to dashboard', async () => {
    (FirestoreModule.setDoc as any).mockResolvedValue({});

    renderOnboarding();

    // Fill required fields and go to step 2
    const nameInputs = screen.getAllByRole('textbox', { name: /שם פרטי/i });
    fireEvent.change(nameInputs[0], { target: { value: 'User1' } });
    fireEvent.change(nameInputs[1], { target: { value: 'User2' } });
    
    fireEvent.click(screen.getByText('המשך לשלב הבא'));

    await waitFor(() => {
      expect(screen.getByTestId('financial-profile-step')).toBeInTheDocument();
    });

    // Complete step 2
    fireEvent.click(screen.getByText('Complete Step 2'));

    await waitFor(() => {
      expect(FirestoreModule.setDoc).toHaveBeenCalledTimes(2);
      expect(mockRefreshFamily).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });
});
