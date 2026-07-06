"""Asset-system tests — combinators, refs, schedule normalization, watchers.

Drives the pure-logic surface of ``polyris.assets`` (CLAUDE.md #13):

  - ``Asset`` combinators (``&`` → AssetAll, ``|`` → AssetAny), equality/hash,
    and the ``within`` / ``consecutive`` freshness-ref constructors.
  - The reference types ``AssetRef`` / ``AssetConsecutiveRef`` and the
    container types ``AssetAll`` / ``AssetAny`` / ``AssetAlias`` — their
    operators, ``to_dict`` shape, and name flattening.
  - ``normalize_asset_schedule`` across every supported input shape, plus the
    module-level ``is_asset_triggered`` / ``get_asset_schedule_info`` helpers.
  - ``Watcher`` registration and ``generate_watchers_config`` grouping.

The ``from_pyarrow`` / ``from_parquet`` / ``from_pydantic`` / ``from_glue_table``
/ ``from_iceberg`` constructors are intentionally not covered here — they need
external libraries or live AWS and belong with the adapter/e2e tests.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from polyris import Asset, Column, types as t
from polyris.assets import (
    AssetAll,
    AssetAny,
    AssetRef,
    AssetConsecutiveRef,
    AssetAlias,
    Watcher,
    generate_watchers_config,
    normalize_asset_schedule,
    is_asset_triggered,
    get_asset_schedule_info,
)


# ============================================================ #
# Asset: equality, combinators, freshness refs
# ============================================================ #
class TestAssetCore:
    def test_equality_and_hash_by_name(self):
        a = Asset("ns/x")
        assert a == Asset("ns/x")
        assert a != Asset("ns/y")
        assert a != "ns/x"  # non-Asset
        assert hash(a) == hash(Asset("ns/x"))

    def test_repr(self):
        assert repr(Asset("ns/x")) == "Asset('ns/x')"

    def test_and_creates_assetall(self):
        a, b = Asset("ns/a"), Asset("ns/b")
        combined = a & b
        assert isinstance(combined, AssetAll)
        assert combined.asset_names == ["ns/a", "ns/b"]

    def test_and_with_assetall_prepends(self):
        a, b, c = Asset("ns/a"), Asset("ns/b"), Asset("ns/c")
        combined = a & (b & c)
        assert isinstance(combined, AssetAll)
        assert combined.asset_names == ["ns/a", "ns/b", "ns/c"]

    def test_and_with_bad_type_raises(self):
        with pytest.raises(TypeError):
            Asset("ns/a") & 5

    def test_or_creates_assetany(self):
        a, b = Asset("ns/a"), Asset("ns/b")
        combined = a | b
        assert isinstance(combined, AssetAny)
        assert combined.asset_names == ["ns/a", "ns/b"]

    def test_or_with_bad_type_raises(self):
        with pytest.raises(TypeError):
            Asset("ns/a") | 5

    def test_within_builds_assetref(self):
        ref = Asset("ns/x").within(days=1, hours=12)
        assert isinstance(ref, AssetRef)
        assert ref.freshness_hours == 36

    def test_within_without_args_raises(self):
        with pytest.raises(ValueError):
            Asset("ns/x").within()

    def test_consecutive_builds_ref(self):
        ref = Asset("ns/x").consecutive(days=7)
        assert isinstance(ref, AssetConsecutiveRef)
        assert ref.consecutive_days == 7

    def test_consecutive_zero_raises(self):
        with pytest.raises(ValueError):
            Asset("ns/x").consecutive(days=0)

    def test_to_dict_basic_and_producers(self):
        a = Asset("ns/orders", schema=[Column("id", t.bigint())])
        task = SimpleNamespace(task_id="make", _dag=None)
        a.add_producer(task)
        a.add_producer(task)  # idempotent
        d = a.to_dict()
        assert d["name"] == "ns/orders"
        assert [c["name"] for c in d["schema"]] == ["id"]
        assert d["producers"] == ["make"]


# ============================================================ #
# AssetRef / AssetConsecutiveRef
# ============================================================ #
class TestAssetRef:
    def test_name_uri_delegate(self):
        ref = Asset("ns/x").within(hours=1)
        assert ref.name == "ns/x"
        assert ref.uri == Asset("ns/x").uri

    def test_equality_and_hash(self):
        a = Asset("ns/x")
        assert AssetRef(a, 24) == AssetRef(a, 24)
        assert AssetRef(a, 24) != AssetRef(a, 48)
        assert AssetRef(a, 24) != "x"
        assert hash(AssetRef(a, 24)) == hash(AssetRef(a, 24))

    def test_to_dict_and_repr(self):
        ref = Asset("ns/x").within(hours=24)
        assert ref.to_dict() == {"asset_name": "ns/x", "freshness_hours": 24}
        assert "within=24h" in repr(ref)

    def test_and_or_combinators(self):
        ref = Asset("ns/x").within(hours=1)
        assert isinstance(ref & Asset("ns/y"), AssetAll)
        assert isinstance(ref | Asset("ns/y"), AssetAny)
        with pytest.raises(TypeError):
            ref & 5


class TestAssetConsecutiveRef:
    def test_name_to_dict_repr(self):
        ref = Asset("ns/x").consecutive(days=5)
        assert ref.name == "ns/x"
        assert ref.to_dict() == {"asset_name": "ns/x", "consecutive_days": 5}
        assert "consecutive=5d" in repr(ref)

    def test_equality_and_hash(self):
        a = Asset("ns/x")
        assert AssetConsecutiveRef(a, 5) == AssetConsecutiveRef(a, 5)
        assert AssetConsecutiveRef(a, 5) != AssetConsecutiveRef(a, 6)
        assert hash(AssetConsecutiveRef(a, 5)) == hash(AssetConsecutiveRef(a, 5))

    def test_and_or_combinators(self):
        ref = Asset("ns/x").consecutive(days=7)
        assert isinstance(ref & Asset("ns/y"), AssetAll)
        assert isinstance(ref | Asset("ns/y"), AssetAny)
        with pytest.raises(TypeError):
            ref | 5


# ============================================================ #
# AssetAll / AssetAny
# ============================================================ #
class TestAssetAll:
    def test_operator_and_names(self):
        grp = AssetAll([Asset("ns/a"), Asset("ns/b")])
        assert grp.operator == "AND"
        assert grp.asset_names == ["ns/a", "ns/b"]
        assert grp.to_dict() == {"operator": "AND", "assets": ["ns/a", "ns/b"]}
        assert "AssetAll" in repr(grp)

    def test_chained_and(self):
        grp = AssetAll([Asset("ns/a")]) & Asset("ns/b")
        assert grp.asset_names == ["ns/a", "ns/b"]
        merged = AssetAll([Asset("ns/a")]) & AssetAll([Asset("ns/b")])
        assert merged.asset_names == ["ns/a", "ns/b"]

    def test_or_mixes_into_assetany(self):
        mixed = AssetAll([Asset("ns/a"), Asset("ns/b")]) | Asset("ns/c")
        assert isinstance(mixed, AssetAny)

    def test_bad_combinations_raise(self):
        with pytest.raises(TypeError):
            AssetAll([Asset("ns/a")]) & 5
        with pytest.raises(TypeError):
            AssetAll([Asset("ns/a")]) | 5


class TestAssetAny:
    def test_operator_and_names_with_nested(self):
        grp = AssetAny([Asset("ns/a"), AssetAll([Asset("ns/b"), Asset("ns/c")])])
        assert grp.operator == "OR"
        # Nested AssetAll renders as a grouped expression.
        assert grp.asset_names == ["ns/a", "(ns/b & ns/c)"]

    def test_to_dict_with_asset_ref_and_all(self):
        grp = AssetAny([
            Asset("ns/a"),
            Asset("ns/b").within(hours=2),
            AssetAll([Asset("ns/c")]),
        ])
        d = grp.to_dict()
        assert d["operator"] == "OR"
        # plain Asset → name; AssetRef → dict with freshness; AssetAll → dict.
        assert d["assets"][0] == "ns/a"
        assert d["assets"][1]["freshness_hours"] == 2
        assert d["assets"][2]["operator"] == "AND"

    def test_chained_or(self):
        merged = AssetAny([Asset("ns/a")]) | AssetAny([Asset("ns/b")])
        assert len(merged.assets) == 2
        appended = AssetAny([Asset("ns/a")]) | Asset("ns/b")
        assert len(appended.assets) == 2

    def test_bad_or_raises(self):
        with pytest.raises(TypeError):
            AssetAny([Asset("ns/a")]) | 5


# ============================================================ #
# AssetAlias
# ============================================================ #
class TestAssetAlias:
    def test_equality_hash_and_dict(self):
        alias = AssetAlias(name="all_sales", assets=[Asset("s/us"), Asset("s/eu")], description="d")
        assert alias == AssetAlias(name="all_sales", assets=[])
        assert alias != AssetAlias(name="other", assets=[])
        assert hash(alias) == hash(AssetAlias(name="all_sales"))
        d = alias.to_dict()
        assert d["is_alias"] is True
        assert d["operator"] == "OR"
        assert d["assets"] == ["s/us", "s/eu"]
        assert "2 assets" in repr(alias)

    def test_and_or_combinators(self):
        alias = AssetAlias(name="a", assets=[Asset("s/us")])
        assert isinstance(alias & Asset("s/eu"), AssetAll)
        assert isinstance(alias | Asset("s/eu"), AssetAny)
        assert isinstance(alias & AssetAlias(name="b", assets=[Asset("s/jp")]), AssetAll)
        with pytest.raises(TypeError):
            alias & 5
        with pytest.raises(TypeError):
            alias | 5


# ============================================================ #
# normalize_asset_schedule
# ============================================================ #
class TestNormalizeAssetSchedule:
    def test_none(self):
        assert normalize_asset_schedule(None) is None

    def test_single_asset(self):
        res = normalize_asset_schedule(Asset("ns/x"))
        assert isinstance(res, AssetAll)
        assert res.asset_names == ["ns/x"]

    def test_alias_becomes_any(self):
        alias = AssetAlias(name="a", assets=[Asset("s/us"), Asset("s/eu")])
        res = normalize_asset_schedule(alias)
        assert isinstance(res, AssetAny)
        assert len(res.assets) == 2

    def test_already_normalized_passthrough(self):
        grp = AssetAll([Asset("ns/a")])
        assert normalize_asset_schedule(grp) is grp

    def test_empty_list_is_none(self):
        assert normalize_asset_schedule([]) is None

    def test_single_item_list(self):
        res = normalize_asset_schedule([Asset("ns/x")])
        assert isinstance(res, AssetAll)
        assert res.asset_names == ["ns/x"]

    def test_single_alias_in_list(self):
        res = normalize_asset_schedule([AssetAlias(name="a", assets=[Asset("s/us")])])
        assert isinstance(res, AssetAny)

    def test_multiple_assets_default_and(self):
        res = normalize_asset_schedule([Asset("ns/a"), Asset("ns/b")])
        assert isinstance(res, AssetAll)
        assert res.asset_names == ["ns/a", "ns/b"]

    def test_alias_expanded_in_multi_list(self):
        res = normalize_asset_schedule([Asset("ns/a"), AssetAlias(name="x", assets=[Asset("s/us")])])
        assert isinstance(res, AssetAll)
        assert res.asset_names == ["ns/a", "s/us"]

    def test_mixed_operator_in_list_returns_as_is(self):
        res = normalize_asset_schedule([Asset("ns/a"), AssetAll([Asset("ns/b"), Asset("ns/c")])])
        assert isinstance(res, AssetAll)
        assert len(res.assets) == 2  # the nested AssetAll is kept as an element


# ============================================================ #
# module-level helpers
# ============================================================ #
class TestModuleHelpers:
    def test_is_asset_triggered(self):
        assert is_asset_triggered(SimpleNamespace(schedule=None)) is False
        assert is_asset_triggered(SimpleNamespace(schedule="rate(1 hour)")) is False
        assert is_asset_triggered(SimpleNamespace(schedule=Asset("ns/x"))) is True
        assert is_asset_triggered(SimpleNamespace(schedule=[Asset("ns/x")])) is True

    def test_get_asset_schedule_info_none(self):
        assert get_asset_schedule_info(SimpleNamespace(schedule=None)) is None

    def test_get_asset_schedule_info_and(self):
        info = get_asset_schedule_info(SimpleNamespace(schedule=Asset("ns/x")))
        assert info["operator"] == "AND"
        assert info["assets"] == ["ns/x"]
        assert info["eventbridge_rule_pattern"]["detail"]["asset_name"] == ["ns/x"]

    def test_get_asset_schedule_info_or_flattens(self):
        sched = AssetAny([Asset("ns/a"), AssetAll([Asset("ns/b"), Asset("ns/c")])])
        info = get_asset_schedule_info(SimpleNamespace(schedule=sched))
        assert info["operator"] == "OR"
        # AssetAll member is flattened into individual names.
        assert info["eventbridge_rule_pattern"]["detail"]["asset_name"] == ["ns/a", "ns/b", "ns/c"]


# ============================================================ #
# Watcher / generate_watchers_config
# ============================================================ #
class TestWatchers:
    def test_watcher_registers_on_asset_and_serializes(self):
        a = Asset("ns/inv")
        w = Watcher(asset=a, sqs_queue_arn="arn:aws:sqs:us-east-1:1:q", batch_size=5)
        assert w in a._watchers
        d = w.to_dict()
        assert d["asset_name"] == "ns/inv"
        assert d["sqs_queue_arn"].endswith(":q")
        assert d["batch_size"] == 5

    def test_empty_config(self):
        cfg = generate_watchers_config([])
        assert cfg["lambda_config"] is None
        assert cfg["event_source_mappings"] == []
        assert cfg["iam_statements"] == []

    def test_config_groups_by_queue_and_takes_max_batch(self):
        q = "arn:aws:sqs:us-east-1:1:shared"
        w1 = Watcher(asset=Asset("ns/a"), sqs_queue_arn=q, batch_size=5)
        w2 = Watcher(asset=Asset("ns/b"), sqs_queue_arn=q, batch_size=10)
        cfg = generate_watchers_config([w1, w2])
        # Both share a queue → a single event source mapping.
        assert len(cfg["event_source_mappings"]) == 1
        esm = cfg["event_source_mappings"][0]
        assert esm["event_source_arn"] == q
        assert esm["batch_size"] == 10  # max of the two
        assert len(esm["watchers"]) == 2
        # IAM grants SQS + EventBridge.
        actions = [a for stmt in cfg["iam_statements"] for a in stmt["actions"]]
        assert "sqs:ReceiveMessage" in actions
        assert "events:PutEvents" in actions


def test_assets_disabled_without_optin(monkeypatch):
    """Assets ship disabled in the v1 build: constructing one without the opt-in
    (POLYRIS_ENABLE_ASSETS=1 / the master switch) raises a clear error. The whole
    test suite runs with the opt-in on (see the root conftest), so this test
    removes it to exercise the shipped default."""
    import polyris.assets as _assets

    monkeypatch.delenv("POLYRIS_ENABLE_ASSETS", raising=False)
    monkeypatch.setattr(_assets, "_ASSETS_ENABLED", False)
    with pytest.raises(RuntimeError, match="disabled in this release"):
        _assets.Asset("x")
