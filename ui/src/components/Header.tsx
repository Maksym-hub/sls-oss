import React from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Notifications from './Notifications';
import { UserMenu } from './UserMenu';
import { viewFromPathname } from '../utils';
import { useAppStore } from '../stores/useAppStore';
import { useShallow } from 'zustand/react/shallow';
import {
    RefreshCw,
    Zap,
    Pause,
    Sun,
    Moon,
    ChevronRight,
    Menu,
    X
} from 'lucide-react';

interface HeaderProps {
    apiConnected: boolean;
    onNotificationNavigate: (pipelineName: string, executionId?: string) => void;
    /** ADR #68 — navigate to backfill detail from backfill notification. */
    onNotificationNavigateBackfill?: (backfillId: string) => void;
}

/**
 * Header — the app-shell topbar: contextual breadcrumbs and global controls.
 *
 * Primary navigation lives in the left rail (AppNav); this topbar carries location
 * (breadcrumbs) and global controls (API status, auto-refresh, notifications, theme,
 * user menu). Top-level view is read from the pathname; other state from Zustand.
 */
export function Header({ apiConnected, onNotificationNavigate, onNotificationNavigateBackfill }: HeaderProps) {
    const pathname = usePathname();
    const mainView = viewFromPathname(pathname);

    const {
        liveMode, toggleLiveMode,
        theme, toggleTheme,
        sidebarOpen, toggleSidebar,
    } = useAppStore(useShallow(s => ({
        liveMode: s.liveMode, toggleLiveMode: s.toggleLiveMode,
        theme: s.theme, toggleTheme: s.toggleTheme,
        sidebarOpen: s.sidebarOpen, toggleSidebar: s.toggleSidebar,
    })));

    return (
        <header className="header" role="banner">
            {/* Mobile hamburger — only where a secondary sidebar exists */}
            {(mainView === 'pipelines' || mainView === 'assets') && (
                <button className="hdr-hamburger-btn" onClick={toggleSidebar} title="Toggle sidebar" aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'} aria-expanded={sidebarOpen}>
                    {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
                </button>
            )}

            {/* Breadcrumbs */}
            <Breadcrumbs />

            {/* Header Controls */}
            <div className="hdr-header-controls">
                {/* API Status */}
                <div
                    className="hdr-status-badge"
                    title={apiConnected ? 'API connected' : 'API disconnected'}
                    role="status"
                    aria-label={apiConnected ? 'API connected' : 'API disconnected'}
                >
                    <div className={`status-dot ${apiConnected ? 'connected' : 'disconnected'}`} />
                    API
                </div>

                {/* Live Mode Toggle */}
                <div
                    className={`hdr-status-badge cursor-pointer ${liveMode ? 'status-badge-active' : ''}`}
                    onClick={toggleLiveMode}
                    role="button"
                    tabIndex={0}
                    aria-label={liveMode ? 'Pause auto-refresh' : 'Enable auto-refresh'}
                    aria-pressed={liveMode}
                    onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleLiveMode(); } }}
                    title={liveMode ? 'Click to pause auto-refresh' : 'Click to enable auto-refresh'}
                >
                    {liveMode ? <><RefreshCw size={14} className="hdr-auto-spin" /> Auto</> : <><Pause size={14} /> Paused</>}
                </div>

                {/* Notifications */}
                <Notifications onNavigate={onNotificationNavigate} onNavigateBackfill={onNotificationNavigateBackfill} />

                {/* Theme Toggle */}
                <button
                    className="hdr-theme-toggle"
                    onClick={toggleTheme}
                    aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
                    title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
                >
                    {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
                </button>

                {/* User Menu (Settings and Help & documentation live inside this dropdown) */}
                <UserMenu />
            </div>
        </header>
    );
}

/**
 * Breadcrumbs — reads view from pathname, deep state from store.
 */
function Breadcrumbs() {
    const router = useRouter();
    const pathname = usePathname();
    const mainView = viewFromPathname(pathname);

    const { selectedPipeline, selectedExecution, setSelectedPipeline } = useAppStore(useShallow(s => ({
        selectedPipeline: s.selectedPipeline, selectedExecution: s.selectedExecution,
        setSelectedPipeline: s.setSelectedPipeline,
    })));

    const onHomeClick = () => {
        setSelectedPipeline(null);
        router.push('/pipelines/');
    };

    return (
        <nav className="hdr-breadcrumbs" aria-label="Breadcrumb">
            <span className="hdr-breadcrumb-item hdr-breadcrumb-home clickable" onClick={onHomeClick} role="link" tabIndex={0} aria-label="polyris — home" onKeyDown={e => { if (e.key === 'Enter') onHomeClick(); }}>
                <span className="hdr-breadcrumb-logo"><Zap size={16} /></span>
                polyris
            </span>

            {mainView === 'pipelines' && selectedPipeline && (
                <>
                    <span className="hdr-breadcrumb-sep"><ChevronRight size={14} /></span>
                    <span className="hdr-breadcrumb-item">{selectedPipeline.name}</span>
                </>
            )}

            {mainView === 'pipelines' && selectedPipeline && selectedExecution && (
                <>
                    <span className="hdr-breadcrumb-sep"><ChevronRight size={14} /></span>
                    <span className="hdr-breadcrumb-item">
                        {selectedExecution.execution_short || selectedExecution.execution_id?.substring(0, 8)}
                    </span>
                </>
            )}

            {mainView === 'assets' && (
                <>
                    <span className="hdr-breadcrumb-sep"><ChevronRight size={14} /></span>
                    <span className="hdr-breadcrumb-item">Assets</span>
                </>
            )}

            {mainView === 'tasks' && (
                <>
                    <span className="hdr-breadcrumb-sep"><ChevronRight size={14} /></span>
                    <span className="hdr-breadcrumb-item">All Tasks</span>
                </>
            )}

            {mainView === 'runs' && (
                <>
                    <span className="hdr-breadcrumb-sep"><ChevronRight size={14} /></span>
                    <span className="hdr-breadcrumb-item">All Runs</span>
                </>
            )}
        </nav>
    );
}

export default Header;
