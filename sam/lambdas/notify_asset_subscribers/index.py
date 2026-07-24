"""
Notify Asset Subscribers Lambda

Notifies tasks that are waiting for asset dependencies (wait_for).
Called after a task with outlets completes successfully.

Input:
{
    "outlets": [
        {"name": "inventory", "uri": "s3://..."}
    ],
    "source_task": "producer_task",
    "source_dag": "producer_pipeline",
    "event_time": "2026-01-26T08:00:00Z"
}

Output:
{
    "notified": 3,
    "assets": ["inventory"],
    "subscribers": ["task_a", "task_b", "task_c"]
}
"""

import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Any

# v0.79.3 (ADR #75) — DAL repository pattern for DynamoDB.
# Raw boto3 calls moved to dal/__init__.py.
from dal import subscriptions_repo, asset_events_repo
# v0.79.4 (ADR #76) — structured JSON logging.
from logger import log

# Lazy initialization for SFN client only (sfn calls stay inline — single
# operation, no scope advantage from a repo).
_sfn = None

def _get_sfn():
    global _sfn
    if _sfn is None:
        import boto3
        _sfn = boto3.client('stepfunctions')
    return _sfn


SUBSCRIPTIONS_TABLE = os.environ.get('SUBSCRIPTIONS_TABLE', 'dependency-subscriptions')
ASSET_EVENTS_TABLE = os.environ.get('ASSET_EVENTS_TABLE', 'asset-events')


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Main handler - notify asset subscribers."""
    
    outlets = event.get('outlets', [])
    event_time = event.get('event_time', '')
    
    if not outlets:
        return {
            'notified': 0,
            'assets': [],
            'subscribers': []
        }
    
    notified_count = 0
    notified_subscribers = []
    asset_names = []
    
    for outlet in outlets:
        asset_name = outlet.get('name', '')
        asset_uri = outlet.get('uri', '')
        
        if not asset_name:
            continue
        
        asset_names.append(asset_name)
        
        # Find and notify subscribers for this asset
        subscribers = _get_asset_subscribers(asset_name)
        
        for sub in subscribers:
            wait_token = sub.get('wait_token', '')
            subscriber_name = sub.get('subscriber', '')
            freshness_hours = sub.get('freshness_hours')
            subscription_type = sub.get('subscription_type', 'asset')
            
            if not wait_token:
                continue
            
            # Consecutive check: re-verify all dates before signaling
            if subscription_type == 'asset_consecutive':
                consecutive_days = int(sub.get('consecutive_days', 1))
                reference_date = sub.get('reference_date', '')
                if not _check_consecutive_ready(asset_name, consecutive_days, reference_date):
                    # Not all dates present yet - keep subscription, don't notify
                    continue
            
            # Check freshness if subscriber requires it
            elif freshness_hours:
                # Re-check freshness at notify time
                if not _check_freshness(asset_name, event_time, freshness_hours):
                    # Asset is stale for this subscriber - don't notify yet
                    continue
            
            # Send signal to waiting task
            success = _send_task_success(
                wait_token,
                asset_name=asset_name,
                asset_uri=asset_uri,
                event_time=event_time
            )
            
            if success:
                notified_count += 1
                notified_subscribers.append(subscriber_name)
                
                # Delete subscription after successful notify
                _delete_subscription(asset_name, subscriber_name)
    
    return {
        'notified': notified_count,
        'assets': asset_names,
        'subscribers': notified_subscribers
    }


def _get_asset_subscribers(asset_name: str) -> List[Dict]:
    """Get all subscribers waiting for this asset (with pagination)."""
    try:
        # v0.79.3 (ADR #75) — DAL handles query + pagination + 10000 cap.
        subs = subscriptions_repo.list_for_asset(asset_name)
        if len(subs) >= 10000:
            log.warn("_get_asset_subscribers", "Hit 10000 subscriber pagination cap", asset_name=asset_name)
        return subs
    except Exception as e:
        log.warn("_get_asset_subscribers", "Query failed", asset_name=asset_name, error=str(e))
        return []


def _check_freshness(asset_name: str, event_time: str, freshness_hours: float) -> bool:
    """Check if asset event meets freshness requirement."""
    try:
        if 'Z' in event_time:
            event_time = event_time.replace('Z', '+00:00')
        event_dt = datetime.fromisoformat(event_time)
        
        if event_dt.tzinfo is None:
            event_dt = event_dt.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        age_hours = (now - event_dt).total_seconds() / 3600
        
        return age_hours <= freshness_hours
    except Exception as e:
        # Preserve "default to fresh" behavior so downstream orchestration isn't
        # blocked by a single bad timestamp, but make the parse failure visible —
        # silent True can otherwise mask systematic timestamp issues for hours.
        log.warn("_check_freshness", "Parse failed; defaulting to fresh",
                 asset_name=asset_name,
                 event_time=event_time,
                 error_type=type(e).__name__,
                 error=str(e))
        return True  # Default to fresh if parsing fails


def _check_consecutive_ready(asset_name: str, consecutive_days: int, reference_date: str) -> bool:
    """
    Check if asset has events for N consecutive dates ending at reference_date.
    
    Used by notify to re-verify before sending signal to consecutive subscribers.
    Returns True only when ALL required dates have events.
    """
    from datetime import timedelta
    
    # Defensive: consecutive_days must be >= 1
    if consecutive_days < 1:
        return False
    
    if not reference_date:
        reference_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    try:
        ref_dt = datetime.strptime(reference_date, '%Y-%m-%d')
    except ValueError:
        return False
    
    # Build required dates set
    required_dates = set()
    for i in range(consecutive_days):
        dt = ref_dt - timedelta(days=i)
        required_dates.add(dt.strftime('%Y-%m-%d'))
    
    # Query recent events
    # v0.79.3 (ADR #75) — DAL handles the boto3 dance.
    try:
        items = asset_events_repo.query_recent(
            asset_name, limit=max(consecutive_days * 5, 30)
        )
    except Exception as e:
        log.warn("_check_consecutive", "Failed to query asset events", asset_name=asset_name, error=str(e))
        return False

    # Extract distinct execution_dates
    found_dates = set()
    for item in items:
        exec_date = item.get('execution_date', '')
        if exec_date:
            found_dates.add(exec_date)
    
    # Check if all required dates are present
    missing = required_dates - found_dates
    return len(missing) == 0


def _send_task_success(wait_token: str, asset_name: str, asset_uri: str, event_time: str) -> bool:
    """Send task success signal to waiting task."""
    sfn = _get_sfn()
    
    output = json.dumps({
        'signal': 'asset_ready',
        'asset_name': asset_name,
        'asset_uri': asset_uri,
        'event_time': event_time
    })
    
    try:
        sfn.send_task_success(
            taskToken=wait_token,
            output=output
        )
        return True
    except sfn.exceptions.TaskTimedOut:
        log.warn("_send_task_success", "Task token timed out", asset_name=asset_name)
        return False
    except sfn.exceptions.InvalidToken:
        log.warn("_send_task_success", "Invalid task token", asset_name=asset_name)
        return False
    except sfn.exceptions.TaskDoesNotExist:
        log.warn("_send_task_success", "Task does not exist", asset_name=asset_name)
        return False
    except Exception as e:
        log.warn("_send_task_success", "send_task_success failed", asset_name=asset_name, error=str(e))
        return False


def _delete_subscription(asset_name: str, subscriber: str):
    """Delete subscription after successful notify."""
    try:
        # v0.79.3 (ADR #75) — DAL owns the composite-key shape.
        subscriptions_repo.delete(asset_name, subscriber)
    except Exception as e:
        log.warn("_delete_subscription", "Delete failed", asset_name=asset_name, subscriber=subscriber, error=str(e))
