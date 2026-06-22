import { useQuery } from '@tanstack/react-query';
import { api } from '../../utils';
import { queryKeys } from '../../lib/queryClient';
import type { RunFeedRow, Task } from '../../types';

/**
 * useAllTasksQuery - Fetch all tasks with filters
 */
export function useAllTasksQuery(filters: { status?: string; date?: string; pipeline?: string; taskName?: string } = {}, enabled = true) {
    const { status, date, pipeline, taskName } = filters;
    
    return useQuery({
        queryKey: queryKeys.allTasks(filters),
        queryFn: async () => {
            const params = new URLSearchParams();
            if (status) params.append('status', status);
            if (date) params.append('date', date);
            if (pipeline) params.append('pipeline', pipeline);
            
            const data = await api.get(`/tasks?${params.toString()}`);
            if (data.error) {
                throw new Error(data.error);
            }
            
            let tasks: Task[] = data.tasks || [];
            
            // Client-side filter by task name
            if (taskName) {
                const search = taskName.toLowerCase();
                tasks = tasks.filter(t => t.task_name?.toLowerCase().includes(search));
            }
            
            return tasks;
        },
        enabled,
        staleTime: 5 * 1000,
    });
}

/**
 * useAllRunsQuery - Fetch all runs with filters
 */
export function useAllRunsQuery(date: string, filters: { status?: string; pipeline?: string } = {}, enabled = true) {
    const { status, pipeline } = filters;
    
    return useQuery({
        queryKey: queryKeys.allRuns(date, filters),
        queryFn: async () => {
            const params = new URLSearchParams();
            params.append('date', date);
            if (status) params.append('status', status);
            if (pipeline) params.append('pipeline', pipeline);
            
            const data = await api.get(`/runs?${params.toString()}`);
            if (data.error) {
                throw new Error(data.error);
            }
            return (data.runs || []) as RunFeedRow[];
        },
        enabled: enabled && !!date,
        staleTime: 5 * 1000,
    });
}

/**
 * useTaskEventsQuery - Fetch events for a specific task execution
 */
export function useTaskEventsQuery(executionName: string | null, isModalOpen: boolean) {
    return useQuery({
        queryKey: queryKeys.taskEvents(executionName ?? ''),
        queryFn: async () => {
            const resp = await api.get(`/task-events?name=${encodeURIComponent(executionName!)}`);
            if (resp.error) {
                throw new Error(resp.error);
            }
            return resp.events || [];
        },
        enabled: !!executionName && isModalOpen,
        staleTime: 10 * 1000,
    });
}


/**
 * useNotificationsQuery - Fetch pipeline failure notifications
 * Polls every 30 seconds, returns raw notifications from API
 */
export function useNotificationsQuery(limit = 10, hours = 4) {
    return useQuery({
        queryKey: queryKeys.notifications(limit, hours),
        queryFn: async () => {
            const data = await api.get(`/notifications?limit=${limit}&hours=${hours}`);
            if (data.error) {
                throw new Error(data.error);
            }
            return data.notifications || [];
        },
        staleTime: 15 * 1000,
        refetchInterval: 30 * 1000,
    });
}

const globalQueries = {
    useAllTasksQuery,
    useAllRunsQuery,
    useTaskEventsQuery,
    useNotificationsQuery,
};

export default globalQueries;
