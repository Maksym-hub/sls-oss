import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ComingSoon } from './ComingSoon';

describe('ComingSoon', () => {
    it('renders the tier-agnostic upcoming-release message for the given feature', () => {
        render(<ComingSoon feature="Asset console" />);
        expect(
            screen.getByText('Asset console is coming in an upcoming release.'),
        ).toBeInTheDocument();
    });

    it('does not mention open-core (copy is reusable in paid builds)', () => {
        render(<ComingSoon feature="Asset console" />);
        expect(screen.queryByText(/open-core/i)).toBeNull();
    });

    it('exposes a status role for assistive tech', () => {
        render(<ComingSoon feature="Asset console" />);
        expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('omits the home button when no onHome handler is provided', () => {
        render(<ComingSoon feature="Asset console" />);
        expect(screen.queryByRole('button')).toBeNull();
    });

    it('renders and fires the home button when onHome is provided', () => {
        const onHome = vi.fn();
        render(<ComingSoon feature="Asset console" onHome={onHome} />);
        fireEvent.click(screen.getByText('Go to Pipelines'));
        expect(onHome).toHaveBeenCalledTimes(1);
    });
});
