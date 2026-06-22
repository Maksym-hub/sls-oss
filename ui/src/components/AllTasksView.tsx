import React, { useState, useMemo, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { TableSkeleton } from './Skeletons';
import { formatDuration } from '../utils';
import { StatusIcon, ListTodo, Search, X, Inbox } from '../utils/icons';
import { SortableHeader } from './SortableHeader';
import { useAppStore } from '@/stores/useAppStore';
import { useShallow } from 'zustand/react/shallow';
import { useAllTasksQuery, usePipelinesQuery } from '@/hooks/queries';
import { useUrlSync } from '@/hooks/useUrlSync';
import { useKeyboardShortcuts, SHORTCUTS } from '@/hooks';
import type { PipelineWithUI, TaskFilter } from '@/types';

interface AllTasksViewProps {
    onPipelineClick: (pipeline: PipelineWithUI, date?: string) => void;
}

interface TasksUrlState {
    status?: string;
    date?: string;
    pipeline?: string;
    taskName?: string;
    [key: string]: string | undefined;
}
const TASKS_URL_KEYS = ['status', 'date', 'pipeline', 'taskName'] as const;

/**
 * AllTasksView - Global view of all task instances across pipelines
 */
export function AllTasksView({
    onPipelineClick,
}: AllTasksViewProps) {
    const { taskFilter: filter, setTaskFilter: onFilterChange } = useAppStore(useShallow(s => ({
        taskFilter: s.taskFilter, setTaskFilter: s.setTaskFilter,
    })));

    // ─── URL Sync ─────────────────────────────────────────────────────────
    const { initialState: urlInitial, replaceUrl: replaceTasksUrl } = useUrlSync<TasksUrlState>({
        keys: TASKS_URL_KEYS,
        onChange: (state) => {
            // Browser back/forward — apply URL → filter
            onFilterChange({
                status: state.status || '',
                date: state.date || '',
                pipeline: state.pipeline || '',
                taskName: state.taskName || '',
            });
        },
    });

    // On mount, apply URL state to filter (if any params present)
    const initialized = useRef(false);
    useEffect(() => {
        if (initialized.current) return;
        initialized.current = true;
        if (urlInitial.status || urlInitial.date || urlInitial.pipeline || urlInitial.taskName) {
            onFilterChange({
                status: urlInitial.status || '',
                date: urlInitial.date || '',
                pipeline: urlInitial.pipeline || '',
                taskName: urlInitial.taskName || '',
            });
        }
    // Mount-only: initialize once from URL state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Mirror filter → URL silently
    useEffect(() => {
        replaceTasksUrl({
            status: filter.status || undefined,
            date: filter.date || undefined,
            pipeline: filter.pipeline || undefined,
            taskName: filter.taskName || undefined,
        });
    // Omits replaceTasksUrl (stable callback ref)
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [filter.status, filter.date, filter.pipeline, filter.taskName]);

    const { data: pipelines = [] } = usePipelinesQuery();
    const allTasksQuery = useAllTasksQuery(filter, true);
    const { data: tasks = [], isLoading: loading } = allTasksQuery;
    const [sort, setSort] = useState({ key: '', dir: 'desc' });
    const taskNameInputRef = useRef<HTMLInputElement>(null);

    // List-view shortcuts (ADR #64): refresh + focus filter.
    useKeyboardShortcuts({
        [SHORTCUTS.REFRESH]: () => allTasksQuery.refetch(),
        [SHORTCUTS.FOCUS_FILTER]: () => taskNameInputRef.current?.focus(),
    });
    
    const handleSort = (key: string) => {
        setSort(prev => ({
            key,
            dir: prev.key === key && prev.dir === 'desc' ? 'asc' : 'desc'
        }));
    };
    
    const sortedTasks = useMemo(() => {
        if (!sort.key) return tasks;
        const sorted = [...tasks].sort((a, b) => {
            let va: string | number = '', vb: string | number = '';
            switch (sort.key) {
                case 'task_name': va = a.task_name || ''; vb = b.task_name || ''; break;
                case 'pipeline_name': va = a.pipeline_name || ''; vb = b.pipeline_name || ''; break;
                case 'status': va = a.status || ''; vb = b.status || ''; break;
                case 'date': va = a.date || ''; vb = b.date || ''; break;
                case 'duration_ms': va = a.duration_ms || 0; vb = b.duration_ms || 0; break;
                case 'started_at': va = a.running_at || a.started_at || ''; vb = b.running_at || b.started_at || ''; break;
                default: return 0;
            }
            if (typeof va === 'number' && typeof vb === 'number') return sort.dir === 'asc' ? va - vb : vb - va;
            return sort.dir === 'asc' ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
        });
        return sorted;
    }, [tasks, sort]);
    
    const hasActiveFilters = filter.status || filter.date || filter.pipeline || filter.taskName;

    const clearFilters = () => {
        onFilterChange({ status: '', date: '', pipeline: '', taskName: '' });
    };

    const handlePipelineClick = (pipelineName: string, taskDate: string) => {
        const pipeline = pipelines.find(p => p.name === pipelineName);
        if (pipeline) {
            onPipelineClick(pipeline, taskDate);
        }
    };

    return (
        <div className="panel-section">
            {/* Filter Bar */}
            <div className="filter-bar">
                <h2 className="title-lg"><ListTodo size={20} /> All Task Instances</h2>
                
                <div className="filter-controls">
                    {/* Pipeline Filter */}
                    <select
                        value={filter.pipeline}
                        onChange={e => onFilterChange({ ...filter, pipeline: e.target.value })}
                        className="input-sm"
                    >
                        <option value="">All Pipelines</option>
                        {pipelines.map(p => (
                            <option key={p.name} value={p.name}>{p.name}</option>
                        ))}
                    </select>

                    {/* Task Name Search */}
                    <input
                        ref={taskNameInputRef}
                        type="text"
                        placeholder="Task name..."
                        value={filter.taskName}
                        onChange={e => onFilterChange({ ...filter, taskName: e.target.value })}
                        className="input-sm w-[150px]"
                    />

                    {/* Status Filter */}
                    <select
                        value={filter.status}
                        onChange={e => onFilterChange({ ...filter, status: e.target.value })}
                        className="input-sm"
                    >
                        <option value="">All Statuses</option>
                        <option value="success">Success</option>
                        <option value="failed">Failed</option>
                        <option value="running">Running</option>
                        <option value="waiting">Waiting</option>
                    </select>

                    {/* Date Filter */}
                    <input
                        type="date"
                        value={filter.date}
                        onChange={e => onFilterChange({ ...filter, date: e.target.value })}
                        className="input-sm"
                    />

                    {/* Clear Button */}
                    {hasActiveFilters && (
                        <Button size="sm" variant="secondary" onClick={clearFilters}>
                            <X size={14} className="mr-1" /> Clear
                        </Button>
                    )}
                </div>

                {/* Task Count */}
                <span className="text-muted text-md">
                    {loading ? (
                        <span className="loading-spinner-sm" />
                    ) : (
                        `${tasks.length} tasks`
                    )}
                </span>
            </div>

            {/* Tasks Table */}
            <div className="card">
                {loading ? (
                    <TableSkeleton rows={10} cols={6} />
                ) : (
                    <table className="table-full" aria-label="Task executions">
                        <thead>
                            <tr className="table-header">
                                <SortableHeader label="Task" sortKey="task_name" currentSort={sort} onSort={handleSort} />
                                <SortableHeader label="Pipeline" sortKey="pipeline_name" currentSort={sort} onSort={handleSort} />
                                <SortableHeader label="Status" sortKey="status" currentSort={sort} onSort={handleSort} />
                                <SortableHeader label="Date" sortKey="date" currentSort={sort} onSort={handleSort} />
                                <SortableHeader label="Duration" sortKey="duration_ms" currentSort={sort} onSort={handleSort} />
                                <SortableHeader label="Started" sortKey="started_at" currentSort={sort} onSort={handleSort} />
                            </tr>
                        </thead>
                        <tbody>
                            {sortedTasks.map((task, i: number) => (
                                <tr key={i} className="border-b">
                                    <td className="p-md">
                                        <span className="text-mono">{task.task_name}</span>
                                    </td>
                                    <td className="p-md">
                                        <span
                                            className="text-accent clickable"
                                            onClick={() => handlePipelineClick(task.pipeline_name, task.date || '')}
                                        >
                                            {task.pipeline_name}
                                        </span>
                                    </td>
                                    <td className="p-md">
                                        <span className={`task-status-badge ${task.status}`}>
                                            <StatusIcon status={task.status} size={14} /> {task.status}
                                        </span>
                                    </td>
                                    <td className="table-cell-mono">{task.date}</td>
                                    <td className="table-cell-mono">
                                        {formatDuration(task.duration_ms)}
                                    </td>
                                    <td className="p-md text-sm text-muted">
                                        {(task.running_at || task.started_at) ? new Date(task.running_at || task.started_at || '').toLocaleString() : '-'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}

                {/* Empty State */}
                {!loading && tasks.length === 0 && (
                    <div className="empty-state">
                        <div className="empty-state-icon">{hasActiveFilters ? <Search size={32} /> : <Inbox size={32} />}</div>
                        <div className="empty-state-title">
                            {hasActiveFilters ? 'No matching tasks' : 'No tasks found'}
                        </div>
                        <div className="empty-state-text">
                            {hasActiveFilters
                                ? 'Try adjusting your filters'
                                : 'Task instances will appear here when pipelines run'}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default AllTasksView;
