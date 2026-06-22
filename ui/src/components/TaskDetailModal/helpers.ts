/**
 * TaskDetailModal helpers — trigger rule evaluation and status constants
 */

export const TERMINAL_STATUSES = ['success', 'succeeded', 'failed', 'skipped', 'upstream_failed', 'stopped', 'aborted'];

export function evaluateDepStatus(depStatus: string, triggerRule: string) {
    const isTerminal = TERMINAL_STATUSES.includes(depStatus);
    const isSuccess = depStatus === 'success' || depStatus === 'succeeded';
    const isFailed = depStatus === 'failed' || depStatus === 'upstream_failed';
    const isSkipped = depStatus === 'skipped';
    
    switch (triggerRule) {
        case 'all_success': return isSuccess ? 'ok' : isTerminal ? 'blocked' : 'waiting';
        case 'all_failed': return isFailed ? 'ok' : isTerminal ? 'blocked' : 'waiting';
        case 'all_done': return isTerminal ? 'ok' : 'waiting';
        case 'one_success': return isSuccess ? 'ok' : isTerminal ? 'neutral' : 'waiting';
        case 'one_failed': return isFailed ? 'ok' : isTerminal ? 'neutral' : 'waiting';
        case 'none_failed': return isFailed ? 'blocked' : isTerminal ? 'ok' : 'waiting';
        case 'none_skipped': return isSkipped ? 'blocked' : isTerminal ? 'ok' : 'waiting';
        case 'none_failed_min_one_success': return isFailed ? 'blocked' : isSuccess ? 'ok' : isTerminal ? 'neutral' : 'waiting';
        case 'all_skipped': return isSkipped ? 'ok' : isTerminal ? 'blocked' : 'waiting';
        case 'always': return 'ok';
        default: return isSuccess ? 'ok' : isTerminal ? 'blocked' : 'waiting';
    }
}

export function getTriggerRuleExplanation(triggerRule: string) {
    const explanations: Record<string, string> = {
        'all_success': 'All dependencies must succeed',
        'all_failed': 'All dependencies must fail',
        'all_done': 'All dependencies must complete (any status)',
        'one_success': 'At least one dependency must succeed',
        'one_failed': 'At least one dependency must fail',
        'none_failed': 'No dependency can fail',
        'none_skipped': 'No dependency can be skipped',
        'none_failed_min_one_success': 'None failed + at least one success',
        'all_skipped': 'All dependencies must be skipped',
        'always': 'Runs regardless of dependency status',
    };
    return explanations[triggerRule] || `Rule: ${triggerRule}`;
}
