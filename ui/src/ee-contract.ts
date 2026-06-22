/**
 * Type contract for the Team-tier UI surface that crosses the open-core
 * boundary (ADR #99). Free code depends only on these types; the concrete
 * surface comes from `@/ee-active.generated` — the real `src/ee/` barrel in the
 * full build, an empty stub in the OSS build.
 */
import type { ComponentType, ReactNode } from 'react';
import type {
  GanttChartProps, Execution, ConsecutiveProgressProps, DependencyStatusListProps,
  PipelineWithUI, Task, SelectedExecution, DAG,
} from '@/types';

/**
 * Inputs the Team pipeline-actions provider needs from the (free) PipelineDetail
 * host. Mirrors the former local interface in usePipelineActions (ADR #99).
 */
export interface PipelineActionsParams {
  selectedPipeline: PipelineWithUI | null;
  selectedTask: Task | null;
  selectedExecution: SelectedExecution | null;
  executions: Execution[];
  tasks: Task[];
  dag: DAG | null;
  date: string;
  setDate: (date: string) => void;
  setSelectedExecution: (exec: SelectedExecution | null) => void;
  showToast: (msg: string, type: string) => void;
  onSelectTask: (task: Task) => void;
}

/**
 * The subset of action handlers the free PipelineDetail host consumes via the
 * provider's render-prop. The hook returns a superset (modal state etc.) which
 * stays internal to the Team provider (ADR #99).
 */
export interface PipelineActions {
  handleRun: () => void;
  handleStop: () => void;
  handlePauseResume: () => void;
  handleExtendPause: () => void;
  handleTaskAction: (action: string, task?: Task | null) => void;
  handleRunAction: (actionType: string, task: Task) => void;
}

/** Props for the Team calendar view-mode rendered inside PipelineDetail (ADR #99). */
export interface CalendarViewProps {
  executions: Execution[];
  selectedDate: string;
  onSelectDate: (date: string) => void;
  pipelineName: string;
}

export interface PaidSurface {
  /** Personal Access Token management (ADR #65/#66). Rendered in SettingsModal. */
  ApiTokensSection?: ComponentType;
  /** /backfills route view: list + detail sub-routing (ADR #99). */
  BackfillsView?: ComponentType;
  /** /assets route view: matrix, lineage, detail, asset-tabs (ADR #99). */
  AssetsView?: ComponentType;
  /** Gantt view-mode in the pipelines view (ADR #99). */
  GanttChart?: ComponentType<GanttChartProps>;
  /** Calendar view-mode in the pipelines view (ADR #99). */
  CalendarView?: ComponentType<CalendarViewProps>;
  /** Host for the cross-cutting backfill modal, rendered once in App (ADR #99). */
  BackfillModalHost?: ComponentType;
  /** Consecutive-run progress shown in the task modal (ADR #99). */
  ConsecutiveProgress?: ComponentType<ConsecutiveProgressProps>;
  /** Dependency status list shown in the task modal (ADR #99). */
  DependencyStatusList?: ComponentType<DependencyStatusListProps>;
  /**
   * Owns usePipelineActions + renders ActionModal; exposes action handlers to
   * the free PipelineDetail host via a render-prop. Absent in OSS, so the host's
   * intervention/task-action UI is gated off there (ADR #99).
   */
  PipelineActionsProvider?: ComponentType<{
    params: PipelineActionsParams;
    children: (actions: PipelineActions) => ReactNode;
  }>;
}
