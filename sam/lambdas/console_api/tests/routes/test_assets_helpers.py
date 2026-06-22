"""
Unit tests for routes.assets._build_assets_from_pipelines.

This helper is the single source of truth for all asset metadata across
list_assets, delete_orphaned_assets, and get_asset_lineage. Bugs here
cascade into wrong UI data and incorrect orphan detection.

Tests use pytest-mock to patch pipelines_repo on the routes.assets module.
"""

import json
import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _pipeline(name, tasks=None, asset_schedule=None, **extra):
    """Build a pipeline_registry-shaped dict, JSON-encoding nested fields."""
    item = {'pipeline_name': name}
    if tasks is not None:
        item['tasks'] = tasks if isinstance(tasks, str) else json.dumps(tasks)
    if asset_schedule is not None:
        item['asset_schedule'] = (
            asset_schedule if isinstance(asset_schedule, str)
            else json.dumps(asset_schedule)
        )
    item.update(extra)
    return item


@pytest.fixture
def patched_pipelines(mocker):
    """Patch routes.assets.pipelines_repo with a controllable list_all().

    Returns a setter: `patched_pipelines([pipe1, pipe2, ...])`.
    """
    from routes import assets as assets_route
    repo_mock = mocker.MagicMock()
    mocker.patch.object(assets_route, 'pipelines_repo', repo_mock)

    def _set(pipelines):
        repo_mock.list_all.return_value = pipelines
    return _set


