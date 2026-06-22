import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

// Render the real BaseModal chrome behaviour minimally (open => dialog).
vi.mock('./BaseModal', () => ({
    BaseModal: ({ isOpen, children }: any) => (isOpen ? <div role="dialog">{children}</div> : null),
    ModalHeader: ({ children }: any) => <div>{children}</div>,
    ModalFooter: ({ children }: any) => <div>{children}</div>,
}));

// Stub the EE surface so this test focuses on the container, not token I/O.
vi.mock('@/ee-active.generated', () => ({
    paidSurface: { ApiTokensSection: () => <div data-testid="tokens-section">tokens</div> },
}));

vi.mock('lucide-react', () => ({
    KeyRound: () => null,
    Settings: () => null,
}));

import { SettingsModal } from './SettingsModal';

describe('SettingsModal', () => {
    it('renders nothing when closed', () => {
        const { container } = render(<SettingsModal isOpen={false} onClose={() => {}} />);
        expect(container.querySelector('[role="dialog"]')).toBeNull();
    });

    it('shows the section nav and the active section when open', () => {
        render(<SettingsModal isOpen onClose={() => {}} />);
        // Title + nav entry both read "API Tokens"; at least one must be present.
        expect(screen.getAllByText('API Tokens').length).toBeGreaterThan(0);
        // The first section (tokens) renders by default.
        expect(screen.getByTestId('tokens-section')).toBeTruthy();
    });
});
