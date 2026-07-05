import React from 'react';
import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/EmptyState';

interface ComingSoonProps {
    /** Human label of the feature, e.g. "Asset console". */
    feature: string;
    onHome?: () => void;
}

/**
 * Placeholder for a feature that isn't built into this release yet but is on the
 * roadmap (e.g. the asset console graduating into open-core — ADR #105). The copy
 * is deliberately tier-agnostic ("coming in an upcoming release", not "to
 * open-core") so the same notice is reusable in both free and paid builds.
 *
 * Distinct from {@link EeFeatureFallback}, which marks a feature as gated to a
 * paid tier ("not available in this edition") rather than simply not-yet-shipped.
 */
export function ComingSoon({ feature, onHome }: ComingSoonProps) {
    return (
        <EmptyState
            icon={Sparkles}
            title={`${feature} is coming in an upcoming release.`}
            action={onHome && (
                <Button size="sm" variant="outline" onClick={onHome}>Go to Pipelines</Button>
            )}
        />
    );
}

export default ComingSoon;