# ──────────────────────────────────────────────────────────────────────────────
# Basic shape
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildAssetsBasicShape:

    def test_empty_pipelines_yields_empty_result(self, patched_pipelines):
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([])
        assets, dag_triggers = _build_assets_from_pipelines()
        assert assets == {}
        assert dag_triggers == {}

    def test_pipeline_without_tasks_yields_empty_assets(self, patched_pipelines):
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([_pipeline('empty-pipe')])
        assets, dag_triggers = _build_assets_from_pipelines()
        assert assets == {}
        assert dag_triggers == {}

    def test_single_outlet_creates_producer(self, patched_pipelines):
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('etl', tasks=[{
                'task_id': 'extract',
                'outlets': [{'name': 'raw/orders', 'uri': 's3://bucket/raw/orders/'}],
            }]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert 'raw/orders' in assets
        assert assets['raw/orders']['producers'] == ['etl.extract']
        assert assets['raw/orders']['consumers'] == []
        assert assets['raw/orders']['uri'] == 's3://bucket/raw/orders/'

    def test_inlet_creates_consumer(self, patched_pipelines):
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('analytics', tasks=[{
                'task_id': 'transform',
                'inlets': [{'name': 'raw/orders'}],
            }]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert 'raw/orders' in assets
        assert assets['raw/orders']['consumers'] == ['analytics.transform']
        assert assets['raw/orders']['producers'] == []


# ──────────────────────────────────────────────────────────────────────────────
# Enrichment fields
# ──────────────────────────────────────────────────────────────────────────────

class TestEnrichmentFields:

    def test_outlet_dict_surfaces_owner_schema_glue_fields(self, patched_pipelines):
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('retail', tasks=[{
                'task_id': 'load',
                'outlets': [{
                    'name': 'retail/orders',
                    'uri': 's3://b/orders/',
                    'owner': 'data-team',
                    'description': 'Daily orders',
                    'tags': ['daily', 'pii'],
                    'schema': [{'name': 'order_id', 'type': 'bigint'}],
                    'glue_table': 'analytics.orders',
                    'glue_catalog': '123456789012',
                    'freshness_hours': 24,
                }],
            }]),
        ])
        assets, _ = _build_assets_from_pipelines()
        a = assets['retail/orders']
        assert a['owner'] == 'data-team'
        assert a['description'] == 'Daily orders'
        assert a['tags'] == ['daily', 'pii']
        assert a['schema'] == [{'name': 'order_id', 'type': 'bigint'}]
        assert a['glue_table'] == 'analytics.orders'
        assert a['glue_catalog'] == '123456789012'
        assert a['freshness_hours'] == 24

    def test_string_outlet_only_sets_name(self, patched_pipelines):
        """outlets: ['name_only'] (legacy shape) — should not crash, no enrichment."""
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('legacy', tasks=[{
                'task_id': 'extract',
                'outlets': ['plain_name'],
            }]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert 'plain_name' in assets
        assert assets['plain_name']['producers'] == ['legacy.extract']
        assert assets['plain_name']['uri'] == ''
        assert assets['plain_name']['owner'] == ''

    def test_freshness_zero_is_kept(self, patched_pipelines):
        """freshness_hours=0 is a valid value (immediate staleness check)."""
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('p', tasks=[{
                'task_id': 't',
                'outlets': [{'name': 'a', 'freshness_hours': 0}],
            }]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert assets['a']['freshness_hours'] == 0


# ──────────────────────────────────────────────────────────────────────────────
# Schema conflict detection across pipelines
# ──────────────────────────────────────────────────────────────────────────────

class TestSchemaConflictDetection:
    """When the same asset is produced by multiple pipelines that declare
    different schemas, _build_assets_from_pipelines must:
      1. Pick the schema with more columns (the richer declaration).
      2. Log a warning so operators can fix the divergent declaration.
      3. Keep all other fields (uri, owner, ...) on last-writer-wins (existing behavior).
    """

    def test_same_schema_in_multiple_pipelines_no_warning(self, patched_pipelines, mocker):
        from routes.assets import _build_assets_from_pipelines
        from routes import assets as assets_route
        warn_spy = mocker.spy(assets_route.log, 'warn')

        same_schema = [{'name': 'id', 'type': 'bigint'}]
        patched_pipelines([
            _pipeline('p1', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': same_schema},
            ]}]),
            _pipeline('p2', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': same_schema},
            ]}]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert assets['shared/asset']['schema'] == same_schema
        # No conflict warning emitted when both declarations match exactly.
        for call in warn_spy.call_args_list:
            assert 'conflicting schemas' not in str(call)

    def test_richer_schema_wins_when_added_second(self, patched_pipelines, mocker):
        from routes.assets import _build_assets_from_pipelines
        from routes import assets as assets_route
        warn_spy = mocker.spy(assets_route.log, 'warn')

        small = [{'name': 'id', 'type': 'bigint'}]
        rich = [
            {'name': 'id', 'type': 'bigint', 'primary_key': True},
            {'name': 'amount', 'type': 'decimal(10,2)'},
            {'name': 'created_at', 'type': 'timestamp'},
        ]
        # First pipeline declares the small schema, second declares the rich one.
        patched_pipelines([
            _pipeline('p1', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': small},
            ]}]),
            _pipeline('p2', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': rich},
            ]}]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert assets['shared/asset']['schema'] == rich, "Richer schema must win"
        warn_spy.assert_called()  # conflict warning emitted

    def test_richer_schema_wins_when_added_first(self, patched_pipelines, mocker):
        """Order should not matter — the richer schema always wins."""
        from routes.assets import _build_assets_from_pipelines
        from routes import assets as assets_route
        warn_spy = mocker.spy(assets_route.log, 'warn')

        small = [{'name': 'id', 'type': 'bigint'}]
        rich = [
            {'name': 'id', 'type': 'bigint'},
            {'name': 'amount', 'type': 'decimal(10,2)'},
            {'name': 'created_at', 'type': 'timestamp'},
        ]
        patched_pipelines([
            _pipeline('p1', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': rich},
            ]}]),
            _pipeline('p2', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': small},
            ]}]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert assets['shared/asset']['schema'] == rich
        warn_spy.assert_called()

    def test_conflict_warn_includes_asset_and_pipeline(self, patched_pipelines, mocker):
        """The warning must carry asset name + pipeline name + column counts."""
        from routes.assets import _build_assets_from_pipelines
        from routes import assets as assets_route
        warn_spy = mocker.spy(assets_route.log, 'warn')

        patched_pipelines([
            _pipeline('p1', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': [{'name': 'a', 'type': 'bigint'}]},
            ]}]),
            _pipeline('p2', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset',
                 'schema': [{'name': 'b', 'type': 'string'},
                            {'name': 'c', 'type': 'string'}]},
            ]}]),
        ])
        _build_assets_from_pipelines()

        # Find the schema-conflict warning amongst all logged warnings.
        conflict_calls = [
            c for c in warn_spy.call_args_list
            if 'conflicting schemas' in str(c)
        ]
        assert len(conflict_calls) == 1, f"Expected exactly 1 conflict warning, got {len(conflict_calls)}"
        kwargs = conflict_calls[0].kwargs
        assert kwargs.get('asset') == 'shared/asset'
        assert kwargs.get('pipeline') == 'p2'
        assert kwargs.get('existing_columns') == 1
        assert kwargs.get('new_columns') == 2

    def test_empty_schema_does_not_overwrite_existing(self, patched_pipelines):
        """An outlet without `schema` must not erase a previously-declared schema."""
        from routes.assets import _build_assets_from_pipelines
        rich = [{'name': 'id', 'type': 'bigint', 'primary_key': True}]
        patched_pipelines([
            _pipeline('producer', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': rich, 'owner': 'team-a'},
            ]}]),
            _pipeline('consumer', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset'},  # No schema field
            ]}]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert assets['shared/asset']['schema'] == rich

    def test_equal_length_different_content_keeps_first(self, patched_pipelines, mocker):
        """If both schemas have the same column count but differ, keep the first
        and warn — the user must resolve the inconsistency."""
        from routes.assets import _build_assets_from_pipelines
        from routes import assets as assets_route
        warn_spy = mocker.spy(assets_route.log, 'warn')

        first = [{'name': 'a', 'type': 'bigint'}, {'name': 'b', 'type': 'string'}]
        second = [{'name': 'a', 'type': 'string'}, {'name': 'c', 'type': 'bigint'}]
        patched_pipelines([
            _pipeline('p1', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': first},
            ]}]),
            _pipeline('p2', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': second},
            ]}]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert assets['shared/asset']['schema'] == first
        # Conflict warning still emitted.
        assert any('conflicting schemas' in str(c) for c in warn_spy.call_args_list)

    def test_more_constraints_wins_on_tied_column_count(self, patched_pipelines, mocker):
        """Same column count, different constraint richness — the schema with
        more constraints (PK, partition, NOT NULL) wins. Catches the case
        where a producer pipeline declares the typed schema and a consumer
        pipeline only declares names+types."""
        from routes.assets import _build_assets_from_pipelines
        from routes import assets as assets_route
        warn_spy = mocker.spy(assets_route.log, 'warn')

        plain = [
            {'name': 'id', 'type': 'bigint'},
            {'name': 'amount', 'type': 'decimal(10,2)'},
        ]
        rich = [
            {'name': 'id', 'type': 'bigint',
             'primary_key': True, 'nullable': False},
            {'name': 'amount', 'type': 'decimal(10,2)',
             'description': 'USD'},
        ]
        # First pipeline declares plain, second declares rich. Same column count.
        patched_pipelines([
            _pipeline('p1', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': plain},
            ]}]),
            _pipeline('p2', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': rich},
            ]}]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert assets['shared/asset']['schema'] == rich, \
            "Constraint-richer schema must win even when column counts match"
        assert any('conflicting schemas' in str(c) for c in warn_spy.call_args_list)

    def test_schema_conflicts_field_empty_when_no_conflict(self, patched_pipelines):
        """Single-pipeline declaration → schema_conflicts is empty list."""
        from routes.assets import _build_assets_from_pipelines
        rich = [{'name': 'id', 'type': 'bigint', 'primary_key': True}]
        patched_pipelines([
            _pipeline('p1', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': rich},
            ]}]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert assets['shared/asset']['schema_conflicts'] == []

    def test_schema_conflicts_field_populated_on_conflict(self, patched_pipelines):
        """Two pipelines with different schemas → schema_conflicts surfaces
        the conflicting pipeline + its column count for UI rendering."""
        from routes.assets import _build_assets_from_pipelines
        small = [{'name': 'id', 'type': 'bigint'}]
        rich = [
            {'name': 'id', 'type': 'bigint'},
            {'name': 'amount', 'type': 'decimal(10,2)'},
            {'name': 'created_at', 'type': 'timestamp'},
        ]
        patched_pipelines([
            _pipeline('producer', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': small},
            ]}]),
            _pipeline('consumer', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': rich},
            ]}]),
        ])
        assets, _ = _build_assets_from_pipelines()
        # Winner is `rich` (3 columns), conflict tracked with the
        # *latter* pipeline's contribution (consumer with 3 cols).
        assert len(assets['shared/asset']['schema_conflicts']) == 1
        conflict = assets['shared/asset']['schema_conflicts'][0]
        assert conflict['pipeline'] == 'consumer'
        assert conflict['columns'] == 3

    def test_schema_conflicts_accumulates_across_three_pipelines(self, patched_pipelines):
        """Three pipelines, all different schemas → two conflict entries
        (the first declaration is the baseline; subsequent ones are conflicts)."""
        from routes.assets import _build_assets_from_pipelines
        s1 = [{'name': 'a', 'type': 'bigint'}]
        s2 = [{'name': 'a', 'type': 'string'}, {'name': 'b', 'type': 'bigint'}]
        s3 = [{'name': 'a', 'type': 'date'}]
        patched_pipelines([
            _pipeline('p1', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': s1},
            ]}]),
            _pipeline('p2', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': s2},
            ]}]),
            _pipeline('p3', tasks=[{'task_id': 't', 'outlets': [
                {'name': 'shared/asset', 'schema': s3},
            ]}]),
        ])
        assets, _ = _build_assets_from_pipelines()
        conflicts = assets['shared/asset']['schema_conflicts']
        assert len(conflicts) == 2
        pipelines_seen = {c['pipeline'] for c in conflicts}
        # p1 is the baseline, p2 and p3 are the divergent ones.
        assert pipelines_seen == {'p2', 'p3'}


