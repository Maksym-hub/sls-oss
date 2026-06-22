import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useGlobalData } from './useGlobalData';

// Mock api
vi.mock('../utils', () => ({
  api: {
    get: vi.fn(),
  },
}));

import { api } from '../utils';

describe('useGlobalData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('should initialize with empty data and default filters', () => {
      const { result } = renderHook(() => useGlobalData('2024-01-15'));
      
      expect(result.current.allTasks).toEqual([]);
      expect(result.current.allRuns).toEqual([]);
      expect(result.current.taskFilter).toEqual({
        status: '',
        date: '',
        pipeline: '',
        taskName: '',
      });
      expect(result.current.runFilter).toEqual({
        status: '',
        pipeline: '',
      });
    });
  });

  describe('loadAllTasks', () => {
    it('should fetch tasks without filters', async () => {
      const mockTasks = [
        { task_name: 'extract', status: 'success' },
        { task_name: 'transform', status: 'running' },
      ];
      api.get.mockResolvedValue({ tasks: mockTasks });
      
      const { result } = renderHook(() => useGlobalData('2024-01-15'));
      
      await act(async () => {
        await result.current.loadAllTasks();
      });
      
      expect(api.get).toHaveBeenCalledWith('/tasks?');
      expect(result.current.allTasks).toEqual(mockTasks);
    });

    it('should apply status filter to API request', async () => {
      api.get.mockResolvedValue({ tasks: [] });
      
      const { result } = renderHook(() => useGlobalData('2024-01-15'));
      
      act(() => {
        result.current.setTaskFilter(prev => ({ ...prev, status: 'failed' }));
      });
      
      await act(async () => {
        await result.current.loadAllTasks();
      });
      
      expect(api.get).toHaveBeenCalledWith('/tasks?status=failed');
    });

    it('should apply multiple filters to API request', async () => {
      api.get.mockResolvedValue({ tasks: [] });
      
      const { result } = renderHook(() => useGlobalData('2024-01-15'));
      
      act(() => {
        result.current.setTaskFilter({
          status: 'running',
          date: '2024-01-15',
          pipeline: 'my-pipeline',
          taskName: '',
        });
      });
      
      await act(async () => {
        await result.current.loadAllTasks();
      });
      
      expect(api.get).toHaveBeenCalledWith(
        '/tasks?status=running&date=2024-01-15&pipeline=my-pipeline'
      );
    });

    it('should filter by task name client-side', async () => {
      const mockTasks = [
        { task_name: 'extract_data', status: 'success' },
        { task_name: 'transform_data', status: 'success' },
        { task_name: 'load_data', status: 'success' },
      ];
      api.get.mockResolvedValue({ tasks: mockTasks });
      
      const { result } = renderHook(() => useGlobalData('2024-01-15'));
      
      act(() => {
        result.current.setTaskFilter(prev => ({ ...prev, taskName: 'extract' }));
      });
      
      await act(async () => {
        await result.current.loadAllTasks();
      });
      
      expect(result.current.allTasks).toEqual([
        { task_name: 'extract_data', status: 'success' },
      ]);
    });

    it('should handle case-insensitive task name filtering', async () => {
      const mockTasks = [
        { task_name: 'EXTRACT_DATA', status: 'success' },
        { task_name: 'Transform_Data', status: 'success' },
      ];
      api.get.mockResolvedValue({ tasks: mockTasks });
      
      const { result } = renderHook(() => useGlobalData('2024-01-15'));
      
      act(() => {
        result.current.setTaskFilter(prev => ({ ...prev, taskName: 'extract' }));
      });
      
      await act(async () => {
        await result.current.loadAllTasks();
      });
      
      expect(result.current.allTasks).toEqual([
        { task_name: 'EXTRACT_DATA', status: 'success' },
      ]);
    });

    it('should handle API error gracefully', async () => {
      api.get.mockResolvedValue({ error: 'Network error' });
      
      const { result } = renderHook(() => useGlobalData('2024-01-15'));
      
      await act(async () => {
        await result.current.loadAllTasks();
      });
      
      expect(result.current.allTasks).toEqual([]);
    });
  });

  describe('loadAllRuns', () => {
    it('should fetch runs with date parameter', async () => {
      const mockRuns = [
        { execution_id: 'exec-1', status: 'running' },
        { execution_id: 'exec-2', status: 'success' },
      ];
      api.get.mockResolvedValue({ runs: mockRuns });
      
      const { result } = renderHook(() => useGlobalData('2024-01-15'));
      
      await act(async () => {
        await result.current.loadAllRuns();
      });
      
      expect(api.get).toHaveBeenCalledWith('/runs?date=2024-01-15');
      expect(result.current.allRuns).toEqual(mockRuns);
    });

    it('should apply run filters to API request', async () => {
      api.get.mockResolvedValue({ runs: [] });
      
      const { result } = renderHook(() => useGlobalData('2024-01-15'));
      
      act(() => {
        result.current.setRunFilter({
          status: 'failed',
          pipeline: 'data-pipeline',
        });
      });
      
      await act(async () => {
        await result.current.loadAllRuns();
      });
      
      expect(api.get).toHaveBeenCalledWith(
        '/runs?date=2024-01-15&status=failed&pipeline=data-pipeline'
      );
    });

    it('should handle API error gracefully', async () => {
      api.get.mockResolvedValue({ error: 'Server error' });
      
      const { result } = renderHook(() => useGlobalData('2024-01-15'));
      
      await act(async () => {
        await result.current.loadAllRuns();
      });
      
      expect(result.current.allRuns).toEqual([]);
    });
  });

  describe('filter updates', () => {
    it('should update task filter state', () => {
      const { result } = renderHook(() => useGlobalData('2024-01-15'));
      
      act(() => {
        result.current.setTaskFilter({ 
          status: 'running', 
          date: '2024-01-15',
          pipeline: '',
          taskName: ''
        });
      });
      
      expect(result.current.taskFilter.status).toBe('running');
      expect(result.current.taskFilter.date).toBe('2024-01-15');
    });

    it('should update run filter state', () => {
      const { result } = renderHook(() => useGlobalData('2024-01-15'));
      
      act(() => {
        result.current.setRunFilter({ status: 'success', pipeline: 'etl' });
      });
      
      expect(result.current.runFilter.status).toBe('success');
      expect(result.current.runFilter.pipeline).toBe('etl');
    });
  });

  describe('date parameter handling', () => {
    it('should use date from hook parameter for runs', async () => {
      api.get.mockResolvedValue({ runs: [] });
      
      const { result, rerender } = renderHook(
        ({ date }) => useGlobalData(date),
        { initialProps: { date: '2024-01-15' } }
      );
      
      await act(async () => {
        await result.current.loadAllRuns();
      });
      
      expect(api.get).toHaveBeenCalledWith('/runs?date=2024-01-15');
      
      rerender({ date: '2024-01-20' });
      
      await act(async () => {
        await result.current.loadAllRuns();
      });
      
      expect(api.get).toHaveBeenLastCalledWith('/runs?date=2024-01-20');
    });
  });
});
