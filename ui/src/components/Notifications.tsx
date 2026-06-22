import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNotificationsQuery } from '@/hooks/queries';
import { Bell, Check, Siren, AlertTriangle, ArrowRight, X, ActionIcons } from '@/utils/icons';
import { MS } from '@/utils/constants';
import { logger } from '@/utils/logger';
import { asStringArray } from '@/utils/formatters';
import type { Notification as NotificationType } from '@/types';

/**
 * Notifications component - shows toast notifications for pipeline failures
 * Features:
 * - Bell icon with badge showing notification count
 * - Dropdown panel to view all notifications
 * - Browser notifications when permission is granted
 * - Toast-style notifications that appear automatically
 * 
 * Data fetching via React Query (useNotificationsQuery) — polls every 30s
 */
function getInitialShownNotifs(): Set<string> {
    try {
        const saved = localStorage.getItem('slsflow-shown-browser-notifs');
        if (saved) {
            const { ids, timestamp } = JSON.parse(saved);
            if (Date.now() - timestamp < 4 * MS.HOUR) {
                return new Set(asStringArray(ids));
            }
        }
    } catch {
        // localStorage may be unavailable
    }
    return new Set<string>();
}

interface NotificationsProps {
    onNavigate: (pipelineName: string, execution?: string) => void;
    /** ADR #68 — navigate to backfill detail when a backfill notification is clicked. */
    onNavigateBackfill?: (backfillId: string) => void;
}

