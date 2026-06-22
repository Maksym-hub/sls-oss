/**
 * SettingsModal — container for user/account settings, opened from UserMenu.
 *
 * Settings are organised into sections shown in a left sidebar. Today there is
 * one section (API Tokens); the SECTIONS array is the single place to register
 * more (appearance, notifications, …) — add an entry and it appears in the nav
 * with no other wiring. Each section renders its own self-contained component.
 */

import React, { useState } from 'react';
import { BaseModal, ModalHeader, ModalFooter } from './BaseModal';
import { paidSurface } from '@/ee-active.generated';
import { KeyRound, Settings } from 'lucide-react';

interface SettingsSection {
    id: string;
    label: string;
    icon: React.ReactNode;
    render: () => React.ReactNode;
}

// Team-tier sections come from the EE surface (absent in the OSS build, ADR #99).
// Register any free settings sections here directly; order = sidebar order.
const ApiTokensSection = paidSurface.ApiTokensSection;

const SECTIONS: SettingsSection[] = [
    ...(ApiTokensSection
        ? [{
              id: 'tokens',
              label: 'API Tokens',
              icon: <KeyRound size={16} />,
              render: () => <ApiTokensSection />,
          }]
        : []),
];

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
    const [activeId, setActiveId] = useState<string>(SECTIONS[0]?.id ?? '');
    const active = SECTIONS.find((s) => s.id === activeId) ?? SECTIONS[0];

    return (
        <BaseModal isOpen={isOpen} onClose={onClose} className="bm-settings-modal">
            <ModalHeader onClose={onClose} icon={<Settings size={20} />}>Settings</ModalHeader>

            <div className="settings-layout">
                <nav className="settings-nav" aria-label="Settings sections">
                    {SECTIONS.map((s) => (
                        <button
                            key={s.id}
                            type="button"
                            className={`settings-nav-item ${s.id === active?.id ? 'active' : ''}`.trim()}
                            onClick={() => setActiveId(s.id)}
                            aria-current={s.id === active?.id ? 'page' : undefined}
                        >
                            {s.icon}
                            {s.label}
                        </button>
                    ))}
                </nav>

                <div className="settings-content">
                    {active?.render()}
                </div>
            </div>

            <ModalFooter>
                <button type="button" className="action-btn" onClick={onClose}>Close</button>
            </ModalFooter>
        </BaseModal>
    );
}

export default SettingsModal;
