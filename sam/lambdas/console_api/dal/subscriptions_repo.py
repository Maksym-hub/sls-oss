"""
Data Access Layer: Subscription Tables.

Encapsulates all DynamoDB operations for:
- dep-subscriptions (SUBSCRIPTIONS_TABLE)
- asset-subscriptions (ASSET_SUBSCRIPTIONS_TABLE)

Used by routes: executions, backfill.
"""

from boto3.dynamodb.conditions import Key
from config import dynamodb, SUBSCRIPTIONS_TABLE, ASSET_SUBSCRIPTIONS_TABLE


class DepSubscriptionsRepo:
    """Repository for dep-subscriptions table.
    
    Table schema: PK: dependency_key, SK: subscriber.
    """

    def __init__(self):
        self._table_name = SUBSCRIPTIONS_TABLE

    @property
    def table(self):
        return dynamodb.Table(self._table_name)

    def delete(self, dependency_key: str, subscriber: str) -> None:
        self.table.delete_item(Key={
            'dependency_key': dependency_key,
            'subscriber': subscriber
        })


class AssetSubscriptionsRepo:
    """Repository for asset-subscriptions table.
    
    Table schema: PK: asset_name, SK: pipeline_name.
    """

    def __init__(self):
        self._table_name = ASSET_SUBSCRIPTIONS_TABLE

    @property
    def table(self):
        return dynamodb.Table(self._table_name)

    def query_by_asset(self, asset_name: str) -> list:
        response = self.table.query(
            KeyConditionExpression=Key('asset_name').eq(asset_name)
        )
        return response.get('Items', [])


# Singleton instances
dep_subscriptions_repo = DepSubscriptionsRepo()
asset_subscriptions_repo = AssetSubscriptionsRepo()
