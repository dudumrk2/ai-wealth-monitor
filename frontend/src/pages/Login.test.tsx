import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Login from './Login';
import * as AuthContext from '../context/AuthContext';
import { STORAGE_KEYS } from '../lib/storageKeys';

// Mock the navigate function
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('Login Component', () => {
  const mockSignInWithGoogle = vi.fn();
  const mockSignInWithDemo = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock the useAuth hook
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      signInWithGoogle: mockSignInWithGoogle,
      signInWithDemo: mockSignInWithDemo,
      user: null,
      familyConfig: null,
      loading: false,
      logout: vi.fn(),
      familyId: null,
      refreshFamily: vi.fn(),
    });
  });

  const renderLogin = () => {
    return render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );
  };

  it('renders login options correctly', () => {
    renderLogin();

    expect(screen.getByText('ניטור עושר משפחתי')).toBeInTheDocument();
    expect(screen.getByText(/כניסה לחשבון משפחה קיים/i)).toBeInTheDocument();
    // This text appears as both a section heading and inside button text
    expect(screen.getAllByText(/יצירת משפחה חדשה/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/צפו בתיק דוגמה חי/i)).toBeInTheDocument();
  });

  it('handles existing family login correctly', async () => {
    mockSignInWithGoogle.mockResolvedValueOnce({});
    renderLogin();

    const signInButton = screen.getByText(/כניסה לחשבון משפחה קיים/i);
    fireEvent.click(signInButton);

    expect(mockSignInWithGoogle).toHaveBeenCalledTimes(1);
    
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });

  it('handles create new family login correctly', async () => {
    mockSignInWithGoogle.mockResolvedValueOnce({});
    
    // Mock localStorage
    const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem');

    renderLogin();

    const createFamilyButton = screen.getByText(/כניסה עם Google ליצירת משפחה חדשה/i);
    fireEvent.click(createFamilyButton);

    expect(removeItemSpy).toHaveBeenCalledWith(STORAGE_KEYS.ONBOARDING_DONE);
    expect(removeItemSpy).toHaveBeenCalledWith(STORAGE_KEYS.FAMILY_CONFIG);
    expect(mockSignInWithGoogle).toHaveBeenCalledTimes(1);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/onboarding');
    });
  });

  it('handles demo sign in correctly', async () => {
    mockSignInWithDemo.mockResolvedValueOnce({});
    renderLogin();

    const demoButton = screen.getByText(/צפו בתיק דוגמה חי/i);
    fireEvent.click(demoButton);

    expect(mockSignInWithDemo).toHaveBeenCalledTimes(1);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });
});
