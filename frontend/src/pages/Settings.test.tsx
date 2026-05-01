import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Settings from './Settings';
import * as AuthContext from '../context/AuthContext';
import * as ThemeContext from '../context/ThemeContext';

// Mock navigation and search params
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [new URLSearchParams(), vi.fn()],
  };
});

// Mock services
vi.mock('../lib/familyService', () => ({
  deleteFamily: vi.fn(),
  addAuthorizedEmail: vi.fn(),
}));

// Mock components
vi.mock('../components/dashboard/UploadSection', () => ({
  default: () => <div data-testid="upload-section" />
}));

describe('Settings Component', () => {
  const mockUser = { uid: 'user123', email: 'test@example.com', getIdToken: vi.fn().mockResolvedValue('token') };

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock Auth hook
    vi.spyOn(AuthContext, 'useAuth').mockReturnValue({
      user: mockUser as any,
      familyId: 'family123',
      familyConfig: {
        householdName: 'Test Family',
        member1: { name: 'User 1', email: 'u1@test.com' },
        member2: { name: 'User 2', email: 'u2@test.com' },
        extraAuthorizedEmails: []
      },
      refreshFamily: vi.fn(),
      signInWithGoogle: vi.fn(),
      signInWithDemo: vi.fn(),
      currentUser: mockUser as any,
      loading: false,
      logout: vi.fn(),
      hasCompletedOnboarding: true,
      completeOnboarding: vi.fn(),
    });

    // Mock Theme hook
    vi.spyOn(ThemeContext, 'useTheme').mockReturnValue({
      theme: 'light',
      toggleTheme: vi.fn(),
    });

    // Mock fetch
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({})
    });
  });

  const renderSettings = () => {
    return render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>
    );
  };

  it('renders settings headers correctly', () => {
    renderSettings();
    expect(screen.getByText('הגדרות')).toBeInTheDocument();
    expect(screen.getByText('פרטי המשפחה וקריאת מיילים')).toBeInTheDocument();
    expect(screen.getByText('הגדרות סריקת דוחות ממייל')).toBeInTheDocument();
    expect(screen.getByText('רענן המלצות AI')).toBeInTheDocument();
    expect(screen.getByText('גישה נוספת מורשית')).toBeInTheDocument();
    expect(screen.getByText('ניהול תהליכי רקע (Cron Jobs)')).toBeInTheDocument();
  });

  it('displays family configuration', async () => {
    renderSettings();
    expect(screen.getByText('Test Family')).toBeInTheDocument();
    expect(screen.getByText('User 1')).toBeInTheDocument();
    expect(screen.getByText('User 2')).toBeInTheDocument();
  });

  it('renders Danger Zone', () => {
    renderSettings();
    expect(screen.getByText('אזור מסוכן')).toBeInTheDocument();
    expect(screen.getByText('מחיקת המשפחה')).toBeInTheDocument();
  });
});