# ──────────────────────────────────────────────────────────────────────────────
# wait_for and dependency-derived consumers
# ──────────────────────────────────────────────────────────────────────────────

class TestWaitForAndDeps:

    def test_wait_for_dict_with_name_creates_consumer(self, patched_pipelines):
        """wait_for is parsed via the 'name' key (consistent with outlets/inlets)."""
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('downstream', tasks=[{
                'task_id': 'consume',
                'wait_for': [{'name': 'upstream/data'}],
            }]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert 'upstream/data' in assets
        assert assets['upstream/data']['consumers'] == ['downstream.consume']

    def test_wait_for_string_creates_consumer(self, patched_pipelines):
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('downstream', tasks=[{
                'task_id': 'consume',
                'wait_for': ['upstream/data'],
            }]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert assets['upstream/data']['consumers'] == ['downstream.consume']

    def test_dependency_derives_consumer_for_outlet(self, patched_pipelines):
        """Task B depends on Task A → A's outlet has B as consumer."""
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('etl', tasks=[
                {'task_id': 'extract', 'outlets': [{'name': 'raw/data'}]},
                {'task_id': 'transform',
                 'dependencies': ['extract'],
                 'outlets': [{'name': 'gold/data'}]},
            ]),
        ])
        assets, _ = _build_assets_from_pipelines()
        # raw/data: produced by extract, consumed by transform via deps
        assert assets['raw/data']['producers'] == ['etl.extract']
        assert 'etl.transform' in assets['raw/data']['consumers']
        # gold/data: produced by transform
        assert assets['gold/data']['producers'] == ['etl.transform']


