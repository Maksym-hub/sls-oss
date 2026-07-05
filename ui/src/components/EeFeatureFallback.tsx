import React from 'react';
import { Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/EmptyState';

interface EeFeatureFallbackProps {
    feature: string;
    onHome?: () => void;
}

/**
 * Placeholder shown when a paid Team-tier view is not present in this edition
 * (ADR #99). Unlike {@link ComingSoon} (not-yet-shipped, coming to everyone),
 * this signals a capability gated behind the paid tier.
 */
export function EeFeatureFallback({ feature, onHome }: EeFeatureFallbackProps) {
    return (
        <EmptyState
            icon={Lock}
            title={`${feature} isn’t available in this edition.`}
            description="This is a Team-tier feature."
            action={onHome && (
                <Button size="sm" variant="outline" onClick={onHome}>Go to Pipelines</Button>
            )}
        />
    );
}

export default EeFeatureFallback;
