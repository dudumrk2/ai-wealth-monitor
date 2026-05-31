import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ThemeProvider, useTheme } from './ThemeContext';

function Consumer() {
  const { theme, toggleTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <button onClick={toggleTheme}>toggle</button>
    </div>
  );
}

// jsdom does not implement matchMedia — install a controllable stub.
function setPrefersDark(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.className = '';
  setPrefersDark(false);
});

describe('ThemeContext', () => {
  it('defaults to light when no saved theme and system prefers light', () => {
    setPrefersDark(false);
    render(<ThemeProvider><Consumer /></ThemeProvider>);
    expect(screen.getByTestId('theme').textContent).toBe('light');
  });

  it('defaults to dark when system prefers dark', () => {
    setPrefersDark(true);
    render(<ThemeProvider><Consumer /></ThemeProvider>);
    expect(screen.getByTestId('theme').textContent).toBe('dark');
  });

  it('reads a previously saved theme from localStorage', () => {
    localStorage.setItem('theme', 'dark');
    render(<ThemeProvider><Consumer /></ThemeProvider>);
    expect(screen.getByTestId('theme').textContent).toBe('dark');
  });

  it('toggles the theme and persists the choice', () => {
    render(<ThemeProvider><Consumer /></ThemeProvider>);
    expect(screen.getByTestId('theme').textContent).toBe('light');
    fireEvent.click(screen.getByText('toggle'));
    expect(screen.getByTestId('theme').textContent).toBe('dark');
    expect(localStorage.getItem('theme')).toBe('dark');
  });

  it('applies the active theme class to the document root', () => {
    localStorage.setItem('theme', 'dark');
    render(<ThemeProvider><Consumer /></ThemeProvider>);
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.classList.contains('light')).toBe(false);
  });

  it('throws a helpful error when useTheme is used outside a provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Consumer />)).toThrow('useTheme must be used within a ThemeProvider');
    spy.mockRestore();
  });
});
