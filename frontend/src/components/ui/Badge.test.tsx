import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Badge } from './Badge';

describe('Badge', () => {
  it('renders children text', () => {
    render(<Badge>Hello</Badge>);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('applies default (blue) variant classes', () => {
    const { container } = render(<Badge>Default</Badge>);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain('bg-blue-600');
  });

  it('applies destructive (red) variant classes', () => {
    const { container } = render(<Badge variant="destructive">Error</Badge>);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain('bg-red-500');
  });

  it('applies success (emerald) variant classes', () => {
    const { container } = render(<Badge variant="success">OK</Badge>);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain('bg-emerald-500');
  });

  it('applies outline variant classes', () => {
    const { container } = render(<Badge variant="outline">Outline</Badge>);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain('border');
  });

  it('applies secondary variant classes', () => {
    const { container } = render(<Badge variant="secondary">Secondary</Badge>);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain('bg-slate-100');
  });

  it('merges custom className', () => {
    const { container } = render(<Badge className="my-custom-class">X</Badge>);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain('my-custom-class');
  });
});
