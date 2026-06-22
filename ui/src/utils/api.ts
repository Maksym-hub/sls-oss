import { logger } from './logger';
import { API } from './constants';
import { getApiUrl as getConfigApiUrl } from '../lib/config';
import config from '../lib/config';
import type { ApiResult } from '../types';

// API URL from config — lazy read from window.CONFIG every call
const getApiUrl = () => getConfigApiUrl();

/**
 * Wraps API response in Result type for cleaner error handling
 */
const wrapResult = <T = unknown>(data: T) => ({ ok: true as const, data });
const wrapError = (message: string, status?: number) => ({ ok: false as const, error: message, status });

/**
 * Parse error message from response
 */
const parseError = async (res: Response): Promise<string> => {
    try {
        const body = await res.json();
        return body.error || body.message || `HTTP ${res.status}`;
    } catch {
        return `HTTP ${res.status}`;
    }
};

/**
 * Retry helper with exponential backoff
 */
const withRetry = async <T>(fn: () => Promise<T>, retries = API.RETRY_COUNT): Promise<T> => {
    let lastError: unknown;
    for (let i = 0; i < retries; i++) {
        try {
            return await fn();
        } catch (e) {
            lastError = e;
            if (i < retries - 1) {
                await new Promise(r => setTimeout(r, Math.pow(2, i) * 100));
            }
        }
    }
    throw lastError;
};

// -----------------------------------------------------------------------------
// Auth Token Management
// -----------------------------------------------------------------------------

type AuthTokenGetter = () => Promise<string | null>;
type AuthErrorCallback = () => void;

let _getAuthToken: AuthTokenGetter | null = null;
let _onAuthError: AuthErrorCallback | null = null;

export const setAuthTokenGetter = (getter: AuthTokenGetter | null) => {
    _getAuthToken = getter;
};

export const setAuthErrorCallback = (callback: AuthErrorCallback | null) => {
    _onAuthError = callback;
};

const getAuthHeaders = async (): Promise<Record<string, string>> => {
    if (!config.AUTH?.enabled) {
        return {};
    }
    if (_getAuthToken) {
        try {
            const token = await _getAuthToken();
            if (token) {
                return { Authorization: `Bearer ${token}` };
            }
        } catch (e) {
            logger.warn('api', 'Failed to get auth token', e);
        }
    }
    return {};
};

const handleAuthError = (status: number) => {
    if (status === 401 && _onAuthError) {
        _onAuthError();
    }
};

// -----------------------------------------------------------------------------
// Base request method
// -----------------------------------------------------------------------------

interface RequestOptions {
    body?: unknown;
    timeout?: number;
    retry?: boolean;
}

const _request = async (method: string, path: string, options: RequestOptions = {}) => {
    const { body = null, timeout = API.TIMEOUT, retry = false } = options;

    const doFetch = async () => {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        try {
            const authHeaders = await getAuthHeaders();
            const headers: Record<string, string> = { ...authHeaders };
            
            if (body !== null) {
                headers['Content-Type'] = 'application/json';
            }

            const fetchOptions: RequestInit = {
                method,
                headers,
                signal: controller.signal,
            };
            if (body !== null) {
                fetchOptions.body = JSON.stringify(body);
            }

            const res = await fetch(`${getApiUrl()}${path}`, fetchOptions);
            clearTimeout(timeoutId);

            if (!res.ok) {
                handleAuthError(res.status);
                const errorMsg = await parseError(res);
                return wrapError(errorMsg, res.status);
            }

            const data = await res.json();
            return { ...wrapResult(data), ...data };
        } catch (e: unknown) {
            clearTimeout(timeoutId);
            if (e instanceof Error && e.name === 'AbortError') {
                return wrapError('Request timeout');
            }
            throw e;
        }
    };

    try {
        if (retry) {
            return await withRetry(doFetch);
        }
        return await doFetch();
    } catch (e: unknown) {
        logger.error('api', `${method} ${path} failed`, e);
        return { ok: false as const, error: e instanceof Error ? e.message : String(e) };
    }
};

// -----------------------------------------------------------------------------
// Public API
// -----------------------------------------------------------------------------

export const api = {
    get(path: string, options: RequestOptions = {}) {
        return _request('GET', path, options);
    },
    post(path: string, data?: unknown, options: RequestOptions = {}) {
        return _request('POST', path, { ...options, body: data });
    },
    put(path: string, data?: unknown, options: RequestOptions = {}) {
        return _request('PUT', path, { ...options, body: data });
    },
    delete(path: string, options: RequestOptions = {}) {
        return _request('DELETE', path, options);
    },
};

export const isOk = <T = unknown>(result: ApiResult<T>): result is { ok: true; data: T } => result.ok === true;

export const getData = <T = unknown>(result: ApiResult<T>, defaultValue: T | null = null): T | null => 
    result.ok ? result.data : defaultValue;
