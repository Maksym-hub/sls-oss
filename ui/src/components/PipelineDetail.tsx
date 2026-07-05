import React, { useState, useMemo, useEffect, lazy, Suspense } from 'react';
import { Button } from '@/components/ui/button';
import { 
    DAGGraph, 
    DAGSkeleton, 
    GanttSkeleton,
    ErrorBoundary,
} from './index';
import { normalizeStatus, POLLING } from '../utils';
import { useAppStore } from '../stores/useAppStore';
import { useShallow } from 'zustand/react/shallow';
import { useToast, useKeyboardShortcuts, SHORTCUTS } from '../hooks';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryClient';
import { paidSurface } from '@/ee-active.generated';
import { PipelineActionsProvider } from '@/components/PipelineActionsProvider';
import type { PipelineActions, PipelineActionsParams } from '@/types';
import { 
    usePipelineDetailQuery,
    usePipelineExecutionsQuery,
    usePipelinesQuery,
    useTaskEventsQuery,
} from '../hooks/queries';
import { 
    GitBranch, 
    BarChart3, 
    Calendar, 
    RefreshCw, 
    Play, 
    Pause, 
    Square, 
    Rocket, 
    ActionIcons,
    Clock,
    FileText,
    AlertTriangle,
    Inbox,
    ArrowLeft,
    Loader2,
    X
} from '../utils/icons';
import type { Task, Execution } from '@/types';

// Lazy load heavy modals (only loaded when opened)
const TaskDetailModal = lazy(() => import('./TaskDetailModal'));

/**
 * PipelineDetail - Main content area showing pipeline execution details.
 * Self-contained: fetches data, manages actions, renders modals.
 */
interface PipelineDetailProps {
    apiError: string | null;
    navigateToExecution: (name: string, execId?: string, date?: string) => void;
}

