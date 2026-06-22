import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DAGGraphFlow from './DAGGraphFlow';
import { createDAG, createTask } from '../test/factories';

// ─── Component mocks ────────────────────────────────────────────────────────
// ResizeObserver is not available in jsdom
class MockResizeObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
}
global.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;

vi.mock('@/utils/icons', () => ({ ActionIcons: new Proxy({}, { get: () => () => null }), Activity: () => null, AlertCircle: () => null, AlertTriangle: () => null, ArrowDown: () => null, ArrowLeft: () => null, ArrowRight: () => null, ArrowUp: () => null, Ban: () => null, BarChart3: () => null, Bell: () => null, BellRing: () => null, BookOpen: () => null, Calendar: () => null, Check: () => null, CheckCircle2: () => null, ChevronDown: () => null, ChevronLeft: () => null, ChevronRight: () => null, Circle: () => null, CircleDot: () => null, CircleHelp: () => null, ClipboardList: () => null, Clock: () => null, ContextIcons: new Proxy({}, { get: () => () => null }), Copy: () => null, Database: () => null, Download: () => null, ElementIcons: () => null, ExpandIcon: () => null, ExternalLink: () => null, Eye: () => null, FileText: () => null, Filter: () => null, Gauge: () => null, GitBranch: () => null, GitMerge: () => null, Globe: () => null, HelpCircle: () => null, History: () => null, Hourglass: () => null, Inbox: () => null, Info: () => null, Keyboard: () => null, Lightbulb: () => null, Link2: () => null, ListTodo: () => null, Loader2: () => null, LoadingIcon: () => null, MarkIcons: () => null, Minus: () => null, Moon: () => null, NavIcon: () => null, NavIcons: () => null, Network: () => null, Package: () => null, Palette: () => null, Pause: () => null, Play: () => null, PlayCircle: () => null, Plug: () => null, Plus: () => null, RefreshCw: () => null, RefreshIcon: () => null, Rewind: () => null, Rocket: () => null, RotateCcw: () => null, STALENESS_ICONS_COMPONENTS: () => null, STATUS_ICONS_COMPONENTS: () => null, Search: () => null, Settings: () => null, Siren: () => null, SkipForward: () => null, Square: () => null, StalenessIcon: () => null, StatusIcon: () => null, StopCircle: () => null, Sun: () => null, Target: () => null, Terminal: () => null, Timer: () => null, ToastIcons: () => null, Trash2: () => null, UIIcons: () => null, User: () => null, Workflow: () => null, Wrench: () => null, X: () => null, XCircle: () => null, XIcon: () => null, Zap: () => null }));
vi.mock('../utils/icons', () => ({ ActionIcons: new Proxy({}, { get: () => () => null }), Activity: () => null, AlertCircle: () => null, AlertTriangle: () => null, ArrowDown: () => null, ArrowLeft: () => null, ArrowRight: () => null, ArrowUp: () => null, Ban: () => null, BarChart3: () => null, Bell: () => null, BellRing: () => null, BookOpen: () => null, Calendar: () => null, Check: () => null, CheckCircle2: () => null, ChevronDown: () => null, ChevronLeft: () => null, ChevronRight: () => null, Circle: () => null, CircleDot: () => null, CircleHelp: () => null, ClipboardList: () => null, Clock: () => null, ContextIcons: new Proxy({}, { get: () => () => null }), Copy: () => null, Database: () => null, Download: () => null, ElementIcons: () => null, ExpandIcon: () => null, ExternalLink: () => null, Eye: () => null, FileText: () => null, Filter: () => null, Gauge: () => null, GitBranch: () => null, GitMerge: () => null, Globe: () => null, HelpCircle: () => null, History: () => null, Hourglass: () => null, Inbox: () => null, Info: () => null, Keyboard: () => null, Lightbulb: () => null, Link2: () => null, ListTodo: () => null, Loader2: () => null, LoadingIcon: () => null, MarkIcons: () => null, Minus: () => null, Moon: () => null, NavIcon: () => null, NavIcons: () => null, Network: () => null, Package: () => null, Palette: () => null, Pause: () => null, Play: () => null, PlayCircle: () => null, Plug: () => null, Plus: () => null, RefreshCw: () => null, RefreshIcon: () => null, Rewind: () => null, Rocket: () => null, RotateCcw: () => null, STALENESS_ICONS_COMPONENTS: () => null, STATUS_ICONS_COMPONENTS: () => null, Search: () => null, Settings: () => null, Siren: () => null, SkipForward: () => null, Square: () => null, StalenessIcon: () => null, StatusIcon: () => null, StopCircle: () => null, Sun: () => null, Target: () => null, Terminal: () => null, Timer: () => null, ToastIcons: () => null, Trash2: () => null, UIIcons: () => null, User: () => null, Workflow: () => null, Wrench: () => null, X: () => null, XCircle: () => null, XIcon: () => null, Zap: () => null }));