# ──────────────────────────────────────────────────────────────────────────────
# Group derivation
# ──────────────────────────────────────────────────────────────────────────────

class TestGroupDerivation:

    def test_slash_in_name_derives_group(self, patched_pipelines):
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('p', tasks=[{
                'task_id': 't',
                'outlets': [{'name': 'retail/orders'}],
            }]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert assets['retail/orders']['group'] == 'retail'

    def test_no_slash_leaves_group_empty(self, patched_pipelines):
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('p', tasks=[{
                'task_id': 't',
                'outlets': [{'name': 'orders'}],
            }]),
        ])
        assets, _ = _build_assets_from_pipelines()
        assert assets['orders']['group'] == ''


# ──────────────────────────────────────────────────────────────────────────────
# DAG triggers (asset_schedule)
# ──────────────────────────────────────────────────────────────────────────────

class TestDagTriggers:

    def test_asset_schedule_populates_dag_triggers(self, patched_pipelines):
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('analytics',
                      tasks=[],
                      asset_schedule={'assets': ['raw/orders'], 'operator': 'OR'}),
        ])
        _, dag_triggers = _build_assets_from_pipelines()
        assert 'analytics' in dag_triggers
        assert dag_triggers['analytics']['assets'] == ['raw/orders']
        assert dag_triggers['analytics']['operator'] == 'OR'

    def test_empty_asset_schedule_skipped(self, patched_pipelines):
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('p', tasks=[], asset_schedule={'assets': []}),
        ])
        _, dag_triggers = _build_assets_from_pipelines()
        assert dag_triggers == {}


