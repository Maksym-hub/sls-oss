"""Asset listing route (free / open-core).

Team asset management (events, trigger, delete, lineage, glue-schema, queue
operations) lives in ee/team/assets.py. The _build_assets_from_pipelines
helper stays here because the free list_assets uses it. See ADR #98.
"""
import json
import os
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Dict

from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError, BotoCoreError

from config import sfn
from dal import (
    pipelines_repo,
    asset_events_repo,
    queued_events_repo,
)
from response import cors_response, safe_parse_body
from logger import log
from constants import Limits
from utils import safe_param_int, dict_schema_richness


def _new_asset_entry() -> dict:
    """Create empty asset dict with all fields."""
    return {
        'producers': [], 'consumers': [], 'uri': '', 'group': '',
        'owner': '', 'schema': [], 'glue_table': '', 'glue_catalog': '',
        'glue_region': '',
        'description': '', 'tags': [], 'freshness_hours': None,
        # Cross-pipeline schema conflict tracking. Populated by
        # `_build_assets_from_pipelines` when the same asset is declared
        # with diverging schemas in 2+ pipelines. The richest declaration
        # still wins (see `dict_schema_richness`); this field surfaces the
        # conflict to the UI so operators can fix it before it bites.
        # Empty list when there is no conflict.
        'schema_conflicts': [],
    }


def _build_assets_from_pipelines() -> tuple:
    """Build complete asset map and DAG triggers from pipeline_registry.
    
    Single source of truth for all asset data. Scans all pipelines,
    parses tasks, and aggregates outlets/inlets/wait_for.
    
    Returns:
        Tuple of (assets_dict, dag_triggers_dict)
    """
    pipelines = pipelines_repo.list_all(max_items=Limits.MAX_SCAN_ITEMS)
    
    assets = {}
    dag_triggers = {}
    task_outlets = {}  # "dag.task" -> [asset_names]
    task_dependencies = {}  # "dag.task" -> ["dag.dep1", ...]
    
    for pipeline in pipelines:
        pipeline_name = pipeline.get('pipeline_name', '')
        
        # Parse asset_schedule
        asset_schedule_str = pipeline.get('asset_schedule', '')
        if asset_schedule_str:
            try:
                asset_schedule = json.loads(asset_schedule_str) if isinstance(asset_schedule_str, str) else asset_schedule_str
                if asset_schedule and asset_schedule.get('assets'):
                    dag_triggers[pipeline_name] = asset_schedule
            except (json.JSONDecodeError, TypeError) as e:
                # Malformed asset_schedule JSON — log so operators can fix the pipeline.
                # Without this warning, orphan-detection silently treats the pipeline's
                # assets as unreferenced and may delete their event history.
                log.warn(
                    "_build_assets_from_pipelines",
                    "Skipped malformed asset_schedule",
                    pipeline=pipeline_name,
                    error=str(e),
                )
        
        # Parse tasks
        tasks_str = pipeline.get('tasks', '[]')
        try:
            tasks = json.loads(tasks_str) if isinstance(tasks_str, str) else tasks_str
            for task in tasks:
                task_id = f"{pipeline_name}.{task.get('task_id', '')}"
                
                deps = task.get('dependencies', [])
                task_dependencies[task_id] = [f"{pipeline_name}.{d}" for d in deps]
                
                # Process outlets
                task_outlet_names = []
                for outlet in task.get('outlets', []):
                    outlet_name = outlet.get('name') if isinstance(outlet, dict) else outlet
                    if outlet_name:
                        task_outlet_names.append(outlet_name)
                        if outlet_name not in assets:
                            assets[outlet_name] = _new_asset_entry()
                        if task_id not in assets[outlet_name]['producers']:
                            assets[outlet_name]['producers'].append(task_id)
                        if isinstance(outlet, dict):
                            # All non-schema fields: last-writer-wins (existing behavior).
                            for field in ('uri', 'owner', 'glue_table', 'glue_catalog',
                                          'glue_region', 'description', 'tags'):
                                if outlet.get(field):
                                    assets[outlet_name][field] = outlet[field]
                            if outlet.get('freshness_hours') is not None:
                                assets[outlet_name]['freshness_hours'] = outlet['freshness_hours']

                            # Schema field: prefer the richer declaration when the same
                            # asset is produced by multiple pipelines with different
                            # schemas. Richness scores columns + non-default constraints
                            # (PK, partition, NOT NULL, ...) — see utils.dict_schema_richness.
                            # Ties keep the first declaration. Always warn so operators
                            # can fix the divergent declaration.
                            new_schema = outlet.get('schema') or []
                            existing_schema = assets[outlet_name].get('schema') or []
                            if new_schema:
                                if not existing_schema:
                                    assets[outlet_name]['schema'] = new_schema
                                elif existing_schema != new_schema:
                                    log.warn(
                                        "_build_assets_from_pipelines",
                                        "Asset has conflicting schemas across pipelines",
                                        asset=outlet_name,
                                        pipeline=pipeline_name,
                                        existing_columns=len(existing_schema),
                                        new_columns=len(new_schema),
                                    )
                                    # Record the conflict so the UI can surface it.
                                    # We keep one entry per (pipeline, column-count)
                                    # divergence — enough for the operator to find
                                    # both sources without bloating the response.
                                    assets[outlet_name]['schema_conflicts'].append({
                                        'pipeline': pipeline_name,
                                        'columns': len(new_schema),
                                    })
                                    if dict_schema_richness(new_schema) > dict_schema_richness(existing_schema):
                                        assets[outlet_name]['schema'] = new_schema
                
                task_outlets[task_id] = task_outlet_names
                
                # Process inlets
                for inlet in task.get('inlets', []):
                    inlet_name = inlet.get('name') if isinstance(inlet, dict) else inlet
                    if inlet_name:
                        if inlet_name not in assets:
                            assets[inlet_name] = _new_asset_entry()
                        if task_id not in assets[inlet_name]['consumers']:
                            assets[inlet_name]['consumers'].append(task_id)
                
                # Process wait_for
                for wait_item in task.get('wait_for', []):
                    wait_name = wait_item.get('name') if isinstance(wait_item, dict) else wait_item
                    if wait_name:
                        if wait_name not in assets:
                            assets[wait_name] = _new_asset_entry()
                        if task_id not in assets[wait_name]['consumers']:
                            assets[wait_name]['consumers'].append(task_id)
        except (json.JSONDecodeError, TypeError) as e:
            # Malformed tasks JSON — log so operators can fix the pipeline.
            # Without this warning, the pipeline's outlets/inlets become invisible
            # to orphan-detection and may cause spurious orphan deletions.
            log.warn(
                "_build_assets_from_pipelines",
                "Skipped malformed tasks JSON",
                pipeline=pipeline_name,
                error=str(e),
            )
    
    # Derive consumers from task dependencies
    for task_id, deps in task_dependencies.items():
        for dep_task_id in deps:
            dep_outlets = task_outlets.get(dep_task_id, [])
            for outlet_name in dep_outlets:
                if outlet_name in assets:
                    if task_id not in assets[outlet_name]['consumers']:
                        assets[outlet_name]['consumers'].append(task_id)
    
    # Auto-derive group from name
    for name, data in assets.items():
        if not data['group'] and '/' in name:
            data['group'] = name.split('/')[0]
    
    return assets, dag_triggers


