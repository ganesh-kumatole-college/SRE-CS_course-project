"""Policy and organization templates for the synthetic benchmark."""

from __future__ import annotations

from typing import Any

ORGANIZATION_PROFILES: dict[str, dict[str, Any]] = {
    "alpha": {
        "name": "alpha",
        "description": "small production organization with guarded admin groups",
        "roles": ["prod-readers", "prod-owners", "security-ops"],
        "positive_operators": {"P1": "prod-readers", "A3": "security-ops"},
    },
    "beta": {
        "name": "beta",
        "description": "regional operations org with contractor-heavy services",
        "roles": ["ops-analysts", "ops-owners", "contractors"],
        "positive_operators": {"P2": "ops-owners", "A3": "contractors"},
    },
    "gamma": {
        "name": "gamma",
        "description": "research org with mixed admin and data-access roles",
        "roles": ["research-users", "data-science", "external-analysts"],
        "positive_operators": {"P1": "research-users", "A3": "external-analysts"},
    },
}

POLICY_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "prod_read": {
        "Action": ["s3:getobject", "ec2:describeinstances"],
        "Resource": ["arn:aws:s3:::alpha-prod/*", "arn:aws:ec2:*:*:instance/*"],
    },
    "prod_write": {
        "Action": ["s3:putobject", "s3:deleteobject", "iam:createuser"],
        "Resource": ["arn:aws:s3:::alpha-prod/*", "arn:aws:iam::*:user/*"],
    },
    "ops_read": {
        "Action": ["logs:describelogstreams", "lambda:listfunctions"],
        "Resource": ["arn:aws:logs:*:*:*", "arn:aws:lambda:*:*:function:*"],
    },
    "ops_write": {
        "Action": ["iam:*", "ec2:runinstances"],
        "Resource": ["arn:aws:iam::*:role/*", "arn:aws:ec2:*:*:instance/*"],
    },
    "data_read": {
        "Action": ["athena:batchgetqueryexecution", "s3:getobject"],
        "Resource": ["arn:aws:s3:::gamma-data/*", "arn:aws:athena:*:*:workgroup/*"],
    },
    "research_admin": {
        "Action": ["iam:*", "s3:*"],
        "Resource": ["arn:aws:s3:::gamma-data/*", "arn:aws:iam::*:role/*"],
    },
    "hard_negative": {
        "Action": ["ec2:describeinstances", "logs:getlogevents"],
        "Resource": ["arn:aws:ec2:*:*:instance/*", "arn:aws:logs:*:*:log-group:*"],
    },
}
