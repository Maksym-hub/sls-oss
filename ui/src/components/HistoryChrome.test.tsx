import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

const { mockPush } = vi.hoisted(() => ({ mockPush: vi.fn() }));

vi.mock('@/hooks/useClientRoute', () => ({
    useClientRoute: () => ({ pathname: '/runs/', push: mockPush, replace: vi.fn() }),
}));
vi.mock('@/components/ui/button', () => ({
    Button: (props: Record<string, unknown>) => (
        <button onClick={props.onClick as () => void}>{props.children as React.ReactNode}</button>
    ),
}));
vi.mock('../utils/icons', () => ({
    Activity: () => <span data-testid="icon-activity" />,
    ListTodo: () => <span data-testid="icon-listtodo" />,
    RefreshCw: () => <span data-testid="icon-refresh" />,
    Search: () => <span data-testid="icon-search" />,
    ChevronLeft: () => <span data-testid="icon-left" />,
    ChevronRight: () => <span data-testid="icon-right" />,
}));

import { HistoryChrome } from './HistoryChrome';

const baseProps = {
    mode: 'runs' as const,
    search: '',
    onSearch: vi.fn(),
    page: 0,
    setPage: vi.fn(),
    total: 25,
    pageCount: 3,
    pageSize: 10,
    onRefresh: vi.fn(),
    children: <div data-testid="table" />,
};

describe('HistoryChrome', () => {
    beforeEach(() => {
        mockPush.mockClear();
        baseProps.onSearch = vi.fn();
        baseProps.setPage = vi.fn();
        baseProps.onRefresh = vi.fn();
    });

    it('renders the History title and both toggle tabs', () => {
        render(<HistoryChrome {...baseProps} />);
        expect(screen.getByText('History')).toBeInTheDocument();
        expect(screen.getByRole('tab', { name: /runs/i })).toBeInTheDocument();
        expect(screen.getByRole('tab', { name: /tasks/i })).toBeInTheDocument();
    });

    it('marks the active tab from mode and pushes the other route on click', () => {
        render(<HistoryChrome {...baseProps} mode="runs" />);
        const runsTab = screen.getByRole('tab', { name: /runs/i });
        const tasksTab = screen.getByRole('tab', { name: /tasks/i });
        expect(runsTab).toHaveAttribute('aria-selected', 'true');
        expect(tasksTab).toHaveAttribute('aria-selected', 'false');
        fireEvent.click(tasksTab);
        expect(mockPush).toHaveBeenCalledWith('/tasks/');
    });

    it('does not navigate when clicking the already-active tab', () => {
        render(<HistoryChrome {...baseProps} mode="runs" />);
        fireEvent.click(screen.getByRole('tab', { name: /runs/i }));
        expect(mockPush).not.toHaveBeenCalled();
    });

    it('calls onSearch as the user types', () => {
        const onSearch = vi.fn();
        render(<HistoryChrome {...baseProps} onSearch={onSearch} />);
        fireEvent.change(screen.getByLabelText('Search runs'), { target: { value: 'etl' } });
        expect(onSearch).toHaveBeenCalledWith('etl');
    });

    it('shows the current window and total, and pages forward/back', () => {
        const setPage = vi.fn();
        render(<HistoryChrome {...baseProps} page={1} setPage={setPage} />);
        expect(screen.getByText('11–20 of 25')).toBeInTheDocument();
        fireEvent.click(screen.getByLabelText('Next page'));
        expect(setPage).toHaveBeenCalledWith(2);
        fireEvent.click(screen.getByLabelText('Previous page'));
        expect(setPage).toHaveBeenCalledWith(0);
    });

    it('disables Previous on the first page and Next on the last', () => {
        const { rerender } = render(<HistoryChrome {...baseProps} page={0} />);
        expect(screen.getByLabelText('Previous page')).toBeDisabled();
        expect(screen.getByLabelText('Next page')).not.toBeDisabled();
        rerender(<HistoryChrome {...baseProps} page={2} />);
        expect(screen.getByLabelText('Next page')).toBeDisabled();
    });

    it('hides the pagination footer entirely when empty', () => {
        render(<HistoryChrome {...baseProps} total={0} pageCount={1} />);
        expect(screen.queryByText(/of 0/)).not.toBeInTheDocument();
        expect(screen.queryByLabelText('Next page')).not.toBeInTheDocument();
    });

    it('shows the count but no pager when everything fits one page', () => {
        render(<HistoryChrome {...baseProps} total={5} pageCount={1} />);
        expect(screen.getByText('5 runs')).toBeInTheDocument();
        expect(screen.queryByLabelText('Next page')).not.toBeInTheDocument();
    });

    it('uses a roving tabindex on the toggle (only the active tab is focusable)', () => {
        render(<HistoryChrome {...baseProps} mode="runs" />);
        expect(screen.getByRole('tab', { name: /runs/i })).toHaveAttribute('tabindex', '0');
        expect(screen.getByRole('tab', { name: /tasks/i })).toHaveAttribute('tabindex', '-1');
    });
});