def list_assets(event: Dict) -> Dict:
    """List all assets from pipeline registry.
    
    Builds asset list from pipeline_registry task outlets/inlets.
    Supports optional group filter.
    
    Args:
        event: API Gateway event with optional query parameters:
            - group: Filter assets by group name
    
    Returns:
        CORS response with assets list.
    """
    try:
        params = event.get('queryStringParameters') or {}
        group_filter = params.get('group')
        
        assets_map, _ = _build_assets_from_pipelines()
        
        assets = []
        for name, data in assets_map.items():
            if group_filter and data.get('group') != group_filter:
                continue
            assets.append({
                'name': name,
                'uri': data.get('uri', ''),
                'group': data.get('group', ''),
                'description': data.get('description', ''),
                'owner': data.get('owner', ''),
                'schema': data.get('schema', []),
                'glue_table': data.get('glue_table', ''),
                'glue_catalog': data.get('glue_catalog', ''),
                'glue_region': data.get('glue_region', ''),
                'tags': data.get('tags', []),
                'freshness_hours': data.get('freshness_hours'),
                'producers': data.get('producers', []),
                'consumers': data.get('consumers', []),
            })
        
        assets.sort(key=lambda x: (x['group'], x['name']))
        
        return cors_response(200, {
            'assets': assets,
            'count': len(assets)
        })
        
    except Exception as e:
        log.error("list_assets", "Error listing assets", error=str(e))
        return cors_response(500, {'error': str(e)})



def register(router) -> None:
    """Register the free asset listing route. See ADR #97."""
    router.add('GET', '/api/assets', list_assets)
