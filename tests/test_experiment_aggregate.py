from misdet.experiments.aggregate import aggregate_seed_metrics, grouped_recall


def test_aggregate_seed_metrics_reports_mean_sd_and_raw_counts():
    result = aggregate_seed_metrics(
        [
            {"precision": 0.5, "recall": 0.4, "confusion": {"tp": 2, "fp": 1, "fn": 3, "tn": 4}},
            {"precision": 0.7, "recall": None, "confusion": {"tp": 3, "fp": 0, "fn": 2, "tn": 5}},
        ],
        ("precision", "recall"),
    )

    assert result["precision"] == {"mean": 0.6, "sd": 0.14142135623730948, "count": 2}
    assert result["recall"] == {"mean": 0.4, "sd": 0.0, "count": 1}
    assert result["confusion"] == {"tp": 5, "fp": 1, "fn": 5, "tn": 9}


def test_grouped_recall_preserves_empty_requested_groups():
    rows = [
        {"operator_id": "P1", "label": 1, "score": 0.9, "pred": 1},
        {"operator_id": "P1", "label": 1, "score": 0.1, "pred": 0},
        {"operator_id": "none", "label": 0, "score": 0.2, "pred": 0},
    ]

    result = grouped_recall(
        rows,
        group_field="operator_id",
        groups=("P1", "P2"),
        bootstrap_replicates=20,
        seed=4,
    )

    assert result[0]["recall"] == 0.5
    assert result[0]["positive_count"] == 2
    assert result[0]["bootstrap_ci"] is not None
    assert result[1] == {
        "group": "P2",
        "count": 0,
        "positive_count": 0,
        "recall": None,
        "bootstrap_ci": None,
    }
