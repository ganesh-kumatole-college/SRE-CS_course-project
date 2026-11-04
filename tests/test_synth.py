import csv
import json
from collections import Counter

from misdet.synth.generator import generate_attachments, generate_benchmark, write_benchmark
from misdet.synth.labels import LABEL_COLUMNS, build_label_rows


def test_generate_benchmark_is_deterministic():
    first = generate_benchmark(seed=7)
    second = generate_benchmark(seed=7)

    assert first["seed"] == 7
    assert first["org_profiles"].keys() == second["org_profiles"].keys()
    assert first["policies"] == second["policies"]
    assert first["labels"] == second["labels"]
    assert first["attachments"] == second["attachments"]


def test_generate_benchmark_builds_expected_artifacts():
    benchmark = generate_benchmark(seed=7)

    assert len(benchmark["policies"]) == 1140
    assert len(benchmark["entities"]) == 9
    assert len(benchmark["attachments"]) == 1140
    assert len(benchmark["labels"]) == 1140
    assert {row["policy_id"] for row in benchmark["labels"]} == {
        policy["policy_id"] for policy in benchmark["policies"]
    }
    assert {row["org"] for row in benchmark["labels"]} == {"alpha", "beta", "gamma"}

    labels_by_org: dict[str, list[dict[str, str | int]]] = {}
    for row in benchmark["labels"]:
        labels_by_org.setdefault(row["org"], []).append(row)
    for rows in labels_by_org.values():
        assert Counter(row["label"] for row in rows) == {0: 350, 1: 30}

    positive_labels = [row for row in benchmark["labels"] if row["label"] == 1]
    assert {row["operator_id"] for row in positive_labels} == {"P1", "P2", "A3"}

    policy_by_id = {policy["policy_id"]: policy for policy in benchmark["policies"]}
    label_by_id = {row["policy_id"]: row for row in benchmark["labels"]}
    base_attachments = {
        row["policy_id"]: row["entity_id"]
        for row in generate_attachments(
            benchmark["policies"],
            benchmark["entities"],
            seed=7,
        )
    }
    for row in benchmark["labels"]:
        statement = policy_by_id[row["policy_id"]]["document"]["Statement"][0]
        if row["label"] == 0:
            assert "Condition" not in statement
        else:
            assert "Condition" in statement
            if row["operator_id"] == "P1":
                assert statement["Action"] == ["s3:getobject", "s3:listbucket"]
            elif row["operator_id"] == "P2":
                assert statement["Action"] == ["iam:*"]
                assert statement["Resource"] == ["*"]
            else:
                assert row["operator_id"] == "A3"
                assert row["attached_entity_id"] != base_attachments[row["policy_id"]]

    assert Counter(row["misconfig_type"] for row in positive_labels) == {
        "permissive": 45,
        "misattached": 45,
    }

    for org in labels_by_org:
        normal_documents = {
            json.dumps(
                {
                    "Effect": policy["document"]["Statement"][0]["Effect"],
                    "Action": policy["document"]["Statement"][0]["Action"],
                    "Resource": policy["document"]["Statement"][0]["Resource"],
                },
                sort_keys=True,
            )
            for policy in benchmark["policies"]
            if policy["org"] == org
            and label_by_id[policy["policy_id"]]["label"] == 0
        }
        assert len(normal_documents) >= 3


def test_write_benchmark_emits_csv_and_jsonl(tmp_path):
    benchmark = generate_benchmark(seed=9)
    paths = write_benchmark(tmp_path, benchmark)

    assert paths["policies"].exists()
    assert paths["entities"].exists()
    assert paths["attachments"].exists()
    assert paths["labels"].exists()

    with paths["labels"].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert list(rows[0].keys()) == LABEL_COLUMNS


def test_build_label_rows_rejects_non_list():
    try:
        build_label_rows({"oops": "not-a-list"})
    except ValueError:
        return
    raise AssertionError("malformed policy input should raise ValueError")


def test_build_label_rows_uses_applied_operator_mapping():
    policies = [
        {"policy_id": "normal", "org": "alpha", "document": {}},
        {"policy_id": "permissive", "org": "alpha", "document": {}},
        {"policy_id": "second-permissive", "org": "alpha", "document": {}},
        {"policy_id": "misattached", "org": "alpha", "document": {}},
    ]

    rows = build_label_rows(
        policies,
        operator_by_policy_id={
            "permissive": "P1",
            "second-permissive": "P2",
            "misattached": "A3",
        },
    )

    assert [(row["policy_id"], row["label"], row["operator_id"]) for row in rows] == [
        ("normal", 0, "none"),
        ("permissive", 1, "P1"),
        ("second-permissive", 1, "P2"),
        ("misattached", 1, "A3"),
    ]
