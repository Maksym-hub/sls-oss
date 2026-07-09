import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { useAppStore } from '../stores/useAppStore';
import { createPipeline, createTask, createDAG, createExecution } from '../test/factories';
import type { PipelineWithUI, DAG } from '../types';

// ─── Query mocks ─────────────────────────────────────────────────────────────
const mockTasks = [
    createTask({ task_name: 'init_config', status: 'success' }),
    createTask({ task_name: 'extract_data', status: 'success' }),
    createTask({ task_name: 'transform', status: 'running' }),
    createTask({ task_name: 'load_db', status: 'waiting' }),
];
const mockDag = createDAG();
const mockExecList = [createExecution()];

const mockDetailQuery = { data: { tasks: mockTasks, dag: mockDag, serverOffsetMs: 0, selectedExecution: null }, isLoading: false };
const mockExecQuery = { data: mockExecList };
const mockPipelinesQuery = { data: [createPipeline()] };
const mockTaskEventsQuery = { data: [], isLoading: false };

vi.mock('../hooks/queries', () => ({
    usePipelineDetailQuery: () => mockDetailQuery,
    usePipelineExecutionsQuery: () => mockExecQuery,
    usePipelinesQuery: () => mockPipelinesQuery,
    useTaskEventsQuery: () => mockTaskEventsQuery,
}));

const mockActions = {
    modal: { isOpen: false, action: null, title: '', message: '', icon: '', confirmText: '', confirmStyle: '', customContent: false, toRun: null, toSkip: null },
    triggerParams: '{}', setTriggerParams: vi.fn(),
    actionPending: false,
    handleRun: vi.fn(), handleStop: vi.fn(), handlePauseResume: vi.fn(),
    handleExtendPause: vi.fn(), handleRefresh: vi.fn(), handleTaskAction: vi.fn(), handleRunAction: vi.fn(),
    executeModalAction: vi.fn(), closeModal: vi.fn(),
};
vi.mock('../hooks', async () => {
    const actual = await vi.importActual<typeof import('../hooks')>('../hooks');
    return {
        ...actual,
        usePipelineActions: () => mockActions,
        useToast: () => ({ show: vi.fn() }),
        // Use the real useKeyboardShortcuts + SHORTCUTS so keydown events
        // dispatch correctly in tests (v0.78.3, ADR #64).
    };
});

vi.mock('@tanstack/react-query', async () => {
    const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query');
    return { ...actual, useQueryClient: () => ({ invalidateQueries: vi.fn() }) };
});

// ─── Component mocks ─────────────────────────────────────────────────────────
vi.mock('./index', () => ({
    DAGGraph: ({ tasks, onSelectTask }: { tasks: { task_name: string }[]; onSelectTask?: (t: unknown) => void }) => (
        <div data-testid="dag-graph">
            {tasks?.map(t => (
                <div key={t.task_name} data-testid={`dag-node-${t.task_name}`} onClick={() => onSelectTask?.(t)}>
                    {t.task_name}
                </div>
            ))}
        </div>
    ),
    DAGSkeleton: () => <div data-testid="dag-skeleton">Loading...</div>,
    GanttSkeleton: () => <div data-testid="gantt-skeleton">Loading...</div>,
    ErrorBoundary: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    ActionModal: () => null,
    BackfillModal: () => null,
    TaskDetailModal: () => null,
}));

// Team view-modes still arrive via the EE surface (ADR #99), not the barrel.
vi.mock('@/ee-active.generated', () => ({
    paidSurface: {
        CalendarView: () => <div data-testid="calendar-view">Calendar</div>,
        GanttChart: () => <div data-testid="gantt-chart">Gantt</div>,
    },
}));

// Pipeline actions provider is free (ADR #110) — stub it so the host renders with
// injected mock handlers; the real hook/modal have their own co-located tests.
vi.mock('@/components/PipelineActionsProvider', () => ({
    PipelineActionsProvider: ({ children }: { params: unknown; children: (a: typeof mockActions) => React.ReactNode }) => children(mockActions),
}));

