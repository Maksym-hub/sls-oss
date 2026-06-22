import React from 'react';

/**
 * Skeleton Components for Loading States
 * 
 * Usage:
 *   <PipelineListSkeleton count={5} />
 *   <DAGSkeleton />
 *   <TaskDetailsSkeleton />
 *   <GanttSkeleton count={6} />
 *   <TableSkeleton rows={5} cols={4} />
 *   <CardSkeleton />
 *   <AssetListSkeleton count={8} />
 */

export function PipelineListSkeleton({ count = 5 }) {
    return (
        <div className="pipeline-list" role="status" aria-label="Loading pipelines">
            <span className="sr-only">Loading…</span>
            {[...Array(count)].map((_, i) => (
                <div key={i} className="sk-skeleton-pipeline-item" style={{ animationDelay: `${i * 50}ms` }}>
                    <div className="sk-skeleton sk-skeleton-pipeline-icon" />
                    <div className="sk-skeleton-pipeline-info">
                        <div className="sk-skeleton sk-skeleton-text lg" />
                        <div className="sk-skeleton sk-skeleton-text sm" />
                    </div>
                </div>
            ))}
        </div>
    );
}

export function DAGSkeleton() {
    return (
        <div className="sk-skeleton-dag" role="status" aria-label="Loading DAG graph">
            <span className="sr-only">Loading…</span>
            <div className="sk-skeleton-dag-nodes">
                {[...Array(5)].map((_, i) => (
                    <div key={i} className="sk-skeleton sk-skeleton-dag-node" style={{ animationDelay: `${i * 100}ms` }} />
                ))}
            </div>
            <svg className="sk-skeleton-dag-edges" viewBox="0 0 400 200">
                <line className="sk-skeleton-dag-edge" x1="50" y1="50" x2="150" y2="100" />
                <line className="sk-skeleton-dag-edge" x1="150" y1="100" x2="250" y2="50" />
                <line className="sk-skeleton-dag-edge" x1="150" y1="100" x2="250" y2="150" />
                <line className="sk-skeleton-dag-edge" x1="250" y1="100" x2="350" y2="100" />
            </svg>
        </div>
    );
}

export function TaskDetailsSkeleton() {
    return (
        <div className="sk-skeleton-details" role="status" aria-label="Loading task details">
            <div className="sk-skeleton-details-header">
                <div className="sk-skeleton sk-skeleton-details-icon" />
                <div className="sk-skeleton-details-title">
                    <div className="sk-skeleton sk-skeleton-text lg" />
                    <div className="sk-skeleton sk-skeleton-text sm" />
                </div>
            </div>
            <div className="sk-skeleton-details-section">
                <div className="sk-skeleton sk-skeleton-text" />
                <div className="sk-skeleton sk-skeleton-text sm" />
                <div className="sk-skeleton sk-skeleton-text" />
            </div>
        </div>
    );
}

export function GanttSkeleton({ count = 6 }) {
    return (
        <div className="sk-skeleton-gantt" role="status" aria-label="Loading Gantt chart">
            {[...Array(count)].map((_, i) => (
                <div key={i} className="sk-skeleton-gantt-row" style={{ animationDelay: `${i * 50}ms` }}>
                    <div className="sk-skeleton sk-skeleton-gantt-label" />
                    <div 
                        className="sk-skeleton sk-skeleton-gantt-bar" 
                        style={{ width: `${30 + ((i * 37 + 13) % 50)}%` }} 
                    />
                </div>
            ))}
        </div>
    );
}

export function TableSkeleton({ rows = 5, cols = 4 }) {
    return (
        <div className="sk-skeleton-table" role="status" aria-label="Loading table">
            <span className="sr-only">Loading…</span>
            <div className="sk-skeleton-table-header">
                {[...Array(cols)].map((_, i) => (
                    <div key={i} className="sk-skeleton sk-skeleton-table-cell header" />
                ))}
            </div>
            <div className="sk-skeleton-table-body">
                {[...Array(rows)].map((_, rowIdx) => (
                    <div key={rowIdx} className="sk-skeleton-table-row" style={{ animationDelay: `${rowIdx * 50}ms` }}>
                        {[...Array(cols)].map((_, colIdx) => (
                            <div key={colIdx} className="sk-skeleton sk-skeleton-table-cell" />
                        ))}
                    </div>
                ))}
            </div>
        </div>
    );
}

export function CardSkeleton({ showImage = false }) {
    return (
        <div className="sk-skeleton-card" role="status" aria-label="Loading card">
            {showImage && <div className="sk-skeleton sk-skeleton-card-image" />}
            <div className="sk-skeleton-card-content">
                <div className="sk-skeleton sk-skeleton-text lg" />
                <div className="sk-skeleton sk-skeleton-text" />
                <div className="sk-skeleton sk-skeleton-text sm" />
            </div>
        </div>
    );
}

export function AssetListSkeleton({ count = 8 }) {
    return (
        <div className="sk-skeleton-asset-list" role="status" aria-label="Loading assets">
            {[...Array(count)].map((_, i) => (
                <div key={i} className="sk-skeleton-asset-item" style={{ animationDelay: `${i * 40}ms` }}>
                    <div className="sk-skeleton sk-skeleton-asset-icon" />
                    <div className="sk-skeleton-asset-info">
                        <div className="sk-skeleton sk-skeleton-text" />
                        <div className="sk-skeleton sk-skeleton-text xs" />
                    </div>
                    <div className="sk-skeleton sk-skeleton-asset-badge" />
                </div>
            ))}
        </div>
    );
}

export function EventListSkeleton({ count = 10 }) {
    return (
        <div className="sk-skeleton-event-list" role="status" aria-label="Loading events">
            {[...Array(count)].map((_, i) => (
                <div key={i} className="sk-skeleton-event-item" style={{ animationDelay: `${i * 30}ms` }}>
                    <div className="sk-skeleton sk-skeleton-event-time" />
                    <div className="sk-skeleton sk-skeleton-event-content" />
                </div>
            ))}
        </div>
    );
}

export function MetricsSkeleton() {
    return (
        <div className="sk-skeleton-metrics" role="status" aria-label="Loading metrics">
            {[...Array(4)].map((_, i) => (
                <div key={i} className="sk-skeleton-metric-card" style={{ animationDelay: `${i * 100}ms` }}>
                    <div className="sk-skeleton sk-skeleton-metric-value" />
                    <div className="sk-skeleton sk-skeleton-text sm" />
                </div>
            ))}
        </div>
    );
}

export function LineageSkeleton() {
    return (
        <div className="sk-skeleton-lineage" role="status" aria-label="Loading lineage graph">
            <div className="sk-skeleton-lineage-nodes">
                {[...Array(7)].map((_, i) => (
                    <div 
                        key={i} 
                        className="sk-skeleton sk-skeleton-lineage-node" 
                        style={{ 
                            animationDelay: `${i * 80}ms`,
                            left: `${10 + (i % 3) * 30}%`,
                            top: `${20 + Math.floor(i / 3) * 35}%`
                        }} 
                    />
                ))}
            </div>
        </div>
    );
}
