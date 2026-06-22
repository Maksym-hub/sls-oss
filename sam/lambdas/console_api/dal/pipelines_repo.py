"""
Data Access Layer: Pipeline Registry Table.

Encapsulates all DynamoDB operations for the pipeline-registry table
(PIPELINES_TABLE). Used by routes: pipelines, tasks, assets, backfill,
executions, health.

Table schema:
    PK: pipeline_name (str)
"""

from boto3.dynamodb.conditions import Key, Attr
from config import dynamodb, PIPELINES_TABLE
from utils import scan_all


class PipelinesRepo:
    """Repository for pipeline-registry table."""

    def __init__(self):
        self._table_name = PIPELINES_TABLE

    @property
    def table(self):
        return dynamodb.Table(self._table_name)

    # ── Single-item operations ────────────────────────────────────────────

    def get(self, pipeline_name: str) -> dict | None:
        """Get a single pipeline by name."""
        response = self.table.get_item(Key={'pipeline_name': pipeline_name})
        return response.get('Item')

    def put(self, item: dict) -> None:
        """Put a pipeline item."""
        self.table.put_item(Item=item)

    def update(self, pipeline_name: str, update_expr: str,
               expr_values: dict = None, expr_names: dict = None) -> dict:
        """Update a pipeline item."""
        params = {
            'Key': {'pipeline_name': pipeline_name},
            'UpdateExpression': update_expr,
        }
        if expr_values:
            params['ExpressionAttributeValues'] = expr_values
        if expr_names:
            params['ExpressionAttributeNames'] = expr_names
        return self.table.update_item(**params)

    # ── Scan operations ───────────────────────────────────────────────────

    def list_all(self, max_items: int = None, **kwargs) -> list:
        """Scan all pipelines with optional pagination."""
        if max_items:
            return scan_all(self.table, max_items=max_items, **kwargs)
        response = self.table.scan(**kwargs)
        return response.get('Items', [])

    def count(self) -> int:
        """Get total count of registered pipelines."""
        response = self.table.scan(Select='COUNT')
        return response.get('Count', 0)

    # ── Convenience helpers ───────────────────────────────────────────────

    def get_sfn_arn(self, pipeline_name: str) -> str | None:
        """Get the Step Functions ARN for a pipeline."""
        item = self.get(pipeline_name)
        if not item:
            return None
        return item.get('sfn_arn', '') or item.get('arn')


# Singleton instance
pipelines_repo = PipelinesRepo()