export function PipelineDetail({ apiError, navigateToExecution }: PipelineDetailProps) {
    const {
        selectedPipeline: pipeline,
        selectedExecution,
        setSelectedExecution,
        viewMode,
        setViewMode,
        date,
        setDate,
        executionPaused, setExecutionPaused,
        liveMode,
        selectedTaskName,
        selectTask,
        showTaskModal, setShowTaskModal,
        openBackfillModal,
    } = useAppStore(useShallow(s => ({
        selectedPipeline: s.selectedPipeline,
        selectedExecution: s.selectedExecution,
        setSelectedExecution: s.setSelectedExecution,
        viewMode: s.viewMode,
        setViewMode: s.setViewMode,
        date: s.date,
        setDate: s.setDate,
        executionPaused: s.executionPaused, setExecutionPaused: s.setExecutionPaused,
        liveMode: s.liveMode,
        selectedTaskName: s.selectedTaskName,
        selectTask: s.selectTask,
        showTaskModal: s.showTaskModal, setShowTaskModal: s.setShowTaskModal,
        openBackfillModal: s.openBackfillModal,
    })));

    // ========== Data ==========
    const [hasActiveCountdown, setHasActiveCountdown] = useState(false);
    const pipelineName = pipeline?.name ?? '';
    const executionId = selectedExecution?.execution_id ?? null;

    const { 
        data: detailData,
        isLoading,
        isFetching,
    } = usePipelineDetailQuery(pipelineName, date, executionId, {
        refetchInterval: liveMode && pipelineName ? (hasActiveCountdown ? POLLING.ACTIVE : POLLING.IDLE) : false,
    });

    const tasks = useMemo(() => detailData?.tasks ?? [], [detailData?.tasks]);
    const dag = detailData?.dag ?? null;
    const serverOffsetMs = detailData?.serverOffsetMs ?? 0;

    const { data: executions = [] } = usePipelineExecutionsQuery(pipelineName, date);
    const { data: pipelines = [] } = usePipelinesQuery();

    // ========== Derived ==========
    const selectedTask = useMemo(() => 
        tasks?.find((t: Task) => t.task_name === selectedTaskName) || null,
        [tasks, selectedTaskName]
    );

    const { data: taskEvents = [], isLoading: taskEventsLoading } = useTaskEventsQuery(
        selectedTask?.execution_name ?? null, 
        showTaskModal
    );

    const dagTaskNames = useMemo(() => dag?.nodes?.map(n => n.id) || [], [dag]);
    const filteredTasks = useMemo(() => 
        tasks.filter(t => dagTaskNames.includes(t.task_name)),
        [tasks, dagTaskNames]
    );

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect -- derive countdown flag from the latest tasks
        setHasActiveCountdown(tasks.some(
            t => ['deps_ready', 'waiting_delay'].includes(t.status) && Number(t.wait_before || 0) > 0
        ));
    }, [tasks]);

    // ========== Auto-select execution ==========
    useEffect(() => {
        if (detailData?.selectedExecution && !selectedExecution) {
            setSelectedExecution(detailData.selectedExecution);
        }
    // Omits: selectedExecution, setSelectedExecution (only auto-select when no execution is chosen)
    }, [detailData?.selectedExecution]); // eslint-disable-line react-hooks/exhaustive-deps

    // ========== Pause detection ==========
    useEffect(() => {
        const hasPausedTasks = filteredTasks.some(t => t.status === 'waiting_paused');
        if (hasPausedTasks && !executionPaused) setExecutionPaused(true);
        else if (!hasPausedTasks && executionPaused) setExecutionPaused(false);
    }, [filteredTasks, executionPaused, setExecutionPaused]);

    // ========== Actions ==========
    const toast = useToast();
    const showToast = (message: string, type = 'info') => toast.show(message, type);

    const queryClient = useQueryClient();
    // eslint-disable-next-line react-hooks/preserve-manual-memoization -- manual useCallback kept intentionally
    const handleRefresh = React.useCallback(() => {
        queryClient.invalidateQueries({ queryKey: queryKeys.pipelines });
        if (pipeline?.name) queryClient.invalidateQueries({ queryKey: ['pipeline', pipeline.name] });
    }, [queryClient, pipeline?.name]);

    // Pipeline action provider — free (ADR #110): task/execution intervention
    // ships in every build, so the provider is always present (no OSS gating).
    const actionParams: PipelineActionsParams = {
        selectedPipeline: pipeline,
        selectedTask,
        selectedExecution,
        executions,
        tasks,
        dag,
        date,
        setDate,
        setSelectedExecution,
        showToast,
        onSelectTask: (task: Task) => selectTask(task?.task_name || null),
    };

    // Team-tier pipeline view-modes (absent in the OSS build) — ADR #99.
    const GanttChart = paidSurface.GanttChart;
    const CalendarView = paidSurface.CalendarView;

    const onTaskSelect = (task: Task) => selectTask(task.task_name);

    // Keyboard shortcuts per ADR #64 (revised v0.78.5).
    //
    // Numeric keys 1-9 are RESERVED for top-level navigation in App.tsx
    // (1=Pipelines, 2=Assets, 3=Tasks, 4=Runs, 5=Backfills). Inner-surface
    // shortcuts use letter keys matching the first letter of the tab name
    // to avoid double-firing handlers and the resulting unpredictable UX.
    useKeyboardShortcuts({
        [SHORTCUTS.REFRESH]: handleRefresh,
        'd': () => setViewMode('dag'),
        'g': () => setViewMode('gantt'),
        'c': () => setViewMode('calendar'),
    });

    // ========== UI State ==========
    const [showHistory, setShowHistory] = useState(false);

    const stats = useMemo(() => ({
        done: filteredTasks.filter(t => t.status === 'success' || t.status === 'succeeded' || t.status === 'skipped').length,
        active: filteredTasks.filter(t => t.status === 'running' || t.status === 'deps_ready' || t.status === 'waiting_delay').length,
        failed: filteredTasks.filter(t => t.status === 'failed' || t.status === 'upstream_failed').length,
        wait: filteredTasks.filter(t => t.status === 'waiting').length,
        stopped: filteredTasks.filter(t => t.status === 'stopped' || t.status === 'aborted').length,
        paused: filteredTasks.filter(t => t.status === 'waiting_paused').length,
        total: dagTaskNames.length
    }), [filteredTasks, dagTaskNames.length]);

    // Close dropdown on outside click
    React.useEffect(() => {
        const handleClick = (e: Event) => {
            if ((e.target as HTMLElement).closest('.dropdown-container')) return;
            setShowHistory(false);
        };
        if (showHistory) {
            document.addEventListener('click', handleClick as EventListener);
            return () => document.removeEventListener('click', handleClick as EventListener);
        }
    }, [showHistory]);

    const content = (actions: PipelineActions | null) => (
        <>
        <section className="pd-canvas">
            {/* Error Banner */}
            {apiError && <div className="pd-error-banner"><AlertTriangle size={16} /> {apiError}</div>}

            {/* Canvas Header */}
            <div className="pd-canvas-header">
                <div>
                    <div className="pd-canvas-title">{pipeline?.name || 'Select a pipeline'}</div>
                    <div className="pd-canvas-subtitle flex items-center gap-md">
                        {pipeline ? (
                            <>
                                <span>
                                    Execution: {selectedExecution 
                                        ? `${selectedExecution.execution_short || selectedExecution.execution_id?.substring(0, 8)}... (${selectedExecution.date || date})`
                                        : date}
                                </span>
                                {executions.length > 0 && (
                                    <ExecutionDropdown
                                        executions={executions}
                                        showHistory={showHistory}
                                        onToggleHistory={() => setShowHistory(!showHistory)}
                                        onCloseHistory={() => setShowHistory(false)}
                                    />
                                )}
                            </>
                        ) : (
                            'Choose from the sidebar'
                        )}
                    </div>
                </div>

                {/* Actions */}
                {pipeline && (
                    <div className="flex items-center gap-lg">
                        {/* View Mode Tabs */}
                        <div className="nav-pills" role="tablist" aria-label="View mode">
                            <div 
                                className={`nav-pill nav-pill--md ${viewMode === 'dag' ? 'active' : ''}`} 
                                onClick={() => setViewMode('dag')}
                                role="tab"
                                aria-selected={viewMode === 'dag'}
                                tabIndex={viewMode === 'dag' ? 0 : -1}
                                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setViewMode('dag'); } }}
                            >
                                <GitBranch size={14} /> DAG
                            </div>
                            {GanttChart && (
                            <div 
                                className={`nav-pill nav-pill--md ${viewMode === 'gantt' ? 'active' : ''}`} 
                                onClick={() => setViewMode('gantt')}
                                role="tab"
                                aria-selected={viewMode === 'gantt'}
                                tabIndex={viewMode === 'gantt' ? 0 : -1}
                                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setViewMode('gantt'); } }}
                            >
                                <BarChart3 size={14} /> Gantt
                            </div>
                            )}
                            {CalendarView && (
                            <div 
                                className={`nav-pill nav-pill--md ${viewMode === 'calendar' ? 'active' : ''}`} 
                                onClick={() => setViewMode('calendar')}
                                role="tab"
                                aria-selected={viewMode === 'calendar'}
                                tabIndex={viewMode === 'calendar' ? 0 : -1}
                                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setViewMode('calendar'); } }}
                            >
                                <Calendar size={14} /> Calendar
                            </div>
                            )}
                        </div>

                        {/* Action Buttons */}
                        <div className="pd-canvas-actions">
                            <Button variant="secondary" onClick={handleRefresh} disabled={isFetching}>
                                {isFetching
                                    ? <><Loader2 size={14} className="animate-spin" /> Refreshing...</>
                                    : <><RefreshCw size={14} /> Refresh</>
                                }
                            </Button>
                            
                            {actions && (<>
                            {(stats.active > 0 || stats.paused > 0) && (
                                <Button
                                    variant={executionPaused ? 'default' : 'outline'}
                                    className={executionPaused 
                                        ? 'bg-green-600 hover:bg-green-700' 
                                        : 'border-yellow-500 text-yellow-600 hover:bg-yellow-50'}
                                    onClick={actions.handlePauseResume}
                                    title={executionPaused 
                                        ? 'Resume pipeline execution' 
                                        : 'Pause pipeline (running tasks will complete)'}
                                >
                                    {executionPaused ? <><Play size={14} /> Resume</> : <><Pause size={14} /> Pause</>}
                                </Button>
                            )}
                            
                            {(stats.active > 0 || stats.wait > 0 || stats.paused > 0) && (
                                <Button variant="destructive" onClick={actions.handleStop}>
                                    <Square size={14} /> Stop
                                </Button>
                            )}
                            
                            <Button onClick={actions.handleRun}><Rocket size={14} /> Run</Button>
                            
                            <Button
                                variant="secondary"
                                onClick={() => {
                                    if (!pipeline?.name) return;
                                    openBackfillModal({
                                        origin: 'pipeline',
                                        target: { type: 'pipeline', name: pipeline.name },
                                    });
                                }}
                                title="Backfill pipeline for date range"
                            >
                                <ActionIcons.backfill size={14} /> Backfill
                            </Button>
                            </>)}
                        </div>
                    </div>
                )}
            </div>

            {/* Paused Execution Banner */}
            {executionPaused && pipeline && actions && (
                <div className="pd-pause-banner">
                    <span className="pd-pause-banner-icon"><Pause size={18} /></span>
                    <span className="pd-pause-banner-text">
                        Pipeline paused – {stats.paused} task{stats.paused !== 1 ? 's' : ''} waiting (12h timeout)
                    </span>
                    <Button size="sm" variant="secondary" onClick={actions.handleExtendPause} title="Extend pause by 12 hours">
                        <Clock size={14} /> +12h
                    </Button>
                    <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={actions.handlePauseResume}>
                        <Play size={14} /> Resume
                    </Button>
                </div>
            )}

            {/* Main Content */}
            <div className="pd-canvas-content relative">
                {/* Loading Overlay */}
                {isLoading && (
                    <div className="pd-loading-overlay" role="status" aria-live="polite">
                        <div className="pd-loading-spinner"><Loader2 size={24} className="animate-spin" /></div>
                        <span className="sr-only">Loading pipeline data…</span>
                    </div>
                )}

                {/* Content States */}
                {!pipeline ? (
                    <EmptyState
                        icon={<ArrowLeft size={48} className="text-gray-300" />}
                        title="Select a pipeline"
                        text="Choose a pipeline from the sidebar to view its execution graph"
                    />
                ) : isLoading && !dag ? (
                    viewMode === 'gantt' && GanttChart ? <GanttSkeleton count={6} /> : <DAGSkeleton />
                ) : executions.length === 0 && !isLoading && viewMode !== 'calendar' ? (
                    (dag?.nodes?.length ?? 0) > 0 ? (
                        <div className="relative h-full">
                            <DAGGraph
                                dag={dag}
                                tasks={[]}
                                selectedTask={null}
                                onSelectTask={() => {}}
                                serverOffsetMs={0}
                                isBlueprint={true}
                            />
                            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-[var(--bg-primary)] px-5 py-2.5 rounded-lg shadow-lg border border-[var(--border)] z-10 text-[var(--text-muted)] text-[13px]">
                                No executions for {date}
                            </div>
                        </div>
                    ) : (
                    <EmptyState
                        icon={<Inbox size={48} className="text-gray-300" />}
                        title={`No executions for ${date}`}
                        text="This pipeline has no runs on this date."
                    />
                    )
                ) : viewMode === 'calendar' && CalendarView ? (
                    <ErrorBoundary fallback={<ErrorFallback message="Failed to load calendar." onRetry={() => window.location.reload()} />}>
                        <CalendarView
                            executions={executions}
                            selectedDate={date}
                            onSelectDate={(d: string) => {
                                setDate(d);
                                setSelectedExecution(null);
                            }}
                            pipelineName={pipeline.name}
                        />
                    </ErrorBoundary>
                ) : viewMode === 'gantt' && GanttChart ? (
                    <ErrorBoundary fallback={<ErrorFallback message="Failed to load Gantt chart." onRetry={() => setViewMode('dag')} retryText="Switch to DAG" />}>
                        <GanttChart
                            tasks={filteredTasks}
                            selectedTask={selectedTask}
                            onSelectTask={onTaskSelect}
                        />
                    </ErrorBoundary>
                ) : (
                    <ErrorBoundary fallback={<ErrorFallback message="Failed to load DAG." onRetry={() => setViewMode('table')} retryText="Switch to Table" />}>
                        <DAGGraph
                            dag={dag}
                            tasks={filteredTasks}
                            selectedTask={selectedTask}
                            onSelectTask={onTaskSelect}
                            serverOffsetMs={serverOffsetMs}
                        />
                    </ErrorBoundary>
                )}
            </div>
        </section>

        {/* Task Detail Modal */}
        {showTaskModal && selectedTask && (
            <Suspense fallback={null}>
            <TaskDetailModal
                task={selectedTask}
                tasks={tasks}
                dag={dag}
                pipelines={pipelines}
                taskEvents={taskEvents}
                taskEventsLoading={taskEventsLoading}
                onClose={() => setShowTaskModal(false)}
                onAction={actions ? (action: string) => actions.handleTaskAction(action, selectedTask) : undefined}
                onRunAction={actions?.handleRunAction}
                onTaskSelect={(task: Task) => selectTask(task.task_name)}
                onOpenPipeline={(name: string, d?: string | null) => {
                    setShowTaskModal(false);
                    navigateToExecution(name, undefined, d || undefined);
                }}
                onPauseResume={actions?.handlePauseResume}
                serverOffsetMs={serverOffsetMs}
            />
            </Suspense>
        )}
        </>
    );

    return (
        <PipelineActionsProvider params={actionParams}>
            {(actions) => content(actions)}
        </PipelineActionsProvider>
    );
}