# ──────────────────────────────────────────────────────────────────────────────
# Resilience to malformed data (silent-except → warning)
# ──────────────────────────────────────────────────────────────────────────────

class TestMalformedData:
    """Regression: v0.70.18 added warn-logs in place of silent except.

    The behavior is unchanged (still skips the bad pipeline and continues),
    but operators now see warnings in CloudWatch instead of vanishing data.
    """

    def test_malformed_tasks_json_logs_warning_and_skips(self, patched_pipelines, mocker):
        from routes import assets as assets_route
        warn_spy = mocker.patch.object(assets_route.log, 'warn')

        good_pipe = _pipeline('good', tasks=[{
            'task_id': 'extract',
            'outlets': [{'name': 'good/asset'}],
        }])
        bad_pipe = {'pipeline_name': 'broken', 'tasks': '{not valid json'}
        patched_pipelines([bad_pipe, good_pipe])

        assets, _ = assets_route._build_assets_from_pipelines()

        # Good pipeline still processed
        assert 'good/asset' in assets
        # Warning emitted for the broken one — at least one call mentioning the pipeline
        assert warn_spy.called
        broken_warns = [
            c for c in warn_spy.call_args_list
            if c.kwargs.get('pipeline') == 'broken'
        ]
        assert len(broken_warns) >= 1, "Expected a warning about the broken pipeline"

    def test_malformed_asset_schedule_logs_warning(self, patched_pipelines, mocker):
        from routes import assets as assets_route
        warn_spy = mocker.patch.object(assets_route.log, 'warn')

        bad_pipe = {
            'pipeline_name': 'broken-sched',
            'asset_schedule': '{also invalid',
            'tasks': '[]',
        }
        patched_pipelines([bad_pipe])

        assets, dag_triggers = assets_route._build_assets_from_pipelines()
        assert assets == {}
        assert dag_triggers == {}
        assert any(
            c.kwargs.get('pipeline') == 'broken-sched'
            for c in warn_spy.call_args_list
        ), "Expected a warning for bad asset_schedule"

    def test_malformed_pipeline_does_not_crash_helper(self, patched_pipelines):
        """The whole helper must not raise; orphan-detection depends on it
        running to completion even when one pipeline is corrupt."""
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            {'pipeline_name': 'broken', 'tasks': 'definitely not json'},
            _pipeline('good', tasks=[{
                'task_id': 't', 'outlets': [{'name': 'good/asset'}],
            }]),
        ])
        # Should NOT raise
        assets, _ = _build_assets_from_pipelines()
        assert 'good/asset' in assets


# ──────────────────────────────────────────────────────────────────────────────
# Multi-pipeline interactions
# ──────────────────────────────────────────────────────────────────────────────

class TestMultiPipeline:

    def test_outlet_in_one_pipeline_inlet_in_another(self, patched_pipelines):
        from routes.assets import _build_assets_from_pipelines
        patched_pipelines([
            _pipeline('producer', tasks=[{
                'task_id': 'extract',
                'outlets': [{'name': 'shared/asset'}],
            }]),
            _pipeline('consumer', tasks=[{
                'task_id': 'analyze',
                'inlets': [{'name': 'shared/asset'}],
            }]),
        ])
        assets, _ = _build_assets_from_pipelines()
        a = assets['shared/asset']
        assert a['producers'] == ['producer.extract']
        assert a['consumers'] == ['consumer.analyze']

    def test_duplicate_producer_not_duplicated_in_list(self, patched_pipelines):
        """Same task referenced twice (e.g. via deps + outlet) → producer list deduped."""
        from routes.assets import _build_assets_from_pipelines
        # Two tasks both producing the same asset (unusual but possible)
        patched_pipelines([
            _pipeline('p', tasks=[
                {'task_id': 'a', 'outlets': [{'name': 'shared'}]},
                {'task_id': 'a', 'outlets': [{'name': 'shared'}]},  # duplicate task_id
            ]),
        ])
        assets, _ = _build_assets_from_pipelines()
        # task_id is the same for both, and producer list dedupes by `if task_id not in producers`
        assert assets['shared']['producers'] == ['p.a']
