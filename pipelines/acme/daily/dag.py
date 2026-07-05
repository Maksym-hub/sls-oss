"""Acme Daily Pipeline.

Extracts data from the Acme retail source and transforms into analytical assets.
Runs daily via EventBridge schedule.

Extractors run only on current date (skip_on_backfill=True).

This pipeline demonstrates:
- Multi-stage ETL (extract → staging → derived assets)
- Asset outlets/inlets for lineage tracking
- Typed schemas with constraints (PK, partition, NOT NULL)
- One asset (product_details) backed by an actual Glue table for drift detection
- skip_on_backfill for source extraction tasks
- trigger_rule="all_done" for final marker task
- Cross-pipeline asset dependencies (consumed by acme-feeds)
"""
from polyris import DAG, task, Asset, Column, types as t
from polyris.config import config

# =============================================================================
# Test ARNs — replace with your actual Step Function ARNs
# =============================================================================
TEST_QUICK = "arn:aws:states:us-east-1:123456789012:stateMachine:test"
TEST_FAIL  = "arn:aws:states:us-east-1:123456789012:stateMachine:test-fail"

# =============================================================================
# Assets - Raw (extracted from source)
#
# Raw assets carry minimal structure: an external ID, the raw scraped payload,
# and extraction-time metadata. The payload is JSON because the upstream source
# returns nested data that we don't unpack until staging. Partitioned by
# `event_date` so we can re-run a single day without rewriting history.
# =============================================================================
listings_raw = Asset(
    "acme/listings_raw",
    extra={"type": "scraped"},
    schema=[
        Column("listing_id",   t.string(),   primary_key=True, nullable=False, description="Source-side listing identifier"),
        Column("payload",      t.json_(),     nullable=False,                   description="Raw scraped JSON from source API"),
        Column("source_url",   t.string(),                                     description="URL the listing was scraped from"),
        Column("scraped_at",   t.timestamp(), nullable=False,                  description="When the scrape executed"),
        Column("event_date",   t.date(),     partition_key=True, nullable=False),
    ],
)
catalog_raw = Asset(
    "acme/catalog_raw",
    extra={"type": "scraped"},
    schema=[
        Column("sku",          t.string(),   primary_key=True, nullable=False, description="Source SKU"),
        Column("payload",      t.json_(),     nullable=False,                   description="Raw catalog entry"),
        Column("scraped_at",   t.timestamp(), nullable=False),
        Column("event_date",   t.date(),     partition_key=True, nullable=False),
    ],
)
metrics_raw = Asset(
    "acme/metrics_raw",
    extra={"type": "scraped"},
    schema=[
        Column("metric_id",    t.string(),   primary_key=True, nullable=False),
        Column("payload",      t.json_(),     nullable=False,                   description="Raw numeric metrics blob"),
        Column("scraped_at",   t.timestamp(), nullable=False),
        Column("event_date",   t.date(),     partition_key=True, nullable=False),
    ],
)

# =============================================================================
# Assets - Staging (cleaned / validated)
#
# Staging unpacks the raw JSON into typed columns. Same partition convention
# as raw. Constraints get tightened — what's NOT NULL here is "we promise it
# survived validation"; raw payloads can be partial, staging is the contract.
# =============================================================================
listings_staging = Asset(
    "acme/listings_staging",
    schema=[
        Column("listing_id",   t.string(),    primary_key=True, nullable=False),
        Column("title",        t.string(),    nullable=False,                   description="Listing title"),
        Column("vendor_name",  t.varchar(200), nullable=False,                  description="Raw vendor name as scraped"),
        Column("price",        t.decimal(12, 2),                                description="Listed price; null if unavailable"),
        Column("currency",     t.char(3),                                       description="ISO-4217 currency code"),
        Column("scraped_at",   t.timestamp(), nullable=False),
        Column("event_date",   t.date(),      partition_key=True, nullable=False),
    ],
)
catalog_staging = Asset(
    "acme/catalog_staging",
    schema=[
        Column("sku",          t.string(),    primary_key=True, nullable=False),
        Column("name",         t.string(),    nullable=False),
        Column("category",     t.varchar(100)),
        Column("brand",        t.varchar(100)),
        Column("unit_size",    t.decimal(10, 3),                                description="Pack size in base units (kg, l, ...)"),
        Column("unit",         t.varchar(8),                                    description="kg | g | l | ml | ea"),
        Column("event_date",   t.date(),      partition_key=True, nullable=False),
    ],
)
metrics_staging = Asset(
    "acme/metrics_staging",
    schema=[
        Column("metric_id",    t.string(),    primary_key=True, nullable=False),
        Column("region",       t.varchar(8),  nullable=False,                   description="ISO 3166-1 alpha-2 (or region code)"),
        Column("store_id",     t.string(),                                      description="POS/store identifier; null for region-level metrics"),
        Column("metric_name",  t.varchar(64), nullable=False),
        Column("metric_value", t.double(),    nullable=False),
        Column("event_date",   t.date(),      partition_key=True, nullable=False),
    ],
)