// Mock ReactFlow — renders nodes as divs for testability

vi.mock('reactflow', () => {
    const Background = () => <div data-testid="rf-background" />;
    const Controls = () => <div data-testid="rf-controls" />;
    const MiniMap = () => <div data-testid="rf-minimap" />;
    const Panel = ({ children, position }: { children: React.ReactNode; position: string; className?: string }) => (
        <div data-testid={`rf-panel-${position}`}>{children}</div>
    );

    const ReactFlow = ({ nodes, edges, onNodeClick, onNodeContextMenu, children }: {
        nodes: { id: string; data: { label: string; status: string } }[];
        edges: { id: string }[];
        onNodeClick?: (e: unknown, node: { id: string }) => void;
        onNodeContextMenu?: (e: unknown, node: { id: string }) => void;
        children?: React.ReactNode;
    }) => {
        return (
            <div data-testid="react-flow">
                {nodes?.map(n => (
                    <div
                        key={n.id}
                        data-testid={`rf-node-${n.id}`}
                        data-status={n.data?.status}
                        onClick={() => onNodeClick?.({}, { id: n.id })}
                        onContextMenu={(e) => { e.preventDefault(); onNodeContextMenu?.({ preventDefault: () => {} }, { id: n.id }); }}
                    >
                        {n.data?.label}
                    </div>
                ))}
                {edges?.map(e => <div key={e.id} data-testid={`rf-edge-${e.id}`} />)}
                {children}
            </div>
        );
    };
    ReactFlow.displayName = 'ReactFlow';

    return {
        __esModule: true,
        default: ReactFlow,
        Background,
        BackgroundVariant: { Dots: 'dots' },
        Controls,
        MiniMap,
        Panel,
        MarkerType: { ArrowClosed: 'arrowclosed' },
        Handle: ({ type, position }: { type: string; position: string }) => <div data-testid={`handle-${type}-${position}`} />,
        Position: { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' },
        useNodesState: vi.fn((init: unknown[]) => [init, vi.fn(), vi.fn()]),
        useEdgesState: vi.fn((init: unknown[]) => [init, vi.fn(), vi.fn()]),
    };
});

// Mock dagre for layout
vi.mock('dagre', () => {
    const mockGraph = {
        setGraph: vi.fn(),
        setDefaultEdgeLabel: vi.fn(),
        setNode: vi.fn(),
        setEdge: vi.fn(),
        node: vi.fn((_id: string) => ({ x: 100, y: 50 })),
    };
    return {
        default: {
            graphlib: { Graph: vi.fn(() => mockGraph) },
            layout: vi.fn(),
        },
    };
});

vi.mock('../utils', () => ({
    normalizeStatus: (s: string) => s,
    formatCountdown: (s: number) => `${s}s`,
    formatWaitBadge: () => null,
    formatDuration: (ms: number) => `${Math.round(ms / 1000)}s`,
}));
vi.mock('../utils/constants', () => ({
    TASK_STATUS: { WAITING_DELAY: 'waiting_delay', DEPS_READY: 'deps_ready', STOPPED: 'stopped' },
    isTerminalStatus: (s: string) => ['success', 'succeeded', 'failed', 'skipped'].includes(s),
    getWaitingReason: () => null,
    MS: { TICK_INTERVAL: 1000 },
}));
vi.mock('reactflow/dist/style.css', () => ({}));

// ─── Tests ──────────────────────────────────────────────────────────────────

describe('DAGGraphFlow', () => {
    const defaultProps = {
        dag: createDAG(),
        tasks: [
            createTask({ task_name: 'init_config', status: 'success' }),
            createTask({ task_name: 'extract_data', status: 'success' }),
            createTask({ task_name: 'transform', status: 'running' }),
            createTask({ task_name: 'load_db', status: 'waiting' }),
        ],
        selectedTask: null,
        onSelectTask: vi.fn(),
        serverOffsetMs: 0,
    };

    beforeEach(() => {
        vi.clearAllMocks();
    });

    // ─── Rendering ──────────────────────────────────────────────────────

    describe('rendering', () => {
        it('renders empty state when dag has no nodes', () => {
            render(<DAGGraphFlow {...defaultProps} dag={{ nodes: [], edges: [] }} />);
            expect(screen.getByText('No tasks found for this date')).toBeInTheDocument();
        });

        it('renders empty state when dag is null', () => {
            render(<DAGGraphFlow {...defaultProps} dag={null} />);
            expect(screen.getByText('No tasks found for this date')).toBeInTheDocument();
        });

        it('renders ReactFlow with correct number of nodes', () => {
            render(<DAGGraphFlow {...defaultProps} />);
            expect(screen.getByTestId('react-flow')).toBeInTheDocument();
            expect(screen.getByTestId('rf-node-init_config')).toBeInTheDocument();
            expect(screen.getByTestId('rf-node-extract_data')).toBeInTheDocument();
            expect(screen.getByTestId('rf-node-transform')).toBeInTheDocument();
            expect(screen.getByTestId('rf-node-load_db')).toBeInTheDocument();
        });

        it('renders edges between nodes', () => {
            render(<DAGGraphFlow {...defaultProps} />);
            expect(screen.getByTestId('rf-edge-init_config-extract_data')).toBeInTheDocument();
            expect(screen.getByTestId('rf-edge-extract_data-transform')).toBeInTheDocument();
            expect(screen.getByTestId('rf-edge-transform-load_db')).toBeInTheDocument();
        });

        it('renders Background, Controls, and MiniMap', () => {
            render(<DAGGraphFlow {...defaultProps} />);
            expect(screen.getByTestId('rf-background')).toBeInTheDocument();
            expect(screen.getByTestId('rf-controls')).toBeInTheDocument();
            expect(screen.getByTestId('rf-minimap')).toBeInTheDocument();
        });

        it('renders stats panel with task counts', () => {
            render(<DAGGraphFlow {...defaultProps} />);
            const statsPanel = screen.getByTestId('rf-panel-top-right');
            expect(statsPanel).toBeInTheDocument();
        });

        it('renders legend panel', () => {
            render(<DAGGraphFlow {...defaultProps} />);
            expect(screen.getByText('Success')).toBeInTheDocument();
            expect(screen.getByText('Running')).toBeInTheDocument();
            expect(screen.getByText('Failed')).toBeInTheDocument();
            expect(screen.getByText('Waiting')).toBeInTheDocument();
        });
    });

    // ─── Blueprint Mode ─────────────────────────────────────────────────

    describe('blueprint mode', () => {
        it('shows blueprint label when isBlueprint=true', () => {
            render(<DAGGraphFlow {...defaultProps} isBlueprint={true} tasks={[]} />);
            expect(screen.getByText(/Blueprint/)).toBeInTheDocument();
        });

        it('hides legend in blueprint mode', () => {
            render(<DAGGraphFlow {...defaultProps} isBlueprint={true} tasks={[]} />);
            expect(screen.queryByText('Success')).not.toBeInTheDocument();
        });
    });

    // ─── Interactions ───────────────────────────────────────────────────

    describe('interactions', () => {
        it('calls onSelectTask when node is clicked', () => {
            render(<DAGGraphFlow {...defaultProps} />);
            fireEvent.click(screen.getByTestId('rf-node-transform'));
            expect(defaultProps.onSelectTask).toHaveBeenCalledTimes(1);
            expect(defaultProps.onSelectTask).toHaveBeenCalledWith(
                expect.objectContaining({ task_name: 'transform' })
            );
        });

        it('calls onSelectTask on right-click (context menu)', () => {
            render(<DAGGraphFlow {...defaultProps} />);
            fireEvent.contextMenu(screen.getByTestId('rf-node-load_db'));
            expect(defaultProps.onSelectTask).toHaveBeenCalledWith(
                expect.objectContaining({ task_name: 'load_db' })
            );
        });

        it('creates placeholder task for unknown nodes', () => {
            const dag = createDAG({ nodes: [...createDAG().nodes, { id: 'unknown_task', outlets: [], inlets: [], skip_on_backfill: false }] });
            render(<DAGGraphFlow {...defaultProps} dag={dag} />);
            fireEvent.click(screen.getByTestId('rf-node-unknown_task'));
            expect(defaultProps.onSelectTask).toHaveBeenCalledWith(
                expect.objectContaining({ task_name: 'unknown_task', status: 'waiting' })
            );
        });
    });

    // ─── Accessibility ──────────────────────────────────────────────────

    describe('accessibility', () => {
        it('has role="figure" on container', () => {
            render(<DAGGraphFlow {...defaultProps} />);
            const container = screen.getByRole('figure');
            expect(container).toBeInTheDocument();
        });

        it('has aria-label on container', () => {
            render(<DAGGraphFlow {...defaultProps} />);
            const container = screen.getByRole('figure');
            expect(container).toHaveAttribute('aria-label', 'Pipeline task dependency graph');
        });
    });

    // ─── Edge Styling ───────────────────────────────────────────────────

    describe('edge styling', () => {
        it('renders all edges for the dag', () => {
            render(<DAGGraphFlow {...defaultProps} />);
            const edges = screen.getAllByTestId(/^rf-edge-/);
            expect(edges.length).toBe(3);
        });
    });

    // Note (v0.75.7): TaskNode-internal behaviour (trigger_rule badge,
    // notification warning, status icon, label) is unit-tested in
    // DAGTaskNode.test.tsx — that file imports the named TaskNode export
    // directly and bypasses the ReactFlow mock entirely. This file
    // continues to exercise wiring (edges, panel layout, callbacks);
    // node internals belong next to TaskNode itself.
});
