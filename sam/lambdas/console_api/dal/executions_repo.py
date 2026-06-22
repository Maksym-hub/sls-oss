"""
Data Access Layer: Pipeline Executions Table.

Encapsulates all DynamoDB operations for the pipeline-executions table
(TABLE_NAME / pipeline_tokens). Used by routes: executions, tasks, slack,
pipelines, health, notifications, backfill.

Table schema:
    PK: execution_name (str)
    GSIs: pipeline-execution-index (pipeline_execution), date-pipeline-index (date, pipeline_name)
"""

from boto3.dynamodb.conditions import Key, Attr
from config import dynamodb, TABLE_NAME
from utils import scan_all, query_all


class ExecutionsRepo:
    """Repository for pipeline-executions (tokens) table."""

    def __init__(self):
        self._table_name = TABLE_NAME

    @property
    def table(self):
        """Lazy table reference (new on every access for Lambda reuse safety)."""
        return dynamodb.Table(self._table_name)

    # ── Single-item operations ────────────────────────────────────────────

    def get(self, execution_name: str, consistent: bool = False) -> dict | None:
        """Get a single execution by execution_name."""
        kwargs = {'Key': {'execution_name': execution_name}}
        if consistent:
            kwargs['ConsistentRead'] = True
        response = self.table.get_item(**kwargs)
        return response.get('Item')

    def put(self, item: dict) -> None:
        """Put an execution item."""
        self.table.put_item(Item=item)

    def delete(self, execution_name: str) -> None:
        """Delete an execution by execution_name."""
        self.table.delete_item(Key={'execution_name': execution_name})

    def update(self, execution_name: str, update_expr: str,
               expr_values: dict = None, expr_names: dict = None,
               condition_expr: str = None) -> dict:
        """Generic update_item with optional condition expression.
        
        Returns the boto3 response dict.
        Raises ClientError on ConditionalCheckFailedException etc.
        """
        params = {
            'Key': {'execution_name': execution_name},
            'UpdateExpression': update_expr,
        }
        if expr_values:
            params['ExpressionAttributeValues'] = expr_values
        if expr_names:
            params['ExpressionAttributeNames'] = expr_names
        if condition_expr:
            params['ConditionExpression'] = condition_expr
        return self.table.update_item(**params)

    # ── GSI: pipeline-execution-index ─────────────────────────────────────

    def query_by_pipeline_execution(self, pipeline_execution: str,
                                     projection: str = None,
                                     expr_names: dict = None,
                                     limit: int = None) -> list:
        """Query pipeline-execution-index GSI. Returns all pages."""
        params = {
            'IndexName': 'pipeline-execution-index',
            'KeyConditionExpression': Key('pipeline_execution').eq(pipeline_execution),
        }
        if projection:
            params['ProjectionExpression'] = projection
        if expr_names:
            params['ExpressionAttributeNames'] = expr_names
        if limit:
            params['Limit'] = limit

        all_items = []
        last_key = None
        while True:
            if last_key:
                params['ExclusiveStartKey'] = last_key
            response = self.table.query(**params)
            all_items.extend(response.get('Items', []))
            last_key = response.get('LastEvaluatedKey')
            if not last_key:
                break
        return all_items

    # ── GSI: date-pipeline-index ──────────────────────────────────────────

    def query_by_date(self, date: str, max_items: int = None,
                      filter_expr=None, projection: str = None,
                      expr_names: dict = None, key_condition=None,
                      select: str = None) -> list:
        """Query date-pipeline-index GSI with optional filters.
        
        Uses query_all helper for automatic pagination.
        """
        params = {
            'IndexName': 'date-pipeline-index',
            'KeyConditionExpression': key_condition or Key('date').eq(date),
        }
        if filter_expr:
            params['FilterExpression'] = filter_expr
        if projection:
            params['ProjectionExpression'] = projection
        if expr_names:
            params['ExpressionAttributeNames'] = expr_names
        if select:
            params['Select'] = select

        if max_items:
            return query_all(self.table, max_items=max_items, **params)
        
        # Single-page query
        response = self.table.query(**params)
        return response.get('Items', [])

    def query_by_date_raw(self, **query_params) -> dict:
        """Raw query on date-pipeline-index, returns full boto3 response.
        
        For cases needing LastEvaluatedKey, Count, etc.
        """
        query_params.setdefault('IndexName', 'date-pipeline-index')
        return self.table.query(**query_params)

    # ── Scan operations ───────────────────────────────────────────────────

    def scan(self, max_items: int = None, **kwargs) -> list:
        """Scan with optional pagination via scan_all helper."""
        if max_items:
            return scan_all(self.table, max_items=max_items, **kwargs)
        response = self.table.scan(**kwargs)
        return response.get('Items', [])

    def scan_raw(self, **kwargs) -> dict:
        """Raw scan, returns full boto3 response."""
        return self.table.scan(**kwargs)

    # ── Health check ──────────────────────────────────────────────────────

    def health_ping(self) -> dict:
        """Lightweight read for health check."""
        return self.table.get_item(
            Key={'execution_name': '_health_check_'},
            ConsistentRead=True
        )

    # ── Conditional check exception ───────────────────────────────────────

    @property
    def conditional_check_exception(self):
        """Access the ConditionalCheckFailedException for try/except."""
        return dynamodb.meta.client.exceptions.ConditionalCheckFailedException


# Singleton instance
executions_repo = ExecutionsRepo()