# =============================================================================
# Assets - Derived
#
# Derived assets are the ones analysts and downstream pipelines query. They
# carry the richest typing: PKs, FK-style references, descriptions, and
# realistic catalog-grade types (decimal for money, date for partitions).
# =============================================================================

# product_details — backed by an actual Glue table so drift detection runs.
# `glue_table="test.example"` references the `test` database (visible in
# your Athena query editor) and the `example` table within it. Format is
# `<database>.<table>` — the Glue Data Catalog itself is implicit (your
# AWS account, in the same region as the Console API Lambda). Use
# `glue_catalog="<account-id>"` for cross-account references and
# `glue_region="<region>"` for cross-region.
#
# Drift detection will compare the schema declared below against the
# columns of `test.example` in Glue — for the screenshot's example
# (id INT, name STRING, price DOUBLE) the diff will surface:
#   - all columns from the declaration as "missing in Glue"
#   - id, name, price as "extra in Glue"
# which is the expected outcome since this is a placeholder mapping.
product_details = Asset(
    "acme/product_details",
    description="Master product catalog — one row per SKU, joined with normalized vendor and category data.",
    glue_table="test.example",
    schema=[
        Column("sku",            t.string(),     primary_key=True, nullable=False, description="Product SKU (matches catalog_staging.sku)"),
        Column("name",           t.string(),     nullable=False,                   description="Product display name"),
        Column("vendor_id",      t.bigint(),                                       description="FK → vendor_normalization.vendor_id"),
        Column("category",       t.varchar(100),                                   description="Top-level category"),
        Column("subcategory",    t.varchar(100)),
        Column("brand",          t.varchar(100)),
        Column("unit_size",      t.decimal(10, 3),                                 description="Pack size in base units"),
        Column("unit",           t.varchar(8),                                     description="kg | g | l | ml | ea"),
        Column("price_current",  t.decimal(12, 2),                                 description="Latest observed price"),
        Column("currency",       t.char(3),                                        description="ISO-4217"),
        Column("first_seen_at",  t.timestamp(),  nullable=False),
        Column("last_seen_at",   t.timestamp(),  nullable=False),
        Column("event_date",     t.date(),       partition_key=True, nullable=False),
    ],
)
vendor_normalization = Asset(
    "acme/vendor_normalization",
    description="Canonical vendor identity — maps raw vendor strings to a stable vendor_id.",
    schema=[
        Column("vendor_id",      t.bigint(),     primary_key=True, nullable=False),
        Column("canonical_name", t.varchar(200), nullable=False, unique=True),
        Column("aliases",        t.array(t.string()),                              description="All raw spellings observed"),
        Column("country",        t.char(2),                                        description="ISO 3166-1 alpha-2"),
        Column("created_at",     t.timestamp(),  nullable=False),
    ],
)
vendor_matching = Asset(
    "acme/vendor_matching",
    description="Per-product vendor resolution result.",
    schema=[
        Column("sku",            t.string(),     primary_key=True, nullable=False),
        Column("vendor_id",      t.bigint(),     nullable=False),
        Column("match_score",    t.double(),     nullable=False, description="0.0–1.0 confidence"),
        Column("match_method",   t.varchar(32),                  description="exact | fuzzy | ml | manual"),
        Column("event_date",     t.date(),       partition_key=True, nullable=False),
    ],
)
attribute_tags = Asset(
    "acme/attribute_tags",
    description="Attribute tags extracted from listing copy (category, claims, certifications).",
    schema=[
        Column("sku",            t.string(),     nullable=False),
        Column("tag_namespace",  t.varchar(32),  nullable=False, description="category | claim | certification"),
        Column("tag_value",      t.varchar(100), nullable=False),
        Column("confidence",     t.double()),
        Column("event_date",     t.date(),       partition_key=True, nullable=False),
    ],
)
release_dates = Asset(
    "acme/release_dates",
    description="Product availability windows derived from catalog history.",
    schema=[
        Column("sku",            t.string(),     primary_key=True, nullable=False),
        Column("first_release",  t.date()),
        Column("last_release",   t.date()),
        Column("availability_window_days", t.integer()),
        Column("event_date",     t.date(),       partition_key=True, nullable=False),
    ],
)
product_measures = Asset(
    "acme/product_measures",
    description="Numerical product features (size, weight, density) joined with release dates.",
    schema=[
        Column("sku",            t.string(),     primary_key=True, nullable=False),
        Column("net_weight_g",   t.decimal(10, 2)),
        Column("gross_weight_g", t.decimal(10, 2)),
        Column("volume_ml",      t.decimal(10, 2)),
        Column("density",        t.double(),                                      description="Computed when both weight & volume are present"),
        Column("event_date",     t.date(),       partition_key=True, nullable=False),
    ],
)
sales_raw = Asset(
    "acme/sales_raw",
    description="Sales aggregation, raw — pre-corrections.",
    schema=[
        Column("sku",            t.string(),     nullable=False),
        Column("region",         t.varchar(8),   nullable=False),
        Column("units_sold",     t.bigint(),     nullable=False),
        Column("revenue",        t.decimal(14, 2), nullable=False),
        Column("currency",       t.char(3),      nullable=False),
        Column("event_date",     t.date(),       partition_key=True, nullable=False),
    ],
)
sales_clean = Asset(
    "acme/sales_clean",
    description="Sales after outlier removal and corrections; the canonical source for downstream sales analytics.",
    schema=[
        Column("sku",            t.string(),     nullable=False),
        Column("region",         t.varchar(8),   nullable=False),
        Column("units_sold",     t.bigint(),     nullable=False),
        Column("revenue",        t.decimal(14, 2), nullable=False),
        Column("currency",       t.char(3),      nullable=False),
        Column("correction_flag", t.varchar(32),                                  description="null | outlier_removed | revenue_corrected"),
        Column("event_date",     t.date(),       partition_key=True, nullable=False),
    ],
)
distribution_data = Asset(
    "acme/distribution_data",
    description="Per-SKU distribution coverage across regions and stores.",
    schema=[
        Column("sku",            t.string(),     nullable=False),
        Column("region",         t.varchar(8),   nullable=False),
        Column("store_count",    t.integer(),    nullable=False),
        Column("coverage_pct",   t.double(),                                      description="0.0–1.0 share of regional stores"),
        Column("event_date",     t.date(),       partition_key=True, nullable=False),
    ],
)
quality_flags = Asset(
    "acme/quality_flags",
    description="Per-SKU data-quality flags for dashboard validation.",
    schema=[
        Column("sku",            t.string(),     primary_key=True, nullable=False),
        Column("has_price",      t.boolean(),    nullable=False),
        Column("has_sales",      t.boolean(),    nullable=False),
        Column("has_distribution", t.boolean(),  nullable=False),
        Column("flag_count",     t.integer(),    nullable=False),
        Column("event_date",     t.date(),       partition_key=True, nullable=False),
    ],
)
classification_result = Asset(
    "acme/classification_result",
    description="Output of the product classification ML model.",
    schema=[
        Column("sku",            t.string(),     primary_key=True, nullable=False),
        Column("predicted_class", t.varchar(64), nullable=False),
        Column("confidence",     t.double(),     nullable=False),
        Column("model_version",  t.varchar(32),  nullable=False),
        Column("predicted_at",   t.timestamp(),  nullable=False),
        Column("event_date",     t.date(),       partition_key=True, nullable=False),
    ],
)

