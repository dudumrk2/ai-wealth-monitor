import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ActionItems from './ActionItems';
import type { ActionItem } from '../../types/portfolio';

const makeItem = (overrides: Partial<ActionItem> = {}): ActionItem => ({
  id: 'item-1',
  type: 'general',
  title: 'Test Action',
  description: 'Do this thing',
  severity: 'high',
  is_completed: false,
  owner: 'shared',
  ...overrides,
});

describe('ActionItems', () => {
  it('renders the default section title', () => {
    render(<ActionItems items={[]} />);
    expect(screen.getByText('פעולות נדרשות לשיפור התיק')).toBeInTheDocument();
  });

  it('uses custom title when provided', () => {
    render(<ActionItems items={[]} title="Custom Title" />);
    expect(screen.getByText('Custom Title')).toBeInTheDocument();
  });

  it('renders item title', () => {
    render(<ActionItems items={[makeItem({ title: 'Buy bonds' })]} />);
    // Desktop view always renders items — may appear more than once (desktop+mobile)
    expect(screen.getAllByText('Buy bonds').length).toBeGreaterThan(0);
  });

  it('renders items for all owner types', () => {
    const items = [
      makeItem({ id: '1', title: 'User Item', owner: 'user' }),
      makeItem({ id: '2', title: 'Spouse Item', owner: 'spouse' }),
      makeItem({ id: '3', title: 'Shared Item', owner: 'shared' }),
    ];
    render(<ActionItems items={items} member1Name="Alice" member2Name="Bob" />);
    // Desktop view renders all sections unconditionally
    expect(screen.getAllByText('User Item').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Spouse Item').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Shared Item').length).toBeGreaterThan(0);
  });

  it('shows empty state message when no items', () => {
    render(<ActionItems items={[]} />);
    expect(screen.getByText('הכל מעודכן! אין פעולות ממתינות.')).toBeInTheDocument();
  });

  it('renders member names as tab headers', () => {
    const items = [
      makeItem({ id: '1', title: 'X', owner: 'user' }),
      makeItem({ id: '2', title: 'Y', owner: 'spouse' }),
    ];
    render(<ActionItems items={items} member1Name="Alice" member2Name="Bob" />);
    expect(screen.getAllByText('Alice').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Bob').length).toBeGreaterThan(0);
  });
});
