"""
Pipeline configuration — project-level settings for polyris.

Defines per-stage environments (namespace, region, AWS profile, roles).
This file is auto-discovered by ``polyris.config`` at deploy/CLI time.

Customize the values below for your AWS account and org.

Usage in dag.py:
    from polyris.config import config

    config.namespace   # "myorg"
    config.stage       # "dev"
    config.region      # "us-east-1"
    config.roles       # {"acq": "arn:aws:iam::...", "etl": "arn:aws:iam::..."}

See docs/reference/CONFIGURATION.md for details.
"""

# =============================================================================
# Environments — one entry per deployment stage
# =============================================================================
ENVIRONMENTS = {
    "dev": {
        "namespace": "polyris-dev-oss",
        "stage": "dev",
        "region": "us-east-1",
        "account_id": "123456789012",
        # "profile": "my-dev-profile",      # optional: AWS CLI profile
        "roles": {
            "acq": "arn:aws:iam::333333333333:role/myorg-prod-sfn-execution-role",
            "etl": "arn:aws:iam::444444444444:role/myorg-etl-prod-cross-acc-pipeline",
        },
    },
    # "prod": {
    #     "namespace": "myorg",
    #     "stage": "prod",
    #     "region": "us-east-1",
    #     "account_id": "987654321098",
    #     "profile": "my-prod-profile",
    #     "roles": {
    #         "acq": "arn:aws:iam::333333333333:role/myorg-prod-sfn-execution-role",
    #         "etl": "arn:aws:iam::444444444444:role/myorg-etl-prod-cross-acc-pipeline",
    #     },
    # },
}

DEFAULT_STAGE = "dev"
