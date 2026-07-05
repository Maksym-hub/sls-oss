"""Shopmart Daily Pipeline.

Extracts data from the Shopmart retail source and transforms into analytical assets.
Runs daily via EventBridge schedule.

This pipeline demonstrates:
- Same ETL pattern as acme-daily (extract → stage → transform)
- Multiple parallel extraction tasks
- Asset-based lineage across the full pipeline
"""
from polyris import DAG, task, Asset

TEST_QUICK = "arn:aws:states:us-east-1:123456789012:stateMachine:test"
TEST_FAIL  = "arn:aws:states:us-east-1:123456789012:stateMachine:test-fail"

# Raw
listings_raw = Asset("shopmart/listings_raw", extra={"type": "scraped"})
catalog_raw  = Asset("shopmart/catalog_raw",  extra={"type": "scraped"})
metrics_raw  = Asset("shopmart/metrics_raw",  extra={"type": "scraped"})

# Staging
listings_staging = Asset("shopmart/listings_staging")
catalog_staging  = Asset("shopmart/catalog_staging")
metrics_staging  = Asset("shopmart/metrics_staging")

# Derived
product_details      = Asset("shopmart/product_details")
vendor_normalization = Asset("shopmart/vendor_normalization")
vendor_matching      = Asset("shopmart/vendor_matching")
attribute_tags       = Asset("shopmart/attribute_tags")
release_dates        = Asset("shopmart/release_dates")
product_measures     = Asset("shopmart/product_measures")
sales_raw            = Asset("shopmart/sales_raw")
sales_clean          = Asset("shopmart/sales_clean")
distribution_data    = Asset("shopmart/distribution_data")
quality_flags        = Asset("shopmart/quality_flags")
classification_result = Asset("shopmart/classification_result")

# Views
product_measures_view      = Asset("shopmart/product_measures_view",  extra={"type": "athena_view"})
locations_view             = Asset("shopmart/locations_view",         extra={"type": "athena_view"})
platform_customers         = Asset("shopmart/platform_customers",     extra={"type": "static_table"})
unclassified_products_view = Asset("shopmart/unclassified_products",  extra={"type": "athena_view"})
classification_view        = Asset("shopmart/classification_view",    extra={"type": "athena_view"})

daily_complete = Asset("shopmart/daily-complete")

with DAG(
    dag_id="shopmart-daily",
    schedule="@daily",
    group="shopmart",
    description="Shopmart daily ETL pipeline"
) as dag:

    @task.sfn(arn=TEST_QUICK, outlets=[listings_raw])
    def extract_listings():
        """Extract product listings from Shopmart source."""
        pass

    @task.sfn(arn=TEST_QUICK, outlets=[catalog_raw])
    def extract_catalog():
        """Extract product catalog from Shopmart source."""
        pass

    @task.sfn(arn=TEST_QUICK, outlets=[metrics_raw])
    def extract_metrics():
        """Extract numerical metrics from Shopmart source."""
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[listings_raw], outlets=[listings_staging])
    def stage_listings():
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[catalog_raw], outlets=[catalog_staging])
    def stage_catalog():
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[metrics_raw], outlets=[metrics_staging])
    def stage_metrics():
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[listings_staging], outlets=[product_details])
    def build_product_details():
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[listings_staging], outlets=[vendor_normalization])
    def normalize_vendors():
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[product_details], outlets=[vendor_matching])
    def match_vendors():
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[listings_staging], outlets=[attribute_tags])
    def tag_attributes():
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[catalog_staging], outlets=[release_dates])
    def build_release_dates():
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[release_dates], outlets=[product_measures, product_measures_view])
    def build_product_measures():
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[metrics_staging], outlets=[sales_raw])
    def build_sales_raw():
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[sales_raw], outlets=[sales_clean])
    def build_sales_clean():
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[metrics_staging], outlets=[distribution_data, locations_view])
    def build_distribution():
        pass

    @task.sfn(arn=TEST_QUICK, inlets=[metrics_staging, sales_clean], outlets=[quality_flags])
    def build_quality_flags():
        pass

    @task.sfn(
        arn=TEST_FAIL,
        inlets=[product_details, platform_customers, unclassified_products_view, classification_view],
        outlets=[classification_result]
    )
    def run_classification_model():
        """Run classification model (WILL FAIL — for testing)."""
        pass

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
        pass

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