# =============================================================================
# Assets - Views (lineage only, not materialized by this pipeline)
# =============================================================================
product_measures_view      = Asset("acme/product_measures_view",  extra={"type": "athena_view"})
locations_view             = Asset("acme/locations_view",         extra={"type": "athena_view"})
platform_customers         = Asset("acme/platform_customers",     extra={"type": "static_table"})
unclassified_products_view = Asset("acme/unclassified_products",  extra={"type": "athena_view"})
classification_view        = Asset("acme/classification_view",    extra={"type": "athena_view"})

# Final
daily_complete = Asset("acme/daily-complete")

# =============================================================================
# Pipeline
# =============================================================================
with DAG(
    dag_id="acme-daily",
    schedule="@daily",
    group="acme",
    description="Acme daily ETL pipeline — extract, stage, transform"
) as dag:

    # Extract (skip on backfill — source unavailable for past dates)
    @task.sfn(arn=TEST_QUICK, outlets=[listings_raw], skip_on_backfill=True)
    def extract_listings():
        """Extract product listings from Acme source."""
        pass

    @task.sfn(arn=TEST_QUICK, outlets=[catalog_raw], skip_on_backfill=True)
    def extract_catalog():
        """Extract product catalog from Acme source."""
        pass

    @task.sfn(arn=TEST_QUICK, outlets=[metrics_raw], skip_on_backfill=True)
    def extract_metrics():
        """Extract numerical metrics from Acme source."""
        pass

    # Stage
    @task.sfn(arn=TEST_QUICK, inlets=[listings_raw], outlets=[listings_staging])
    def stage_listings():
        """Validate and clean listings raw data."""
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[catalog_raw], outlets=[catalog_staging])
    def stage_catalog():
        """Validate and clean catalog raw data."""
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[metrics_raw], outlets=[metrics_staging])
    def stage_metrics():
        """Validate and clean metrics raw data."""
        pass

    # Transform: listings
    @task.sfn(arn=TEST_QUICK, inlets=[listings_staging], outlets=[product_details])
    def build_product_details():
        """Build product details table."""
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[listings_staging], outlets=[vendor_normalization])
    def normalize_vendors():
        """Normalize vendor names across sources."""
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[product_details], outlets=[vendor_matching])
    def match_vendors():
        """Match vendors across data sources."""
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[listings_staging], outlets=[attribute_tags])
    def tag_attributes():
        """Tag product attributes (category, brand, claims)."""
        pass

    # Transform: catalog
    @task.sfn(arn=TEST_QUICK, inlets=[catalog_staging], outlets=[release_dates])
    def build_release_dates():
        """Extract product release dates and availability windows."""
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[release_dates], outlets=[product_measures, product_measures_view])
    def build_product_measures():
        """Build product measures table and Athena view."""
        pass

    # Transform: metrics
    @task.sfn(arn=TEST_QUICK, inlets=[metrics_staging], outlets=[sales_raw])
    def build_sales_raw():
        """Build raw sales aggregation."""
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[sales_raw], outlets=[sales_clean])
    def build_sales_clean():
        """Apply corrections and outlier removal to sales data."""
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[metrics_staging], outlets=[distribution_data, locations_view])
    def build_distribution():
        """Build distribution coverage table and locations view."""
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[metrics_staging, sales_clean], outlets=[quality_flags])
    def build_quality_flags():
        """Compute data quality flags for dashboard validation."""
        pass

    # Classify (TEST_FAIL — demonstrates error handling)
    @task.sfn(
        arn=TEST_FAIL,
        inlets=[product_details, platform_customers, unclassified_products_view, classification_view],
        outlets=[classification_result]
    )
    def run_classification_model():
        """Run product classification model (WILL FAIL — for testing)."""
        pass

    # Final marker
    @task.sfn(
        arn=TEST_QUICK,
        inlets=[
            vendor_matching, vendor_normalization, attribute_tags,
            product_measures, sales_clean, distribution_data,
            quality_flags, classification_result,
        ],
        outlets=[daily_complete],
        trigger_rule="all_done"
    )
    def mark_daily_complete():
        """Mark daily pipeline complete (runs regardless of upstream status)."""
        pass

    # Wire dependencies
    lst   = extract_listings()
    cat   = extract_catalog()
    num   = extract_metrics()

    lst_s = stage_listings(lst)
    cat_s = stage_catalog(cat)
    num_s = stage_metrics(num)

    prod    = build_product_details(lst_s)
    v_norm  = normalize_vendors(lst_s)
    v_match = match_vendors(prod)
    attrs   = tag_attributes(lst_s)

    rel    = build_release_dates(cat_s)
    p_meas = build_product_measures(rel)

    s_raw   = build_sales_raw(num_s)
    s_clean = build_sales_clean(s_raw)
    dist    = build_distribution(num_s)
    quality = build_quality_flags([num_s, s_clean])

    clf = run_classification_model(prod)

    mark_daily_complete([v_match, v_norm, attrs, p_meas, s_clean, dist, quality, clf])

# Deploy: polyris-deploy
