import { useState, useCallback } from 'react';
import { api } from '../utils';
import type { Task, Execution, TaskFilter, RunFilter } from '../types';

/**
 * useGlobalData - Hook for managing global data (all tasks, all runs)
 * 
 * Used in the History view (runs + tasks)
 */
export function useGlobalData(date: string) {
    const [allTasks, setAllTasks] = useState<Task[]>([]);
    const [allRuns, setAllRuns] = useState<Execution[]>([]);
    const [taskFilter, setTaskFilter] = useState<TaskFilter>({ status: '', date: '', pipeline: '', taskName: '' });
    const [runFilter, setRunFilter] = useState<RunFilter>({ status: '', pipeline: '' });
    
    // Load all tasks with filters
    const loadAllTasks = useCallback(async () => {
        const params = new URLSearchParams();
        if (taskFilter.status) params.append('status', taskFilter.status);
        if (taskFilter.date) params.append('date', taskFilter.date);
        if (taskFilter.pipeline) params.append('pipeline', taskFilter.pipeline);
        
        const data = await api.get(`/tasks?${params.toString()}`);
        if (!data.error) {
            let tasks: Task[] = data.tasks || [];
            // Client-side filter by task name
            if (taskFilter.taskName) {
                const search = taskFilter.taskName.toLowerCase();
                tasks = tasks.filter((t: Task) => t.task_name?.toLowerCase().includes(search));
            }
            setAllTasks(tasks);
        }
    }, [taskFilter]);
    
    // Load all runs with filters
    const loadAllRuns = useCallback(async () => {
        const params = new URLSearchParams();
        params.append('date', date);
        if (runFilter.status) params.append('status', runFilter.status);
        if (runFilter.pipeline) params.append('pipeline', runFilter.pipeline);
        
        const data = await api.get(`/runs?${params.toString()}`);
        if (!data.error) setAllRuns(data.runs || []);
    }, [date, runFilter]);
    
    return {
        // Data
        allTasks,
        allRuns,
        
        // Filters
        taskFilter,
        runFilter,
        setTaskFilter,
        setRunFilter,
        
        // Actions
        loadAllTasks,
        loadAllRuns,
    };
}
