import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

// Default mock: free build (empty paid surface) + a stored timeout.
vi.mock('@/ee-active.generated', () => ({ paidSurface: {} }));
vi.mock('@/utils/api', () => ({
  api: {
    get: vi.fn(async () => ({ ok: true, data: { decision_timeout_seconds: 7200 } })),
    put: vi.fn(async () => ({ ok: true, data: { decision_timeout_seconds: 3600 } })),
  },
  isOk: (r: { ok?: boolean }) => !!r?.ok,
}));

import { DecisionTimeoutSection } from './DecisionTimeoutSection';

describe('DecisionTimeoutSection', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows the stored value', async () => {
    render(<DecisionTimeoutSection />);
    await waitFor(() => {
      expect(screen.getByText(/Currently 2 hours/)).toBeInTheDocument();
    });
  });

  it('renders read-only on the free tier (no Save button)', async () => {
    render(<DecisionTimeoutSection />);
    await waitFor(() => {
      expect(screen.getByText(/Read-only/)).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument();
    const input = screen.getByLabelText(/Wait for/) as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });
});
