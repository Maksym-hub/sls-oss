import React from 'react';
import { Button } from '@/components/ui/button';

interface EeFeatureFallbackProps {
    feature: string;
    onHome?: () => void;
}

/** Placeholder shown when a Team-tier view is not present in this edition (ADR #99). */
export function EeFeatureFallback({ feature, onHome }: EeFeatureFallbackProps) {
    return (
        <div className="error-fallback" role="status">
            <p>{feature} is a Team-tier feature and isn’t available in this edition.</p>
            {onHome && (
                <Button size="sm" variant="secondary" onClick={onHome}>Go to Pipelines</Button>
            )}
        </div>
    );
}

export default EeFeatureFallback;