vi.mock('@/utils/icons', () => ({ ActionIcons: new Proxy({}, { get: () => () => null }), Activity: () => null, AlertCircle: () => null, AlertTriangle: () => null, ArrowDown: () => null, ArrowLeft: () => null, ArrowRight: () => null, ArrowUp: () => null, Ban: () => null, BarChart3: () => null, Bell: () => null, BellRing: () => null, BookOpen: () => null, Calendar: () => null, Check: () => null, CheckCircle2: () => null, ChevronDown: () => null, ChevronLeft: () => null, ChevronRight: () => null, Circle: () => null, CircleDot: () => null, CircleHelp: () => null, ClipboardList: () => null, Clock: () => null, ContextIcons: new Proxy({}, { get: () => () => null }), Copy: () => null, Database: () => null, Download: () => null, ElementIcons: () => null, ExpandIcon: () => null, ExternalLink: () => null, Eye: () => null, FileText: () => null, Filter: () => null, Gauge: () => null, GitBranch: () => null, GitMerge: () => null, Globe: () => null, HelpCircle: () => null, History: () => null, Hourglass: () => null, Inbox: () => null, Info: () => null, Keyboard: () => null, Lightbulb: () => null, Link2: () => null, ListTodo: () => null, Loader2: () => null, LoadingIcon: () => null, MarkIcons: () => null, Minus: () => null, Moon: () => null, NavIcon: () => null, NavIcons: () => null, Network: () => null, Package: () => null, Palette: () => null, Pause: () => null, Play: () => null, PlayCircle: () => null, Plug: () => null, Plus: () => null, RefreshCw: () => null, RefreshIcon: () => null, Rewind: () => null, Rocket: () => null, RotateCcw: () => null, STALENESS_ICONS_COMPONENTS: () => null, STATUS_ICONS_COMPONENTS: () => null, Search: () => null, Settings: () => null, Siren: () => null, SkipForward: () => null, Square: () => null, StalenessIcon: () => null, StatusIcon: () => null, StopCircle: () => null, Sun: () => null, Target: () => null, Terminal: () => null, Timer: () => null, ToastIcons: () => null, Trash2: () => null, UIIcons: () => null, User: () => null, Workflow: () => null, Wrench: () => null, X: () => null, XCircle: () => null, XIcon: () => null, Zap: () => null }));
vi.mock('../utils/icons', () => ({ ActionIcons: new Proxy({}, { get: () => () => null }), Activity: () => null, AlertCircle: () => null, AlertTriangle: () => null, ArrowDown: () => null, ArrowLeft: () => null, ArrowRight: () => null, ArrowUp: () => null, Ban: () => null, BarChart3: () => null, Bell: () => null, BellRing: () => null, BookOpen: () => null, Calendar: () => null, Check: () => null, CheckCircle2: () => null, ChevronDown: () => null, ChevronLeft: () => null, ChevronRight: () => null, Circle: () => null, CircleDot: () => null, CircleHelp: () => null, ClipboardList: () => null, Clock: () => null, ContextIcons: new Proxy({}, { get: () => () => null }), Copy: () => null, Database: () => null, Download: () => null, ElementIcons: () => null, ExpandIcon: () => null, ExternalLink: () => null, Eye: () => null, FileText: () => null, Filter: () => null, Gauge: () => null, GitBranch: () => null, GitMerge: () => null, Globe: () => null, HelpCircle: () => null, History: () => null, Hourglass: () => null, Inbox: () => null, Info: () => null, Keyboard: () => null, Lightbulb: () => null, Link2: () => null, ListTodo: () => null, Loader2: () => null, LoadingIcon: () => null, MarkIcons: () => null, Minus: () => null, Moon: () => null, NavIcon: () => null, NavIcons: () => null, Network: () => null, Package: () => null, Palette: () => null, Pause: () => null, Play: () => null, PlayCircle: () => null, Plug: () => null, Plus: () => null, RefreshCw: () => null, RefreshIcon: () => null, Rewind: () => null, Rocket: () => null, RotateCcw: () => null, STALENESS_ICONS_COMPONENTS: () => null, STATUS_ICONS_COMPONENTS: () => null, Search: () => null, Settings: () => null, Siren: () => null, SkipForward: () => null, Square: () => null, StalenessIcon: () => null, StatusIcon: () => null, StopCircle: () => null, Sun: () => null, Target: () => null, Terminal: () => null, Timer: () => null, ToastIcons: () => null, Trash2: () => null, UIIcons: () => null, User: () => null, Workflow: () => null, Wrench: () => null, X: () => null, XCircle: () => null, XIcon: () => null, Zap: () => null }));
vi.mock('lucide-react', () => ({ Activity: () => null, AlertCircle: () => null, ArrowLeft: () => null, Check: () => null, CheckCircle: () => null, ChevronDown: () => null, ChevronRight: () => null, ChevronUp: () => null, Circle: () => null, Eye: () => null, EyeOff: () => null, HelpCircle: () => null, KeyRound: () => null, ListTodo: () => null, Loader2: () => null, Lock: () => null, LogOut: () => null, Mail: () => null, Menu: () => null, Moon: () => null, Package: () => null, Pause: () => null, RefreshCw: () => null, Shield: () => null, Sun: () => null, User: () => null, Users: () => null, Workflow: () => null, X: () => null, Zap: () => null }));
vi.mock('@/components/ui/button', () => ({
    Button: (props: Record<string, unknown>) => <button onClick={props.onClick as () => void} title={props.title as string} data-variant={props.variant}>{props.children as React.ReactNode}</button>,
}));
vi.mock('../lib/config', () => ({ default: { API_URL: '/api', POLLING_INTERVAL: 5000, AUTH_ENABLED: false } }));
vi.mock('../utils/api', () => ({ api: { get: vi.fn(), post: vi.fn() }, setAuthTokenGetter: vi.fn(), setAuthErrorCallback: vi.fn() }));
vi.mock('@/utils/api', () => ({ api: { get: vi.fn(), post: vi.fn() }, setAuthTokenGetter: vi.fn(), setAuthErrorCallback: vi.fn() }));
vi.mock('../utils/storage', () => ({ getFromStorage: vi.fn(), saveToStorage: vi.fn() }));
vi.mock('@/hooks/useAuth', () => ({ AuthProvider: ({ children }: any) => children, useAuth: () => ({ isSignedIn: true, user: { email: 'test@test.com' }, signOut: vi.fn() }), useAuthHeader: () => ({}), AUTH_STATE: { SIGNED_IN: 'signedIn', SIGNED_OUT: 'signedOut' } }));