function Notifications({ onNavigate, onNavigateBackfill }: NotificationsProps) {
    const [dismissed, setDismissed] = useState<Set<string>>(() => {
        try {
            const saved = localStorage.getItem('slsflow-dismissed-notifications');
            return saved ? new Set(asStringArray(JSON.parse(saved))) : new Set();
        } catch {
            return new Set();
        }
    });
    const shownBrowserNotifsRef = useRef<Set<string>>(getInitialShownNotifs());
    const [permissionGranted, setPermissionGranted] = useState(
        () => typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted'
    );
    const [showDropdown, setShowDropdown] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);
    
    // Fetch notifications via React Query (polls every 30s)
    const { data: allNotifications = [] } = useNotificationsQuery(10, 4);
    
    // Filter out dismissed notifications for UI display
    const notifications: NotificationType[] = allNotifications.filter(
        (n: NotificationType) => !dismissed.has(n.id)
    );
    
    // Save dismissed to localStorage
    useEffect(() => {
        try {
            localStorage.setItem('slsflow-dismissed-notifications', JSON.stringify([...dismissed]));
        } catch {
            // localStorage may be unavailable
        }
    }, [dismissed]);
    
    // (shownBrowserNotifs persisted inline when updated)
    
    // Request browser notification permission on mount
    useEffect(() => {
        if ('Notification' in window && Notification.permission !== 'granted' && Notification.permission !== 'denied') {
            Notification.requestPermission().then(permission => {
                setPermissionGranted(permission === 'granted');
            });
        }
    }, []);
    
    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setShowDropdown(false);
            }
        };
        
        document.addEventListener('mousedown', handleClickOutside as EventListener);
        return () => document.removeEventListener('mousedown', handleClickOutside as EventListener);
    }, []);
    
    // Show browser notifications for unseen failures
    useEffect(() => {
        if (!permissionGranted || allNotifications.length === 0) return;
        
        const shownBrowserNotifs = shownBrowserNotifsRef.current;
        const unseenNotifs = allNotifications.filter(
            (n: NotificationType) => !shownBrowserNotifs.has(n.id)
        );
        
        if (unseenNotifs.length === 0) return;
        
        unseenNotifs.forEach((n: NotificationType) => {
            try {
                new Notification('Pipeline Failed', {
                    body: `${n.pipeline_name} • ${n.task_name}`,
                    icon: '/favicon.ico',
                    tag: n.id
                });
                shownBrowserNotifs.add(n.id);
            } catch (e: unknown) {
                logger.warn('notifications', 'Failed to show browser notification', e);
            }
        });
        
        // Persist to localStorage
        try {
            localStorage.setItem('slsflow-shown-browser-notifs', JSON.stringify({
                ids: [...shownBrowserNotifs],
                timestamp: Date.now()
            }));
        } catch {
            // localStorage may be unavailable
        }
    }, [allNotifications, permissionGranted]);
    
    // Dismiss a notification
    const dismissNotification = useCallback((id: string | number) => {
        setDismissed(prev => new Set([...prev, String(id)]));
    }, []);
    
    // Dismiss all notifications
    const dismissAll = useCallback(() => {
        const allIds = notifications.map(n => n.id);
        setDismissed(prev => new Set([...prev, ...allIds]));
        setShowDropdown(false);
    }, [notifications]);
    
    // Handle "View" click - navigate to the failed pipeline
    const handleView = useCallback((notification: NotificationType) => {
        // ADR #68 — backfill notifications navigate to backfill detail.
        if (notification.type === 'backfill' && notification.backfill_id && onNavigateBackfill) {
            onNavigateBackfill(notification.backfill_id);
            dismissNotification(notification.id);
            setShowDropdown(false);
            return;
        }
        if (onNavigate) {
            onNavigate(notification.pipeline_name ?? '', notification.pipeline_execution);
        }
        dismissNotification(notification.id);
        setShowDropdown(false);
    }, [onNavigate, onNavigateBackfill, dismissNotification]);
    
    const notificationCount = notifications.length;
    
    return (
        <>
            {/* Bell Icon in Header */}
            <div className="ntf-notification-bell-container" ref={dropdownRef}>
                <button 
                    className={`ntf-notification-bell ${notificationCount > 0 ? 'has-notifications' : ''}`}
                    onClick={() => setShowDropdown(!showDropdown)}
                    aria-label={notificationCount > 0 ? `${notificationCount} notifications` : 'No notifications'}
                    aria-expanded={showDropdown}
                    aria-haspopup="true"
                    title={notificationCount > 0 ? `${notificationCount} notifications` : 'No notifications'}
                >
                    <Bell size={18} />
                    {notificationCount > 0 && (
                        <span className="ntf-notification-badge">{notificationCount > 9 ? '9+' : notificationCount}</span>
                    )}
                </button>
                
                {/* Dropdown Panel */}
                {showDropdown && (
                    <div className="ntf-notification-dropdown">
                        <div className="ntf-notification-dropdown-header">
                            <span className="ntf-notification-dropdown-title">Notifications</span>
                            {notificationCount > 0 && (
                                <button 
                                    className="ntf-notification-clear-all"
                                    onClick={dismissAll}
                                >
                                    Clear All
                                </button>
                            )}
                        </div>
                        <div className="ntf-notification-dropdown-content">
                            {notifications.length === 0 ? (
                                <div className="ntf-notification-empty">
                                    <span className="ntf-notification-empty-icon">
                                        <Check size={18} className="text-green-500" />
                                    </span>
                                    <span>No new notifications</span>
                                </div>
                            ) : (
                                notifications.map(notification => (
                                    <div 
                                        key={notification.id} 
                                        className={`ntf-notification-item ${notification.type}`}
                                    >
                                        <div className="ntf-notification-item-icon">
                                            {notification.type === 'backfill'
                                                ? <ActionIcons.backfill size={16} className={
                                                    notification.backfill_status === 'completed' ? 'text-green-500'
                                                    : notification.backfill_status === 'failed' ? 'text-red-500'
                                                    : notification.backfill_status === 'partial' ? 'text-amber-500'
                                                    : 'text-slate-400'
                                                } />
                                                : notification.type === 'failure'
                                                ? <Siren size={16} className="text-red-500" />
                                                : <AlertTriangle size={16} className="text-amber-500" />
                                            }
                                        </div>
                                        <div className="ntf-notification-item-content">
                                            <div className="ntf-notification-item-title">
                                                {notification.type === 'backfill'
                                                    ? `Backfill ${notification.backfill_status}: ${notification.target_pipeline}`
                                                    : notification.pipeline_name}
                                            </div>
                                            <div className="ntf-notification-item-subtitle">
                                                {notification.type === 'backfill'
                                                    ? `${notification.completed_partitions}/${notification.total_partitions} partitions • ${notification.time_ago}`
                                                    : `${notification.task_name} • ${notification.time_ago}`}
                                            </div>
                                        </div>
                                        <div className="ntf-notification-item-actions">
                                            <button 
                                                className="ntf-notification-item-btn"
                                                onClick={() => handleView(notification)}
                                                title="View"
                                                aria-label={
                                                    notification.type === 'backfill'
                                                        ? `View backfill ${notification.backfill_id}`
                                                        : `View ${notification.pipeline_name} failure`
                                                }
                                            >
                                                <ArrowRight size={14} />
                                            </button>
                                            <button 
                                                className="ntf-notification-item-btn ntf-dismiss"
                                                onClick={() => dismissNotification(notification.id)}
                                                title="Dismiss"
                                                aria-label="Dismiss notification"
                                            >
                                                <X size={14} />
                                            </button>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                )}
            </div>
            
            {/* Toast Notifications (floating) */}
            {notifications.length > 0 && !showDropdown && (
                <div className="ntf-notifications-container" role="log" aria-live="polite" aria-label="Pipeline failure notifications">
                    {notifications.slice(0, 3).map(notification => (
                        <div 
                            key={notification.id} 
                            className={`ntf-notification-toast ${notification.type}`}
                        >
                            <span className="ntf-notification-icon">
                                {notification.type === 'backfill'
                                    ? <ActionIcons.backfill size={18} className={
                                        notification.backfill_status === 'completed' ? 'text-green-500'
                                        : notification.backfill_status === 'failed' ? 'text-red-500'
                                        : notification.backfill_status === 'partial' ? 'text-amber-500'
                                        : 'text-slate-400'
                                    } />
                                    : notification.type === 'failure'
                                    ? <Siren size={18} className="text-red-500" />
                                    : <AlertTriangle size={18} className="text-amber-500" />
                                }
                            </span>
                            <div className="ntf-notification-content">
                                <div className="ntf-notification-title">
                                    {notification.type === 'backfill'
                                        ? `Backfill ${notification.backfill_status}`
                                        : 'Pipeline Failed'}
                                </div>
                                <div className="ntf-notification-subtitle">
                                    {notification.type === 'backfill'
                                        ? `${notification.target_pipeline} • ${notification.completed_partitions}/${notification.total_partitions} • ${notification.time_ago}`
                                        : `${notification.pipeline_name} • ${notification.time_ago}`}
                                </div>
                                <div className="ntf-notification-actions">
                                    <button 
                                        className="ntf-notification-btn primary"
                                        onClick={() => handleView(notification)}
                                    >
                                        View
                                    </button>
                                    <button 
                                        className="ntf-notification-btn secondary"
                                        onClick={() => dismissNotification(notification.id)}
                                    >
                                        Dismiss
                                    </button>
                                </div>
                            </div>
                            <button 
                                className="ntf-notification-close"
                                onClick={() => dismissNotification(notification.id)}
                                title="Dismiss"
                                aria-label="Dismiss notification"
                            >
                                <X size={14} />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </>
    );
}

export default Notifications;
