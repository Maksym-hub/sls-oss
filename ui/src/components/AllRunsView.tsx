import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { TableSkeleton } from './Skeletons';
import { formatDuration } from '../utils';
import { 
    Activity, 
    RefreshCw, 
    Search,
    Inbox,
    ActionIcons,
} from '../utils/icons';
import { SortableHeader } from './SortableHeader';
import { useAppStore } from '@/stores/useAppStore';
import { useShallow } from 'zustand/react/shallow';
import { useAllRunsQuery, usePipelinesQuery } from '@/hooks/queries';
import { useUrlSync } from '@/hooks/useUrlSync';
import { useKeyboardShortcuts, SHORTCUTS } from '@/hooks';
import type { PipelineWithUI, Execution, RunFeedRow } from '@/types';

interface AllRunsViewProps {
    onPipelineClick: (pipeline: PipelineWithUI, run: Execution) => void;
}

interface RunsUrlState {
    status?: string;
    pipeline?: string;
    [key: string]: string | undefined;
}
const RUNS_URL_KEYS = ['status', 'pipeline'] as const;

/**
 * AllRunsView - Global view of all pipeline runs/executions
 */
export function AllRunsView({
    onPipelineClick,
}: AllRunsViewProps) {
    const router = useRouter();
    const { date, runFilter: filter, setRunFilter: onFilterChange } = useAppStore(useShallow(s => ({
        date: s.date, runFilter: s.runFilter, setRunFilter: s.setRunFilter,
    })));

    // ─── URL Sync ─────────────────────────────────────────────────────────
    // Note: `date` is shared with global header, not in URL here (header
    // already controls it). We sync only filter (status, pipeline).
    const { initialState: urlInitial, replaceUrl: replaceRunsUrl } = useUrlSync<RunsUrlState>({
        keys: RUNS_URL_KEYS,
        onChange: (state) => {
            onFilterChange({
                status: state.status || '',
                pipeline: state.pipeline || '',
            });
        },
    });

    const initialized = useRef(false);
    useEffect(() => {
        if (initialized.current) return;
        initialized.current = true;
        if (urlInitial.status || urlInitial.pipeline) {
            onFilterChange({
                status: urlInitial.status || '',
                pipeline: urlInitial.pipeline || '',
            });
        }
    // Mount-only: initialize once from URL state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        replaceRunsUrl({
            status: filter.status || undefined,
            pipeline: filter.pipeline || undefined,
        });
    // Omits replaceRunsUrl (stable callback ref)
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [filter.status, filter.pipeline]);

    const { data: pipelines = [] } = usePipelinesQuery();
    const { data: runs = [], isLoading: loading, refetch: refetchAllRuns } = useAllRunsQuery(date, filter, true);
    const [sort, setSort] = useState({ key: '', dir: 'desc' });

    // List-view shortcuts (ADR #64): refresh.
    useKeyboardShortcuts({
        [SHORTCUTS.REFRESH]: () => refetchAllRuns(),
    });
    
    const handleSort = (key: string) => {
        setSort(prev => ({
            key,
            dir: prev.key === key && prev.dir === 'desc' ? 'asc' : 'desc'
        }));
    };
    
    const sortedRuns = useMemo(() => {
        if (!sort.key) return runs;
        const sorted = [...runs].sort((a, b) => {
            let va: string | number = '', vb: string | number = '';
            switch (sort.key) {
                case 'pipeline_name': va = a.pipeline_name || ''; vb = b.pipeline_name || ''; break;
                case 'status': va = a.status || ''; vb = b.status || ''; break;
                case 'date': va = a.date || ''; vb = b.date || ''; break;
                case 'duration_ms': va = a.duration_ms || 0; vb = b.duration_ms || 0; break;
                case 'started_at': va = a.started_at || ''; vb = b.started_at || ''; break;
                default: return 0;
            }
            if (typeof va === 'number' && typeof vb === 'number') return sort.dir === 'asc' ? va - vb : vb - va;
            return sort.dir === 'asc' ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
        });
        return sorted;
    }, [runs, sort]);
    
    const hasActiveFilters = filter.pipeline || filter.status;

    const clearFilters = () => {
        onFilterChange({ status: '', pipeline: '' });
    };

    const handlePipelineClick = (run: RunFeedRow) => {
        const pipeline = pipelines.find(p => p.name === run.pipeline_name);
        if (pipeline) {
            onPipelineClick(pipeline, run);
        }
    };

    return (
        <div className="panel-section">
            {/* Filter Bar */}
            <div className="filter-bar">
                <h2 className="title-lg"><Activity size={20} /> All Pipeline Runs</h2>
                
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

                    {/* Status Filter */}
                    <select
                        value={filter.status}
                        onChange={e => onFilterChange({ ...filter, status: e.target.value })}
                        className="input-sm"
                    >
                        <option value="">All Statuses</option>
                        <optgroup label="Runs">
                            <option value="succeeded">Succeeded</option>
                            <option value="failed">Failed</option>
                            <option value="running">Running</option>
                            <option value="aborted">Aborted</option>
                        </optgroup>
                        <optgroup label="Backfills">
                            <option value="pending">Pending</option>
                            <option value="completed">Completed</option>
                            <option value="partial">Partial</option>
                            <option value="canceled">Canceled</option>
                        </optgroup>
                    </select>

                    {/* Clear Button */}
                    {hasActiveFilters && (
                        <Button size="sm" variant="secondary" onClick={clearFilters}>
                            Clear
                        </Button>
                    )}
                </div>

                {/* Run Count */}
                <span className="text-muted text-md">
                    {loading ? (
                        <span className="loading-spinner-sm" />
                    ) : (
                        `${runs.length} runs`
                    )}
                </span>

                {/* Refresh Button */}
                <Button size="sm" variant="secondary" onClick={() => refetchAllRuns()}>
                    <RefreshCw size={14} /> Refresh
                </Button>
            </div>

            {/* Runs Table */}
            <div className="card">
                {loading ? (
                    <TableSkeleton rows={10} cols={7} />
                ) : (
                    <table className="table-full" aria-label="Pipeline executions">
                        <thead>
                            <tr className="table-header">
                                <SortableHeader label="Pipeline" sortKey="pipeline_name" currentSort={sort} onSort={handleSort} />
                                <th className="arv-table-cell">Execution</th>
                                <SortableHeader label="Status" sortKey="status" currentSort={sort} onSort={handleSort} />

                                <SortableHeader label="Date" sortKey="date" currentSort={sort} onSort={handleSort} />
                                <SortableHeader label="Duration" sortKey="duration_ms" currentSort={sort} onSort={handleSort} />
                                <SortableHeader label="Started" sortKey="started_at" currentSort={sort} onSort={handleSort} />
                                <th className="arv-table-cell">Backfill</th>
                            </tr>
                        </thead>
                        <tbody>
                            {sortedRuns.map((run, i: number) => {
                                const isBackfill = run.kind === 'backfill';
                                const rowKey = isBackfill
                                    ? `bf-${run.backfill_id}`
                                    : `ex-${run.pipeline_execution || i}`;
                                return (
                                <tr key={rowKey} className="border-b">
                                    <td className="p-md">
                                        <span
                                            className="text-accent clickable font-medium"
                                            onClick={() => handlePipelineClick(run)}
                                        >
                                            {run.pipeline_name}
                                        </span>
                                    </td>
                                    <td className="table-cell-mono">
                                        {isBackfill ? (
                                            <span className="text-muted" title="Backfill — multiple executions">
                                                <ActionIcons.backfill size={12} /> {run.completed_partitions ?? 0}/{run.total_partitions ?? 0} partitions
                                            </span>
                                        ) : (
                                            <>{run.pipeline_execution_short || run.pipeline_execution?.substring(0, 8)}...</>
                                        )}
                                    </td>
                                    <td className="p-md">
                                        {isBackfill ? (
                                            <span className={`bl-status-pill bl-status-pill--${run.status}`}>
                                                {String(run.status) === 'partial'
                                                    ? `partial (${run.completed_partitions ?? 0}/${run.total_partitions ?? 0})`
                                                    : run.status}
                                            </span>
                                        ) : (
                                            <span className={`task-status-badge ${run.status}`}>
                                                {run.status}
                                            </span>
                                        )}
                                    </td>

                                    <td className="table-cell-mono">{isBackfill ? '—' : run.date}</td>
                                    <td className="table-cell-mono">
                                        {formatDuration(run.duration_ms)}
                                    </td>
                                    <td className="p-md text-sm text-muted">
                                        {run.started_at ? new Date(run.started_at).toLocaleString() : '-'}
                                    </td>
                                    <td className="table-cell-mono">
                                        {run.backfill_id ? (
                                            <span
                                                className="text-accent clickable"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    router.push(`/backfills/${run.backfill_id}/`);
                                                }}
                                                title={`View backfill ${run.backfill_id}`}
                                            >
                                                <ActionIcons.backfill size={12} /> {run.backfill_id}
                                            </span>
                                        ) : (
                                            <span className="text-muted">—</span>
                                        )}
                                    </td>
                                </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}

                {/* Empty State */}
                {!loading && runs.length === 0 && (
                    <div className="empty-state">
                        <div className="empty-state-icon">{hasActiveFilters ? <Search size={32} /> : <Inbox size={32} />}</div>
                        <div className="empty-state-title">
                            {hasActiveFilters ? 'No matching runs' : 'No runs found'}
                        </div>
                        <div className="empty-state-text">
                            {hasActiveFilters
                                ? 'Try adjusting your filters'
                                : 'Pipeline runs will appear here when executions complete'}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default AllRunsView;