/**
 * ExecutionDropdown — reads selectedExecution and date from store
 */
function ExecutionDropdown({ 
    executions, 
    showHistory, 
    onToggleHistory, 
    onCloseHistory
}: { 
    executions: Execution[]; 
    showHistory: boolean; 
    onToggleHistory: () => void; 
    onCloseHistory: () => void;
}) {
    const { selectedExecution, setSelectedExecution, date, setDate } = useAppStore(useShallow(s => ({
        selectedExecution: s.selectedExecution, setSelectedExecution: s.setSelectedExecution,
        date: s.date, setDate: s.setDate,
    })));

    return (
        <div className="pd-dropdown-container">
            <Button variant="secondary" size="sm" onClick={onToggleHistory}>
                <FileText size={14} /> Executions ({executions.length})
            </Button>
            
            {selectedExecution && (
                <Button
                    variant="secondary"
                    size="sm"
                    className="ml-2"
                    onClick={() => {
                        setSelectedExecution(null);
                        setDate(new Date().toISOString().split('T')[0]);
                    }}
                    title="Clear filter, show today"
                >
                    <X size={14} />
                </Button>
            )}
            
            {showHistory && (
                <div className="pd-dropdown-menu">
                    <div className="pd-dropdown-header">PIPELINE EXECUTIONS</div>
                    {executions.map((ex, i: number) => {
                        const isSelected = selectedExecution?.execution_id === ex.execution_id || 
                                          (!selectedExecution && ex.date === date);
                        const statusClass = normalizeStatus(ex.status);
                        
                        return (
                            <div
                                key={i}
                                className={`pd-dropdown-item ${isSelected ? 'selected' : ''}`}
                                onClick={() => {
                                    setSelectedExecution({ ...ex, auto_selected: false });
                                    if (ex.date) setDate(ex.date);
                                    onCloseHistory();
                                }}
                            >
                                <div className="flex-between">
                                    <span className="pd-dropdown-item-title">
                                        {ex.execution_short || (ex.execution_id ? ex.execution_id.substring(0, 8) : ex.date)}...
                                    </span>
                                    <span className={`pd-exec-status-mini ${statusClass}`}>
                                        {ex.status || 'unknown'}
                                    </span>
                                </div>
                                <div className="pd-dropdown-item-meta">
                                    {ex.started_at ? new Date(ex.started_at).toLocaleString() : ex.date}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

/**
 * EmptyState - Empty state placeholder
 */
function EmptyState({ icon, title, text, children }: { icon: React.ReactNode; title: string; text?: string; children?: React.ReactNode }) {
    return (
        <div className="empty-state">
            <div className="empty-state-icon">{icon}</div>
            <div className="empty-state-title">{title}</div>
            <div className="empty-state-text">
                {text}
                {children}
            </div>
        </div>
    );
}

/**
 * ErrorFallback - Error fallback UI
 */
function ErrorFallback({ message, onRetry, retryText = 'Reload' }: { message: string; onRetry: () => void; retryText?: string }) {
    return (
        <div className="pd-error-fallback">
            {message} <button onClick={onRetry}>{retryText}</button>
        </div>
    );
}

export default PipelineDetail;
