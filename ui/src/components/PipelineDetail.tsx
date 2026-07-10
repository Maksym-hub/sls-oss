import React, { useState, useMemo, useEffect, lazy, Suspense } from 'react';
import { Button } from '@/components/ui/button';
import { DatePicker } from './DatePicker';
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
    BookOpen,
    AlertTriangle,
    Inbox,
    ArrowLeft,
    Loader2
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
        'g': () => { if (GanttChart) setViewMode('gantt'); },
        'c': () => { if (CalendarView) setViewMode('calendar'); },
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


    // Date of this pipeline's most recent run (from the sidebar stats), so an empty
    // date can offer a one-click jump to the latest execution instead of guessing.
    const latestRunDate = useMemo(() => {
        const full = pipelines.find(p => p.name === pipeline?.name) ?? pipeline;
        return full?.recent_runs?.find(r => r.date)?.date ?? null;
    }, [pipelines, pipeline]);

    // Close dropdown on outside click
    React.useEffect(() => {
        const handleClick = (e: Event) => {
            if ((e.target as HTMLElement).closest('.pd-dropdown-container')) return;
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
                                    Execution scope: {selectedExecution
                                        ? `${selectedExecution.execution_short || selectedExecution.execution_id?.substring(0, 8)}... (${selectedExecution.date || date})`
                                        : date}
                                </span>
                                {/* Always render — the drawer owns the date picker,
                                    so it must be reachable even when the current date
                                    has no executions (otherwise the page deadlocks). */}
                                <ExecutionDropdown
                                    executions={executions}
                                    latestRunDate={latestRunDate}
                                    showHistory={showHistory}
                                    onToggleHistory={() => setShowHistory(!showHistory)}
                                    onCloseHistory={() => setShowHistory(false)}
                                />
                            </>
                        ) : (
                            'Choose from the sidebar'
                        )}
                    </div>
                </div>

                {/* Actions */}
                {pipeline && (
                    <div className="flex items-center gap-lg">
                        {/* View Mode Tabs — only when more than one view exists.
                            In OSS, DAG is the only view, so no tab strip is shown. */}
                        {(GanttChart || CalendarView) && (
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
                        )}

                        {/* Action buttons — state-driven. Refresh is icon-only utility;
                            the run/pause/resume/stop set switches on pipeline state. */}
                        <div className="pd-canvas-actions">
                            <div className="pd-action-group pd-action-group--utility">
                                <Button variant="secondary" onClick={handleRefresh} disabled={isFetching} title="Refresh" aria-label="Refresh">
                                    <RefreshCw size={16} className={isFetching ? 'animate-spin' : ''} />
                                </Button>
                            </div>

                            {actions && (
                                executionPaused ? (
                                    <div className="pd-action-group pd-action-group--danger">
                                        <Button
                                            variant="default"
                                            className="bg-green-600 hover:bg-green-700"
                                            onClick={actions.handlePauseResume}
                                            disabled={!!actions.pendingAction}
                                            title="Resume pipeline execution"
                                        >
                                            {actions.pendingAction === 'resume'
                                                ? <><Loader2 size={14} className="animate-spin" /> Resuming…</>
                                                : <><Play size={14} /> Resume</>}
                                        </Button>
                                        <span className="pd-action-sep" aria-hidden="true" />
                                        <Button variant="destructive" onClick={actions.handleStop} disabled={!!actions.pendingAction}>
                                            {actions.pendingAction === 'stop'
                                                ? <><Loader2 size={14} className="animate-spin" /> Stopping…</>
                                                : <><Square size={14} /> Stop</>}
                                        </Button>
                                    </div>
                                ) : (stats.active > 0 || stats.wait > 0) ? (
                                    <div className="pd-action-group pd-action-group--danger">
                                        <Button
                                            variant="outline"
                                            onClick={actions.handlePauseResume}
                                            disabled={!!actions.pendingAction}
                                            title="Pause pipeline (running tasks will complete)"
                                        >
                                            {actions.pendingAction === 'pause'
                                                ? <><Loader2 size={14} className="animate-spin" /> Pausing…</>
                                                : <><Pause size={14} /> Pause</>}
                                        </Button>
                                        <span className="pd-action-sep" aria-hidden="true" />
                                        <Button variant="destructive" onClick={actions.handleStop} disabled={!!actions.pendingAction}>
                                            {actions.pendingAction === 'stop'
                                                ? <><Loader2 size={14} className="animate-spin" /> Stopping…</>
                                                : <><Square size={14} /> Stop</>}
                                        </Button>
                                    </div>
                                ) : (
                                    <div className="pd-action-group pd-action-group--primary">
                                        <Button onClick={actions.handleRun} disabled={!!actions.pendingAction}>
                                            {actions.pendingAction === 'run'
                                                ? <><Loader2 size={14} className="animate-spin" /> Starting…</>
                                                : <><Rocket size={14} /> Run</>}
                                        </Button>

                                        {paidSurface.BackfillNavTab && (
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
                                        )}
                                    </div>
                                )
                            )}
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
                            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-[var(--bg-primary)] px-5 py-2.5 rounded-lg shadow-lg border border-[var(--border)] z-10 text-[var(--text-muted)] text-[13px] flex items-center gap-3">
                                <span>No executions for {date}</span>
                                {latestRunDate && latestRunDate !== date ? (
                                    <Button
                                        size="sm"
                                        onClick={() => { setSelectedExecution(null); setDate(latestRunDate); }}
                                    >
                                        View latest run · {latestRunDate}
                                    </Button>
                                ) : (
                                    <span>— open <strong>Execution history</strong> to pick another date</span>
                                )}
                            </div>
                        </div>
                    ) : (
                    <EmptyState
                        icon={<Inbox size={48} className="text-gray-300" />}
                        title={`No executions for ${date}`}
                        text="This pipeline has no runs on this date."
                    >
                        {latestRunDate && latestRunDate !== date && (
                            <Button onClick={() => { setSelectedExecution(null); setDate(latestRunDate); }}>
                                View latest run · {latestRunDate}
                            </Button>
                        )}
                    </EmptyState>
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
    latestRunDate,
    showHistory,
    onToggleHistory,
    onCloseHistory
}: {
    executions: Execution[];
    latestRunDate: string | null;
    showHistory: boolean;
    onToggleHistory: () => void;
    onCloseHistory: () => void;
}) {
    const { selectedExecution, setSelectedExecution, date, setDate } = useAppStore(useShallow(s => ({
        selectedExecution: s.selectedExecution, setSelectedExecution: s.setSelectedExecution,
        date: s.date, setDate: s.setDate,
    })));

    // Clear the manual selection and jump back to the latest run.
    const goLatest = () => {
        setSelectedExecution(null);
        if (latestRunDate) setDate(latestRunDate);
        onCloseHistory();
    };

    return (
        <div className="pd-dropdown-container">
            <Button variant="secondary" size="sm" onClick={onToggleHistory}>
                <BookOpen size={16} /> History ({executions.length})
            </Button>

            {showHistory && (
                <div className="pd-exec-dropdown" role="dialog" aria-label="Execution history">
                    <div className="pd-exec-dropdown-head">
                        <span className="pd-exec-dropdown-title">Execution history</span>
                    </div>

                    {/* Date scope — on the pipeline page the date scopes which executions show */}
                    <div className="pd-exec-dropdown-datebar">
                        <DatePicker
                            value={date}
                            onChange={d => { setSelectedExecution(null); setDate(d); }}
                            placeholder="All dates"
                            ariaLabel="Execution date"
                        />
                        {latestRunDate && (date !== latestRunDate || (selectedExecution && !selectedExecution.auto_selected)) && (
                            <Button
                                variant="secondary"
                                size="sm"
                                className="ml-auto"
                                onClick={goLatest}
                                title="Back to the latest run"
                            >
                                Latest
                            </Button>
                        )}
                    </div>

                    <div className="pd-exec-dropdown-list">
                        {executions.length === 0 && (
                            <div className="pd-exec-dropdown-empty">No executions for this date</div>
                        )}
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
