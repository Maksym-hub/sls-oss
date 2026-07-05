'use client';

import React, { lazy, Suspense } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Loader2 } from './utils/icons';
import { 
    HelpModal,
    ErrorBoundary,
    CommandPalette,
    Header,
    PipelinesSidebar,
    PipelineDetail
} from './components';
import { ComingSoon } from '@/components/ComingSoon';
import { paidSurface } from '@/ee-active.generated';
import { useKeyboardShortcuts, SHORTCUTS } from './hooks';
import { usePipelinesQuery } from './hooks/queries';
import { useAppStore } from './stores/useAppStore';
import { useShallow } from 'zustand/react/shallow';
import { useStoreInit } from './stores/useStoreInit';
import { POLLING, viewFromPathname } from './utils';
import type { PipelineWithUI } from './types';
import { isMainView } from './types';

// Lazy load heavy components
const AllTasksView = lazy(() => import('./components/AllTasksView'));
const AllRunsView = lazy(() => import('./components/AllRunsView'));

const ViewLoader = () => (
    <div className="view-loader">
        <Loader2 size={32} className="animate-spin" />
        <span>Loading...</span>
    </div>
);

function App() {
    const router = useRouter();
    const pathname = usePathname();
    const mainView = viewFromPathname(pathname);
    const BackfillsView = paidSurface.BackfillsView;
    const AssetsView = paidSurface.AssetsView;
    const BackfillModalHost = paidSurface.BackfillModalHost;

    // ========== Store ==========
    const {
        setViewMode,
        setSelectedPipeline,
        theme, toggleTheme,
        liveMode,
        showHelpModal, setShowHelpModal,
        showCommandPalette, setShowCommandPalette,
        showTaskModal, setShowTaskModal,
        backfillModalSeed, closeBackfillModal,
    } = useAppStore(useShallow(s => ({
        setViewMode: s.setViewMode,
        setSelectedPipeline: s.setSelectedPipeline,
        theme: s.theme, toggleTheme: s.toggleTheme,
        liveMode: s.liveMode,
        showHelpModal: s.showHelpModal, setShowHelpModal: s.setShowHelpModal,
        showCommandPalette: s.showCommandPalette, setShowCommandPalette: s.setShowCommandPalette,
        showTaskModal: s.showTaskModal, setShowTaskModal: s.setShowTaskModal,
        backfillModalSeed: s.backfillModalSeed,
        closeBackfillModal: s.closeBackfillModal,
    })));

    // ========== Data ==========
    const { 
        data: pipelines = [], 
        error: pipelinesError,
    } = usePipelinesQuery({ refetchInterval: liveMode ? POLLING.IDLE : false });

    const apiConnected = !pipelinesError;
    const apiError = pipelinesError ? `Cannot connect to API: ${pipelinesError.message}` : null;

    // ========== Store Init (URL sync, pipeline restore, effects) ==========
    const { navigateToExecution } = useStoreInit({ pipelines });

    // ========== Keyboard Shortcuts ==========
    useKeyboardShortcuts({
        [SHORTCUTS.HELP]: () => setShowHelpModal(true),
        [SHORTCUTS.SEARCH]: () => setShowCommandPalette(!showCommandPalette),
        [SHORTCUTS.ESCAPE]: () => {
            if (showCommandPalette) setShowCommandPalette(false);
            else if (showTaskModal) setShowTaskModal(false);
            else if (showHelpModal) setShowHelpModal(false);
            else if (backfillModalSeed) closeBackfillModal();
        },
        [SHORTCUTS.TOGGLE_THEME]: toggleTheme,
        'g': () => mainView === 'pipelines' && setViewMode('gantt'),
        'd': () => mainView === 'pipelines' && setViewMode('dag'),
        'c': () => mainView === 'pipelines' && setViewMode('calendar'),
        '1': () => router.push('/pipelines/'),
        '2': () => router.push('/assets/'),
        '3': () => router.push('/tasks/'),
        '4': () => router.push('/runs/'),
        '5': () => router.push('/backfills/'),
    });

    // ========== Render ==========
    return (
        <div className="app">
            <a href="#main-content" className="skip-link">Skip to main content</a>
            
            {!apiConnected && (
                <div className="connection-banner" role="alert">
                    <span><AlertTriangle size={16} /> Connection lost. Retrying...</span>
                    <Button size="sm" variant="secondary" onClick={() => window.location.reload()}>Retry Now</Button>
                </div>
            )}
            
            <Header
                apiConnected={apiConnected}
                onNotificationNavigate={(name, execId) => navigateToExecution(name, execId)}
                onNotificationNavigateBackfill={(backfillId) => router.push(`/backfills/${backfillId}/`)}
            />
            
            <main className="main" id="main-content">
                {mainView === 'pipelines' ? (
                    <div className="main-top">
                        <PipelinesSidebar />
                        <PipelineDetail
                            apiError={apiError}
                            navigateToExecution={navigateToExecution}
                        />
                    </div>
                ) : mainView === 'tasks' ? (
                    <Suspense fallback={<ViewLoader />}>
                        <AllTasksView
                            onPipelineClick={(pipeline, taskDate) => {
                                navigateToExecution(pipeline.name, undefined, taskDate);
                            }}
                        />
                    </Suspense>
                ) : mainView === 'runs' ? (
                    <Suspense fallback={<ViewLoader />}>
                        <AllRunsView
                            onPipelineClick={(pipeline, run) => {
                                navigateToExecution(pipeline.name, run?.pipeline_execution, run?.date);
                            }}
                        />
                    </Suspense>
                ) : mainView === 'backfills' ? (
                    <Suspense fallback={<ViewLoader />}>
                        {BackfillsView
                            ? <BackfillsView />
                            : <ComingSoon feature="Backfills" onHome={() => router.push('/pipelines/')} />}
                    </Suspense>
                ) : mainView === 'assets' ? (
                    <ErrorBoundary fallback={
                        <div className="pd-error-fallback">
                            Failed to load Assets view. 
                            <button onClick={() => router.push('/pipelines/')}>Go to Pipelines</button>
                        </div>
                    }>
                        <Suspense fallback={<ViewLoader />}>
                            {AssetsView
                                ? <AssetsView />
                                : <ComingSoon feature="Asset console" onHome={() => router.push('/pipelines/')} />}
                        </Suspense>
                    </ErrorBoundary>
                ) : null}
            </main>
            
            <HelpModal isOpen={showHelpModal} onClose={() => setShowHelpModal(false)} />

            {BackfillModalHost && <BackfillModalHost />}
            
            <CommandPalette
                isOpen={showCommandPalette}
                onClose={() => setShowCommandPalette(false)}
                pipelines={pipelines}
                onSelectPipeline={(p: PipelineWithUI) => { setSelectedPipeline(p); router.push('/pipelines/'); }}
                onNavigate={(view: string) => {
                    if (view === 'help') { setShowHelpModal(true); return; }
                    if (isMainView(view)) router.push(`/${view}/`);
                }}
                onToggleTheme={toggleTheme}
                theme={theme}
            />
        </div>
    );
}

export { App };
export default App;
