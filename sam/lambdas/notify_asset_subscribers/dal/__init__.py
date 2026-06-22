"""
DAL for notify_asset_subscribers Lambda (v0.79.3, ADR #75).

Two repositories — one per table this Lambda touches:
  - SubscriptionsRepo (read + delete on asset-subscriptions table)
  - AssetEventsRepo (read on asset-events table)

Both use the same `boto3.resource('dynamodb')` instance under the hood,
created lazily by a shared `_resource()` helper.
"""
from __future__ import annotations

import os
import boto3
from typing import List, Dict, Optional


_dynamodb = None


def _resource():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource('dynamodb')
    return _dynamodb


class SubscriptionsRepo:
    """asset-subscriptions table: dependency_key + subscriber composite."""

    def __init__(self, table_name: Optional[str] = None):
        self._table_name = table_name or os.environ.get(
            'SUBSCRIPTIONS_TABLE', 'asset-subscriptions'
        )

    @property
    def table(self):
        return _resource().Table(self._table_name)

    def list_for_asset(self, asset_name: str, *, hard_cap: int = 10000) -> List[Dict]:
        """Return all subscribers for `asset:{asset_name}` (paginated)."""
        dependency_key = f'asset:{asset_name}'
        subscribers: List[Dict] = []
        last_key = None
        while True:
            kwargs = {
                'KeyConditionExpression': 'dependency_key = :dk',
                'ExpressionAttributeValues': {':dk': dependency_key},
            }
            if last_key:
                kwargs['ExclusiveStartKey'] = last_key
            response = self.table.query(**kwargs)
            subscribers.extend(response.get('Items', []))
            last_key = response.get('LastEvaluatedKey')
            if not last_key:
                break
            if len(subscribers) >= hard_cap:
                # Caller should log; we just stop pagination.
                break
        return subscribers

    def delete(self, asset_name: str, subscriber: str) -> None:
        """Delete a subscription after notify."""
        self.table.delete_item(Key={
            'dependency_key': f'asset:{asset_name}',
            'subscriber': subscriber,
        })


class AssetEventsRepo:
    """asset-events table: keyed by asset_name (PK)."""

    def __init__(self, table_name: Optional[str] = None):
        self._table_name = table_name or os.environ.get(
            'ASSET_EVENTS_TABLE', 'asset-events'
        )

    @property
    def table(self):
        return _resource().Table(self._table_name)

    def query_recent(self, asset_name: str, *, limit: int = 30) -> List[Dict]:
        """Return recent events for an asset (newest first)."""
        response = self.table.query(
            KeyConditionExpression='asset_name = :name',
            ExpressionAttributeValues={':name': asset_name},
            ScanIndexForward=False,
            Limit=limit,
        )
        return response.get('Items', [])


# Module singletons
subscriptions_repo = SubscriptionsRepo()
asset_events_repo = AssetEventsRepo()