import { PipelineDetail } from './PipelineDetail';

/** Set store state for PipelineDetail */
function setStore(overrides: Record<string, unknown> = {}) {
    const store = useAppStore.getState();
    const pipeline = (overrides.pipeline !== undefined ? overrides.pipeline : createPipeline()) as PipelineWithUI | null;
    store.setSelectedPipeline(pipeline);
    store.setSelectedExecution((overrides.selectedExecution ?? null) as null);
    store.setViewMode((overrides.viewMode ?? 'dag') as 'dag' | 'gantt' | 'calendar');
    store.setDate((overrides.date ?? '2024-01-15') as string);
    store.setExecutionPaused((overrides.executionPaused ?? false) as boolean);
}

const defaultProps = {
    apiError: null as string | null,
    navigateToExecution: vi.fn(),
};

describe('PipelineDetail', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        setStore();
        // Reset mock query data
        mockDetailQuery.data = { tasks: mockTasks, dag: mockDag, serverOffsetMs: 0, selectedExecution: null };
        mockDetailQuery.isLoading = false;
    });

    describe('rendering', () => {
        it('renders the DAG graph in dag viewMode', () => {
            render(<PipelineDetail {...defaultProps} />);
            expect(screen.getByTestId('dag-graph')).toBeInTheDocument();
        });

        it('renders calendar in calendar viewMode', () => {
            setStore({ viewMode: 'calendar' });
            render(<PipelineDetail {...defaultProps} />);
            expect(screen.getByTestId('calendar-view')).toBeInTheDocument();
        });

        it('renders gantt in gantt viewMode', () => {
            setStore({ viewMode: 'gantt' });
            render(<PipelineDetail {...defaultProps} />);
            expect(screen.getByTestId('gantt-chart')).toBeInTheDocument();
        });

        it('shows loading skeleton when isLoading', () => {
            mockDetailQuery.isLoading = true;
            mockDetailQuery.data = { tasks: [], dag: null as unknown as DAG, serverOffsetMs: 0, selectedExecution: null };
            render(<PipelineDetail {...defaultProps} />);
            expect(screen.getByTestId('dag-skeleton')).toBeInTheDocument();
        });
    });

    describe('task stats', () => {
        it('filters tasks to match DAG nodes', () => {
            render(<PipelineDetail {...defaultProps} />);
            // 1 running + 1 waiting → Stop button appears
            expect(screen.getByText(/Stop/)).toBeInTheDocument();
        });
    });

    describe('task selection', () => {
        it('updates store when a DAG node is clicked', () => {
            render(<PipelineDetail {...defaultProps} />);
            fireEvent.click(screen.getByTestId('dag-node-extract_data'));
            expect(useAppStore.getState().selectedTaskName).toBe('extract_data');
        });
    });

    describe('DAG-based filtering', () => {
        it('only shows tasks that are in the DAG', () => {
            mockDetailQuery.data = {
                ...mockDetailQuery.data,
                tasks: [...mockTasks, createTask({ task_name: 'orphan_task', status: 'success' })],
            };
            render(<PipelineDetail {...defaultProps} />);
            expect(screen.queryByTestId('dag-node-orphan_task')).not.toBeInTheDocument();
            expect(screen.getByTestId('dag-node-extract_data')).toBeInTheDocument();
        });
    });

    describe('error handling', () => {
        it('shows error message', () => {
            render(<PipelineDetail {...defaultProps} apiError="API connection failed" />);
            expect(screen.getByText(/API connection failed/)).toBeInTheDocument();
        });
    });

    describe('view mode controls', () => {
        it('renders view mode toggle buttons', () => {
            render(<PipelineDetail {...defaultProps} />);
            expect(screen.getByText(/DAG/i)).toBeInTheDocument();
            expect(screen.getByText(/Gantt/i)).toBeInTheDocument();
            expect(screen.getByText(/Calendar/i)).toBeInTheDocument();
        });

        it('updates store when view toggle clicked', () => {
            render(<PipelineDetail {...defaultProps} />);
            fireEvent.click(screen.getByText(/Gantt/i));
            expect(useAppStore.getState().viewMode).toBe('gantt');
        });
    });

    // v0.78.3+ — viewMode shortcuts. v0.78.5: switched from numeric to
    // letter keys (d/g/c) because numeric keys conflict with global
    // top-level navigation in App.tsx. See ADR #64.
    describe('keyboard shortcuts › viewMode', () => {
        it('pressing "g" switches to gantt viewMode', () => {
            render(<PipelineDetail {...defaultProps} />);
            fireEvent.keyDown(document, { key: 'g' });
            expect(useAppStore.getState().viewMode).toBe('gantt');
        });

        it('pressing "c" switches to calendar viewMode', () => {
            render(<PipelineDetail {...defaultProps} />);
            fireEvent.keyDown(document, { key: 'c' });
            expect(useAppStore.getState().viewMode).toBe('calendar');
        });

        it('pressing "d" switches back to dag viewMode', () => {
            setStore({ viewMode: 'gantt' });
            render(<PipelineDetail {...defaultProps} />);
            fireEvent.keyDown(document, { key: 'd' });
            expect(useAppStore.getState().viewMode).toBe('dag');
        });
    });

    describe('action buttons', () => {
        it('has a Run button', () => {
            render(<PipelineDetail {...defaultProps} />);
            expect(screen.getByRole('button', { name: /run/i })).toBeInTheDocument();
        });

        it('renders the Execution history trigger even with no executions on the date (regression: drawer must stay reachable to change the date)', () => {
            const prev = mockExecQuery.data;
            mockExecQuery.data = [];
            render(<PipelineDetail {...defaultProps} />);
            expect(screen.getByRole('button', { name: /Execution history/i })).toBeInTheDocument();
            mockExecQuery.data = prev;
        });

        it('calls handleRun when Run clicked', () => {
            render(<PipelineDetail {...defaultProps} />);
            const runButtons = screen.getAllByText(/Run/i);
            const runBtn = runButtons.find(el => el.textContent?.trim() === 'Run');
            if (runBtn) fireEvent.click(runBtn);
            expect(mockActions.handleRun).toHaveBeenCalled();
        });
    });
});
