"""
Tests for notify_asset_subscribers Lambda.

Tests subscriber notification and freshness re-checking.
"""

import pytest
from datetime import datetime, timezone, timedelta


@pytest.fixture(autouse=True)
def reset_globals(mocker):
    """Reset global clients for each test."""
    import index
    # v0.79.3 (ADR #75): _dynamodb global removed; DAL repos are
    # module singletons but tests patch their methods directly per test.
    mocker.patch.object(index, '_sfn', None)


class TestNotifyAssetSubscribers:
    """Test notify_asset_subscribers handler."""
    
    def test_empty_outlets_returns_zero(self):
        """Empty outlets should return notified=0."""
        from index import handler
        
        result = handler({'outlets': []}, None)
        
        assert result['notified'] == 0
        assert result['assets'] == []
        assert result['subscribers'] == []
    
    def test_no_subscribers_returns_zero(self, mocker):
        """No subscribers should return notified=0."""
        from index import handler
        
        mock_table = mocker.MagicMock()
        mock_table.query.return_value = {'Items': []}
        
        mock_dynamodb = mocker.MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        
        mocker.patch('index._get_dynamodb', return_value=mock_dynamodb, create=True)
        # v0.79.3 (ADR #75) — also wire mock_table into DAL repos
        # so calls via subscriptions_repo / asset_events_repo land
        # on the same mock the test set up.
        from index import subscriptions_repo, asset_events_repo
        mocker.patch.object(type(subscriptions_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_table)
        mocker.patch.object(type(asset_events_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_table)
        result = handler({
            'outlets': [{'name': 'inventory', 'uri': 's3://bucket/inv'}],
            'source_task': 'producer',
            'source_dag': 'pipeline',
            'event_time': datetime.now(timezone.utc).isoformat()
        }, None)
        
        assert result['notified'] == 0
        assert 'inventory' in result['assets']
    
    def test_notifies_subscribers(self, mocker):
        """Should notify waiting subscribers."""
        from index import handler
        
        mock_table = mocker.MagicMock()
        mock_table.query.return_value = {
            'Items': [
                {'subscriber': 'task_a', 'wait_token': 'token_a'},
                {'subscriber': 'task_b', 'wait_token': 'token_b'},
            ]
        }
        
        mock_dynamodb = mocker.MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        
        mock_sfn = mocker.MagicMock()
        
        mocker.patch('index._get_dynamodb', return_value=mock_dynamodb, create=True)
        # v0.79.3 (ADR #75) — also wire mock_table into DAL repos
        # so calls via subscriptions_repo / asset_events_repo land
        # on the same mock the test set up.
        from index import subscriptions_repo, asset_events_repo
        mocker.patch.object(type(subscriptions_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_table)
        mocker.patch.object(type(asset_events_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_table)
        mocker.patch('index._get_sfn', return_value=mock_sfn)
        result = handler({
            'outlets': [{'name': 'inventory', 'uri': 's3://bucket/inv'}],
            'source_task': 'producer',
            'source_dag': 'pipeline',
            'event_time': datetime.now(timezone.utc).isoformat()
        }, None)
        
        assert result['notified'] == 2
        assert 'task_a' in result['subscribers']
        assert 'task_b' in result['subscribers']
        assert mock_sfn.send_task_success.call_count == 2
        assert mock_table.delete_item.call_count == 2
    
    def test_handles_expired_token(self, mocker):
        """Should handle expired token gracefully."""
        from index import handler
        
        mock_table = mocker.MagicMock()
        mock_table.query.return_value = {
            'Items': [{'subscriber': 'task_a', 'wait_token': 'expired_token'}]
        }
        
        mock_dynamodb = mocker.MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        
        mock_sfn = mocker.MagicMock()
        mock_sfn.exceptions = mocker.MagicMock()
        mock_sfn.exceptions.TaskTimedOut = Exception
        mock_sfn.send_task_success.side_effect = mock_sfn.exceptions.TaskTimedOut()
        
        mocker.patch('index._get_dynamodb', return_value=mock_dynamodb, create=True)
        # v0.79.3 (ADR #75) — also wire mock_table into DAL repos
        # so calls via subscriptions_repo / asset_events_repo land
        # on the same mock the test set up.
        from index import subscriptions_repo, asset_events_repo
        mocker.patch.object(type(subscriptions_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_table)
        mocker.patch.object(type(asset_events_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_table)
        mocker.patch('index._get_sfn', return_value=mock_sfn)
        result = handler({
            'outlets': [{'name': 'inventory', 'uri': 's3://bucket/inv'}],
            'source_task': 'producer',
            'source_dag': 'pipeline',
            'event_time': datetime.now(timezone.utc).isoformat()
        }, None)
        
        assert result['notified'] == 0
    
    def test_skips_stale_for_freshness_subscriber(self, mocker):
        """Should skip notification if subscriber requires freshness and asset is stale."""
        from index import handler
        
        mock_table = mocker.MagicMock()
        mock_table.query.return_value = {
            'Items': [
                {'subscriber': 'task_a', 'wait_token': 'token_a', 'freshness_hours': 1}
            ]
        }
        
        mock_dynamodb = mocker.MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        
        mock_sfn = mocker.MagicMock()
        
        stale_event_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        
        mocker.patch('index._get_dynamodb', return_value=mock_dynamodb, create=True)
        # v0.79.3 (ADR #75) — also wire mock_table into DAL repos
        # so calls via subscriptions_repo / asset_events_repo land
        # on the same mock the test set up.
        from index import subscriptions_repo, asset_events_repo
        mocker.patch.object(type(subscriptions_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_table)
        mocker.patch.object(type(asset_events_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_table)
        mocker.patch('index._get_sfn', return_value=mock_sfn)
        result = handler({
            'outlets': [{'name': 'inventory', 'uri': 's3://bucket/inv'}],
            'source_task': 'producer',
            'source_dag': 'pipeline',
            'event_time': stale_event_time
        }, None)
        
        assert result['notified'] == 0
        mock_sfn.send_task_success.assert_not_called()
    
    def test_multiple_outlets(self, mocker):
        """Should handle multiple outlets."""
        from index import handler
        
        mock_table = mocker.MagicMock()
        
        def mock_query(**kwargs):
            key = kwargs.get('ExpressionAttributeValues', {}).get(':dk', '')
            if 'inventory' in key:
                return {'Items': [{'subscriber': 'task_inv', 'wait_token': 'token_inv'}]}
            elif 'catalog' in key:
                return {'Items': [{'subscriber': 'task_cat', 'wait_token': 'token_cat'}]}
            return {'Items': []}
        
        mock_table.query.side_effect = mock_query
        
        mock_dynamodb = mocker.MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        
        mock_sfn = mocker.MagicMock()
        
        mocker.patch('index._get_dynamodb', return_value=mock_dynamodb, create=True)
        # v0.79.3 (ADR #75) — also wire mock_table into DAL repos
        # so calls via subscriptions_repo / asset_events_repo land
        # on the same mock the test set up.
        from index import subscriptions_repo, asset_events_repo
        mocker.patch.object(type(subscriptions_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_table)
        mocker.patch.object(type(asset_events_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_table)
        mocker.patch('index._get_sfn', return_value=mock_sfn)
        result = handler({
            'outlets': [
                {'name': 'inventory', 'uri': 's3://bucket/inv'},
                {'name': 'catalog', 'uri': 's3://bucket/cat'}
            ],
            'source_task': 'producer',
            'source_dag': 'pipeline',
            'event_time': datetime.now(timezone.utc).isoformat()
        }, None)
        
        assert result['notified'] == 2
        assert 'inventory' in result['assets']
        assert 'catalog' in result['assets']


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_check_freshness_fresh(self):
        """Fresh event should return True."""
        from index import _check_freshness
        
        event_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert _check_freshness('inventory', event_time, 24) is True
    
    def test_check_freshness_stale(self):
        """Stale event should return False."""
        from index import _check_freshness
        
        event_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        assert _check_freshness('inventory', event_time, 24) is False
    
    def test_get_asset_subscribers(self, mocker):
        """Should query subscribers by asset key."""
        from index import _get_asset_subscribers
        
        mock_table = mocker.MagicMock()
        mock_table.query.return_value = {
            'Items': [
                {'subscriber': 'task_a', 'wait_token': 'token_a'}
            ]
        }
        
        mock_dynamodb = mocker.MagicMock()
        mock_dynamodb.Table.return_value = mock_table
        
        mocker.patch('index._get_dynamodb', return_value=mock_dynamodb, create=True)
        # v0.79.3 (ADR #75) — also wire mock_table into DAL repos
        # so calls via subscriptions_repo / asset_events_repo land
        # on the same mock the test set up.
        from index import subscriptions_repo, asset_events_repo
        mocker.patch.object(type(subscriptions_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_table)
        mocker.patch.object(type(asset_events_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_table)
        result = _get_asset_subscribers('inventory')
        
        assert len(result) == 1
        assert result[0]['subscriber'] == 'task_a'
        mock_table.query.assert_called_once()
        call_kwargs = mock_table.query.call_args[1]
        assert ':dk' in str(call_kwargs)


class TestConsecutiveNotify:
    """Test consecutive re-check in notify."""
    
    def test_consecutive_not_ready_skips_signal(self, mocker):
        """3/7 consecutive days → don't send signal, keep subscription."""
        from index import handler
        
        mock_sub_table = mocker.MagicMock()
        mock_sub_table.query.return_value = {
            'Items': [{
                'subscriber': 'weekly_task',
                'wait_token': 'token123',
                'subscription_type': 'asset_consecutive',
                'consecutive_days': 7,
                'reference_date': '2026-02-22'
            }]
        }
        
        mock_events_table = mocker.MagicMock()
        mock_events_table.query.return_value = {
            'Items': [
                {'asset_name': 'daily', 'execution_date': '2026-02-20', 'event_time': '2026-02-20T08:00:00Z'},
                {'asset_name': 'daily', 'execution_date': '2026-02-21', 'event_time': '2026-02-21T08:00:00Z'},
                {'asset_name': 'daily', 'execution_date': '2026-02-22', 'event_time': '2026-02-22T08:00:00Z'},
            ]
        }
        
        mock_dynamodb = mocker.MagicMock()
        def table_router(name):
            if 'subscription' in name or 'dependency' in name:
                return mock_sub_table
            return mock_events_table
        mock_dynamodb.Table.side_effect = table_router
        
        mock_sfn = mocker.MagicMock()
        
        mocker.patch('index._get_dynamodb', return_value=mock_dynamodb, create=True)
        # v0.79.3 (ADR #75) — wire the per-table mocks into the DAL repos.
        from index import subscriptions_repo, asset_events_repo
        mocker.patch.object(type(subscriptions_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_sub_table)
        mocker.patch.object(type(asset_events_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_events_table)
        mocker.patch('index._get_sfn', return_value=mock_sfn)
        result = handler({
            'outlets': [{'name': 'daily', 'uri': 's3://bucket/daily'}],
            'source_task': 'daily_task',
            'source_dag': 'daily_pipeline',
            'event_time': '2026-02-22T08:00:00Z'
        }, None)
        
        assert result['notified'] == 0
        mock_sfn.send_task_success.assert_not_called()
        mock_sub_table.delete_item.assert_not_called()
    
    def test_consecutive_ready_sends_signal(self, mocker):
        """7/7 consecutive days → send signal."""
        from index import handler
        
        mock_sub_table = mocker.MagicMock()
        mock_sub_table.query.return_value = {
            'Items': [{
                'subscriber': 'weekly_task',
                'wait_token': 'token123',
                'subscription_type': 'asset_consecutive',
                'consecutive_days': 7,
                'reference_date': '2026-02-22'
            }]
        }
        
        mock_events_table = mocker.MagicMock()
        mock_events_table.query.return_value = {
            'Items': [
                {'asset_name': 'daily', 'execution_date': f'2026-02-{16+i:02d}', 'event_time': f'2026-02-{16+i:02d}T08:00:00Z'}
                for i in range(7)
            ]
        }
        
        mock_dynamodb = mocker.MagicMock()
        def table_router(name):
            if 'subscription' in name or 'dependency' in name:
                return mock_sub_table
            return mock_events_table
        mock_dynamodb.Table.side_effect = table_router
        
        mock_sfn = mocker.MagicMock()
        
        mocker.patch('index._get_dynamodb', return_value=mock_dynamodb, create=True)
        # v0.79.3 (ADR #75) — wire the per-table mocks into the DAL repos.
        from index import subscriptions_repo, asset_events_repo
        mocker.patch.object(type(subscriptions_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_sub_table)
        mocker.patch.object(type(asset_events_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_events_table)
        mocker.patch('index._get_sfn', return_value=mock_sfn)
        result = handler({
            'outlets': [{'name': 'daily', 'uri': 's3://bucket/daily'}],
            'source_task': 'daily_task',
            'source_dag': 'daily_pipeline',
            'event_time': '2026-02-22T08:00:00Z'
        }, None)
        
        assert result['notified'] == 1
        assert 'weekly_task' in result['subscribers']
        mock_sfn.send_task_success.assert_called_once()
    
    def test_mixed_within_and_consecutive(self, mocker):
        """within subscriber gets signal, consecutive (not ready) doesn't."""
        from index import handler
        
        mock_sub_table = mocker.MagicMock()
        mock_sub_table.query.return_value = {
            'Items': [
                {
                    'subscriber': 'within_task',
                    'wait_token': 'token_within',
                    'subscription_type': 'asset',
                },
                {
                    'subscriber': 'consec_task',
                    'wait_token': 'token_consec',
                    'subscription_type': 'asset_consecutive',
                    'consecutive_days': 7,
                    'reference_date': '2026-02-22'
                }
            ]
        }
        
        mock_events_table = mocker.MagicMock()
        mock_events_table.query.return_value = {
            'Items': [
                {'asset_name': 'daily', 'execution_date': '2026-02-20', 'event_time': '2026-02-20T08:00:00Z'},
                {'asset_name': 'daily', 'execution_date': '2026-02-21', 'event_time': '2026-02-21T08:00:00Z'},
                {'asset_name': 'daily', 'execution_date': '2026-02-22', 'event_time': '2026-02-22T08:00:00Z'},
            ]
        }
        
        mock_dynamodb = mocker.MagicMock()
        def table_router(name):
            if 'subscription' in name or 'dependency' in name:
                return mock_sub_table
            return mock_events_table
        mock_dynamodb.Table.side_effect = table_router
        
        mock_sfn = mocker.MagicMock()
        
        mocker.patch('index._get_dynamodb', return_value=mock_dynamodb, create=True)
        # v0.79.3 (ADR #75) — wire the per-table mocks into the DAL repos.
        from index import subscriptions_repo, asset_events_repo
        mocker.patch.object(type(subscriptions_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_sub_table)
        mocker.patch.object(type(asset_events_repo), 'table',
                            new_callable=mocker.PropertyMock,
                            return_value=mock_events_table)
        mocker.patch('index._get_sfn', return_value=mock_sfn)
        result = handler({
            'outlets': [{'name': 'daily', 'uri': 's3://bucket/daily'}],
            'source_task': 'daily_task',
            'source_dag': 'daily_pipeline',
            'event_time': '2026-02-22T08:00:00Z'
        }, None)
        
        assert result['notified'] == 1
        assert 'within_task' in result['subscribers']
        assert 'consec_task' not in result['subscribers']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
