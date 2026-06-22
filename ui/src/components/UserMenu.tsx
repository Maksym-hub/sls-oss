/**
 * UserMenu Component
 * 
 * Dropdown menu for authenticated users showing:
 * - User info (email, role)
 * - Sign out action
 * - Admin-only: User management link
 * 
 * @module components/UserMenu
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import type { UserMenuProps } from '@/types';
import { useAuth } from '@/hooks/useAuth';
import { 
    User, 
    LogOut, 
    ChevronDown,
    Shield,
    Users,
    Settings,
    Loader2
} from 'lucide-react';
import { SettingsModal } from './SettingsModal';

/**
 * Get user initials for avatar
 */
const getInitials = (name: string, email: string) => {
    if (name && name !== email) {
        return name
            .split(' ')
            .map((part: string) => part[0])
            .join('')
            .toUpperCase()
            .slice(0, 2);
    }
    return email?.charAt(0).toUpperCase() || 'U';
};

/**
 * UserMenu - User dropdown in header
 */
export function UserMenu({ onManageUsers }: UserMenuProps) {
    const { user, signOut, isAuthEnabled } = useAuth();
    const [isOpen, setIsOpen] = useState(false);
    const [isSigningOut, setIsSigningOut] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);
    
    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (e: Event) => {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
                setIsOpen(false);
            }
        };
        
        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isOpen]);
    
    // Close on escape
    useEffect(() => {
        const handleEscape = (e: Event) => {
            if ((e as KeyboardEvent).key === 'Escape') {
                setIsOpen(false);
            }
        };
        
        if (isOpen) {
            document.addEventListener('keydown', handleEscape);
        }
        
        return () => {
            document.removeEventListener('keydown', handleEscape);
        };
    }, [isOpen]);
    
    const handleSignOut = useCallback(async () => {
        setIsSigningOut(true);
        try {
            await signOut();
        } finally {
            setIsSigningOut(false);
            setIsOpen(false);
        }
    }, [signOut]);
    
    // Don't render if auth is disabled
    if (!isAuthEnabled) {
        return null;
    }
    
    if (!user) {
        return null;
    }
    
    const initials = getInitials(user.name || '', user.email || '');
    const displayName = user.name || user.email?.split('@')[0] || 'User';
    
    return (
        <div className="um-user-menu" ref={menuRef}>
            <button
                className="um-user-menu-trigger"
                onClick={() => setIsOpen(!isOpen)}
                aria-expanded={isOpen}
                aria-haspopup="true"
            >
                <div className="um-user-avatar">{initials}</div>
                <span className="um-user-name">{displayName}</span>
                <ChevronDown size={14} className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>
            
            {isOpen && (
                <div className="um-user-menu-dropdown" role="menu">
                    <div className="um-user-menu-header">
                        <div className="um-user-avatar um-user-avatar--lg">{initials}</div>
                        <div className="um-user-menu-identity">
                            <div className="um-user-menu-name">{displayName}</div>
                            <div className="um-user-menu-email">{user.email}</div>
                            <div className="um-user-menu-role">
                                {user.isAdmin ? (
                                    <>
                                        <Shield size={12} />
                                        Admin
                                    </>
                                ) : (
                                    <>
                                        <User size={12} />
                                        User
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                    
                    <div className="um-user-menu-content">
                        <button
                            className="um-user-menu-item"
                            onClick={() => {
                                setIsOpen(false);
                                setSettingsOpen(true);
                            }}
                            role="menuitem"
                        >
                            <Settings size={16} />
                            Settings
                        </button>
                        <div className="um-user-menu-divider" />

                        {user.isAdmin && onManageUsers && (
                            <>
                                <button
                                    className="um-user-menu-item"
                                    onClick={() => {
                                        setIsOpen(false);
                                        onManageUsers();
                                    }}
                                    role="menuitem"
                                >
                                    <Users size={16} />
                                    Manage Users
                                </button>
                                <div className="um-user-menu-divider" />
                            </>
                        )}
                        
                        <button
                            className="um-user-menu-item um-destructive"
                            onClick={handleSignOut}
                            disabled={isSigningOut}
                            role="menuitem"
                        >
                            {isSigningOut ? (
                                <>
                                    <Loader2 size={16} className="animate-spin" />
                                    Signing out...
                                </>
                            ) : (
                                <>
                                    <LogOut size={16} />
                                    Sign Out
                                </>
                            )}
                        </button>
                    </div>
                </div>
            )}

            <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
        </div>
    );
}


export default UserMenu;
