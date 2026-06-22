import React from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Button } from '@/components/ui/button';
import Notifications from './Notifications';
import { UserMenu } from './UserMenu';
import { toDateString, viewFromPathname } from '../utils';
import { useAppStore } from '../stores/useAppStore';
import { useShallow } from 'zustand/react/shallow';
import { useBackfillsListQuery } from '../hooks/queries';
import type { ViewTabProps } from '@/types';
import { 
    Workflow, 
    Package, 
    ListTodo, 
    Activity, 
    RefreshCw, 
    Pause, 
    HelpCircle,
    Sun,
    Moon,
    Zap,
    ChevronRight,
    Menu,
    X
} from 'lucide-react';
import { ActionIcons } from '@/utils/icons';

interface HeaderProps {
    apiConnected: boolean;
    onNotificationNavigate: (pipelineName: string, executionId?: string) => void;
    /** ADR #68 — navigate to backfill detail from backfill notification. */
    onNotificationNavigateBackfill?: (backfillId: string) => void;
}

/**
 * Header - Main application header with navigation and controls.
 * Reads top-level view from pathname (Next file-system routes); other state
 * from Zustand store.
 */
export function Header({ apiConnected, onNotificationNavigate, onNotificationNavigateBackfill }: HeaderProps) {
    const router = useRouter();
    const pathname = usePathname();
    const mainView = viewFromPathname(pathname);

    const {
        date, setDate,
        liveMode, toggleLiveMode,
        theme, toggleTheme,
        sidebarOpen, toggleSidebar,
        setShowHelpModal,
    } = useAppStore(useShallow(s => ({
        date: s.date, setDate: s.setDate,
        liveMode: s.liveMode, toggleLiveMode: s.toggleLiveMode,
        theme: s.theme, toggleTheme: s.toggleTheme,
        sidebarOpen: s.sidebarOpen, toggleSidebar: s.toggleSidebar,
        setShowHelpModal: s.setShowHelpModal,
    })));

    const switchView = (view: string) => router.push(`/${view}/`);

    // Active backfill count for the nav badge. Polls every 5s (handled by
    // useBackfillsListQuery's refetchInterval for 'active' filter). Falls
    // back to 0 silently on error — header should never crash on query.
    const activeBackfillsQuery = useBackfillsListQuery('active');
    const activeBackfillCount = activeBackfillsQuery.data?.length ?? 0;

    return (
        <header className="header" role="banner">
            {/* Mobile hamburger */}
            {(mainView === 'pipelines' || mainView === 'assets') && (
                <button className="hdr-hamburger-btn" onClick={toggleSidebar} title="Toggle sidebar" aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'} aria-expanded={sidebarOpen}>
                    {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
                </button>
            )}

            {/* Logo */}
            <div className="hdr-logo">
                <div className="hdr-logo-icon"><Zap size={20} /></div>
                slsflow Console
            </div>

            {/* Breadcrumbs */}
            <Breadcrumbs />

            {/* View Switcher */}
            <nav className="nav-pills ml-lg" aria-label="Main navigation">
                <ViewTab
                    active={mainView === 'pipelines'}
                    onClick={() => switchView('pipelines')}
                    icon={<Workflow size={16} />}
                    label="Pipelines"
                />
                <ViewTab
                    active={mainView === 'assets'}
                    onClick={() => switchView('assets')}
                    icon={<Package size={16} />}
                    label="Assets"
                />
                <ViewTab
                    active={mainView === 'tasks'}
                    onClick={() => switchView('tasks')}
                    icon={<ListTodo size={16} />}
                    label="All Tasks"
                />
                <ViewTab
                    active={mainView === 'runs'}
                    onClick={() => switchView('runs')}
                    icon={<Activity size={16} />}
                    label="All Runs"
                />
                <ViewTab
                    active={mainView === 'backfills'}
                    onClick={() => switchView('backfills')}
                    icon={<ActionIcons.backfill size={16} />}
                    label="Backfills"
                    badge={activeBackfillCount}
                />
            </nav>

            {/* Header Controls */}
            <div className="hdr-header-controls">
                {/* Date Picker */}
                {(mainView === 'pipelines' || mainView === 'runs' || mainView === 'assets') && (
                    <div className="hdr-date-picker">
                        <input
                            type="date"
                            value={date}
                            onChange={(e) => setDate(e.target.value)}
                            aria-label="Select date"
                        />
                        <Button onClick={() => setDate(toDateString(new Date()))}>
                            Today
                        </Button>
                    </div>
                )}

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
                    {liveMode ? <><RefreshCw size={14} className="animate-spin" /> Auto</> : <><Pause size={14} /> Paused</>}
                </div>

                {/* Notifications */}
                <Notifications onNavigate={onNotificationNavigate} onNavigateBackfill={onNotificationNavigateBackfill} />

                {/* Help Button */}
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setShowHelpModal(true)}
                    aria-label="Help and documentation"
                    title="Help & Documentation"
                >
                    <HelpCircle size={18} />
                </Button>

                {/* Theme Toggle */}
                <button
                    className="hdr-theme-toggle"
                    onClick={toggleTheme}
                    aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
                    title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
                >
                    {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
                </button>
                
                {/* User Menu */}
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
            <span className="hdr-breadcrumb-item clickable" onClick={onHomeClick} role="link" tabIndex={0} onKeyDown={e => { if (e.key === 'Enter') onHomeClick(); }}>
                Home
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

/**
 * ViewTab - Single tab in the view switcher
 */
function ViewTab({ active, onClick, icon, label, badge }: ViewTabProps) {
    return (
        <div
            className={`nav-pill nav-pill--md ${active ? 'active' : ''}`}
            onClick={onClick}
            title={label}
            role="tab"
            tabIndex={0}
            aria-selected={active}
            aria-label={badge ? `${label} (${badge} active)` : label}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } }}
        >
            {icon} <span className="hdr-nav-pill-label">{label}</span>
            {badge && badge > 0 ? (
                <span className="nav-pill-badge" aria-hidden="true">{badge}</span>
            ) : null}
        </div>
    );
}

export default Header;
