import numpy as np
import pytest

from misdet.baselines.core import (
    HANDCRAFTED_FEATURE_NAMES,
    bag_of_actions_features,
    fit_bag_of_actions,
    handcrafted_features,
    prevalence_output,
    random_scores,
    rule_output,
    transform_bag_of_actions,
)
from misdet.experiments import run_baseline_comparison


def _policy(action=None, resource=None, **statement):
    effect = statement.pop("Effect", "Allow")
    action_field = {"Action": action or ["s3:getobject"]} if "NotAction" not in statement else {}
    resource_field = (
        {"Resource": resource or ["arn:aws:s3:::bucket/*"]}
        if "NotResource" not in statement
        else {}
    )
    row = {
        "policy_id": statement.pop("policy_id", "policy-1"),
        "document": {
            "Statement": [
                {
                    "Effect": effect,
                    **action_field,
                    **resource_field,
                    **statement,
                }
            ]
        },
    }
    return row


def test_rule_baselines_preserve_wildcard_and_negated_selector_semantics():
    policies = [
        _policy(action=["s3:getobject"], resource=["arn:aws:s3:::bucket/*"]),
        _policy(
            policy_id="policy-2",
            action=None,
            resource=None,
            NotAction=["iam:deleteuser"],
            NotResource=["arn:aws:iam::*:user/*"],
        ),
        _policy(
            policy_id="policy-3",
            action=["*"],
            resource=["*"],
            Effect="Deny",
        ),
    ]

    wildcard = rule_output(policies, name="wildcard")
    permissiveness = rule_output(policies, name="permissiveness")
    equivalent = rule_output(policies, name="offline_custodian_equivalent")

    np.testing.assert_array_equal(wildcard.predictions, [1, 1, 0])
    assert permissiveness.scores[1] == permissiveness.scores[0]
    np.testing.assert_array_equal(equivalent.predictions, [0, 0, 0])


def test_handcrafted_features_have_stable_columns_and_finite_values():
    values = handcrafted_features([_policy(), _policy(policy_id="policy-2", Effect="Deny")])
    assert values.shape == (2, len(HANDCRAFTED_FEATURE_NAMES))
    assert np.isfinite(values).all()
    assert HANDCRAFTED_FEATURE_NAMES[0] == "statement_count"
    assert values[0, 1] == 1
    assert values[1, 2] == 1


def test_bag_of_actions_is_deterministic_and_can_transform_held_out_policies():
    policies = [
        _policy(policy_id="policy-1", action=["s3:GetObject", "s3:ListBucket"]),
        _policy(policy_id="policy-2", action=["iam:PassRole"]),
    ]
    first = bag_of_actions_features(policies)
    second = bag_of_actions_features(policies)
    np.testing.assert_array_equal(first, second)

    encoder = fit_bag_of_actions([policies[0]])
    held_out = transform_bag_of_actions([policies[1]], encoder)
    assert held_out.shape == (1, len(encoder.vocabulary_))
    assert np.isfinite(held_out).all()


def test_bag_of_actions_baseline_uses_the_shared_split(tmp_path):
    policies = [
        _policy(policy_id=f"policy-{index:02d}", action=["s3:GetObject"])
        for index in range(20)
    ]
    labels = [
        {"policy_id": policy["policy_id"], "label": int(index >= 16)}
        for index, policy in enumerate(policies)
    ]
    outputs = run_baseline_comparison(
        policies,
        labels,
        tmp_path / "runs",
        baseline_names=("handcrafted_feature", "bag_of_actions"),
        detector_name="one_class_svm",
        detector_params={"nu": 0.2},
        validation_folds=4,
        bootstrap_replicates=10,
        seed=3,
    )
    assert set(outputs) == {"handcrafted_feature", "bag_of_actions"}
    handcrafted_ids = (outputs["handcrafted_feature"] / "preds.csv").read_text().splitlines()[1:]
    bag_ids = (outputs["bag_of_actions"] / "preds.csv").read_text().splitlines()[1:]
    assert [row.split(",", 1)[0] for row in handcrafted_ids] == [
        row.split(",", 1)[0] for row in bag_ids
    ]


def test_random_and_prevalence_baselines_are_deterministic():
    np.testing.assert_array_equal(random_scores(4, seed=7), random_scores(4, seed=7))
    output = prevalence_output(3, [0, 0, 0])
    np.testing.assert_array_equal(output.scores, [0, 0, 0])
    np.testing.assert_array_equal(output.predictions, [0, 0, 0])


def test_baseline_comparison_shares_split_and_writes_metrics(tmp_path):
    policies = [
        _policy(policy_id=f"policy-{index:02d}", action=["s3:getobject"])
        for index in range(20)
    ]
    labels = [
        {
            "policy_id": policy["policy_id"],
            "label": int(index >= 16),
            "misconfig_type": "permissive" if index >= 16 else "none",
        }
        for index, policy in enumerate(policies)
    ]
    names = ("random", "prevalence", "wildcard", "permissiveness", "handcrafted_feature")
    outputs = run_baseline_comparison(
        policies,
        labels,
        tmp_path / "runs",
        baseline_names=names,
        detector_name="one_class_svm",
        detector_params={"nu": 0.2},
        validation_folds=4,
        bootstrap_replicates=10,
        seed=3,
    )

    assert tuple(outputs) == names
    test_ids = []
    for _name, output in outputs.items():
        assert {path.name for path in output.iterdir()} == {
            "config.yaml",
            "metrics.json",
            "preds.csv",
            "env.txt",
            "git_sha.txt",
        }
        with (output / "preds.csv").open(encoding="utf-8") as handle:
            rows = handle.readlines()
        current_ids = [line.split(",", 1)[0] for line in rows[1:]]
        test_ids.append(current_ids)
        assert '"pr_auc"' in (output / "metrics.json").read_text(encoding="utf-8")
    assert all(ids == test_ids[0] for ids in test_ids)

    with pytest.raises(FileExistsError):
        run_baseline_comparison(
            policies,
            labels,
            tmp_path / "runs",
            baseline_names=("random",),
            bootstrap_replicates=10,
            seed=3,
        )


@pytest.mark.parametrize(
    "policies",
    [
        [],
        [{"policy_id": "broken", "document": {}}],
        [{"policy_id": "broken", "document": {"Statement": [{"Effect": "Allow"}]}}],
    ],
)
def test_baselines_reject_empty_and_malformed_policies(policies):
    with pytest.raises((TypeError, ValueError)):
        handcrafted_features(policies)
