"""Assets — cross-pipeline lineage and asset-triggered runs (EXPERIMENTAL).

⚠️  Assets are experimental (v0.93.0): the API may change, and the visual asset
    console is not in the open-source build yet (engine + CLI lineage only).

This pipeline consumes `clean/orders` — the asset **produced by the
`11_assets_basic` pipeline** — and produces `analytics/orders_daily`. Because the
two pipelines share an Asset by name, Polyris links them into one lineage graph:

    (orders-clean)  extract -> transform --produces--> clean/orders
                                                            |
    (orders-analytics)                        reads <------+
                                              aggregate --produces--> analytics/orders_daily

Instead of a timer, this DAG is **triggered by the asset**: `schedule=[clean_orders]`
means "run whenever clean/orders is updated." Scheduling options:

    schedule=my_asset            run when that asset updates
    schedule=[a, b]              run when BOTH a and b are ready (AND)
    schedule=[a & b]             explicit AND
    schedule=[a | b]             run when EITHER updates (OR)

Run it locally (no AWS):  polyris-output --graph
"""
import warnings
import polyris
from polyris import DAG, task, Asset

warnings.filterwarnings("ignore", category=polyris.ExperimentalWarning)

# NOTE: placeholder ARN — replace with your own state machine before deploying.
ARN = "arn:aws:states:us-east-1:000000000000:stateMachine:polyris-test-sfn"

# Same asset name as produced in 11_assets_basic — this is what links the lineage.
clean_orders = Asset("clean/orders", uri="s3://polyris-example/clean/orders/", group="processed")
orders_daily = Asset("analytics/orders_daily", uri="s3://polyris-example/analytics/orders_daily/", group="aggregated")

with DAG(
    dag_id="orders-analytics",
    schedule=[clean_orders],   # asset-triggered: runs when clean/orders updates
    description="Aggregate clean orders into a daily analytics asset (asset-triggered).",
) as dag:

    @task.sfn(arn=ARN, inlets=[clean_orders], outlets=[orders_daily])
    def aggregate():
        """Read clean/orders, write the daily analytics asset."""
        pass

    aggregate()
