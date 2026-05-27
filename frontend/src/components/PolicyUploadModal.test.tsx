import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PolicyUploadModal from './PolicyUploadModal';
import * as AuthContext from '../context/AuthContext';

vi.mock('../context/AuthContext');

const mockAuthReturn = {
  user: null,
  signInWithGoogle: vi.fn(),
  signInWithDemo: vi.fn(),
  familyConfig: null,
  loading: false,
  logout: vi.fn(),
  familyId: null,
  refreshFamily: vi.fn(),
};

beforeEach(() => {
  vi.spyOn(AuthContext, 'useAuth').mockReturnValue(mockAuthReturn as any);
  globalThis.fetch = vi.fn();
});

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  onSuccess: vi.fn(),
  policyId: 'pol-1',
  policyName: 'Test Policy',
  uid: 'user123',
};

describe('PolicyUploadModal', () => {
  it('renders nothing when isOpen is false', () => {
    const { container } = render(<PolicyUploadModal {...defaultProps} isOpen={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders modal content when isOpen is true', () => {
    render(<PolicyUploadModal {...defaultProps} />);
    expect(screen.getByText('Test Policy')).toBeInTheDocument();
    expect(screen.getByText('העלאת פוליסה')).toBeInTheDocument();
  });

  it('calls onClose when the close button is clicked', () => {
    const onClose = vi.fn();
    render(<PolicyUploadModal {...defaultProps} onClose={onClose} />);
    // The close button wraps the X icon — find buttons and click the last one (X button)
    const buttons = screen.getAllByRole('button');
    // The X close button is the first button in the header
    fireEvent.click(buttons[0]);
    expect(onClose).toHaveBeenCalled();
  });

  it('shows error when non-PDF file is selected', () => {
    render(<PolicyUploadModal {...defaultProps} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const nonPdfFile = new File(['content'], 'doc.txt', { type: 'text/plain' });
    fireEvent.change(fileInput, { target: { files: [nonPdfFile] } });
    expect(screen.getByText('אנא בחר קובץ PDF בלבד')).toBeInTheDocument();
  });

  it('shows file name when valid PDF is selected', () => {
    render(<PolicyUploadModal {...defaultProps} />);
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const pdfFile = new File(['%PDF-1.4'], 'policy.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [pdfFile] } });
    expect(screen.getByText('policy.pdf')).toBeInTheDocument();
  });
});
