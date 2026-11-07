from pathlib import Path

import pytest

from misdet.experiments.config import load_config, resolve_config

CONFIG_DIR = Path(__file__).parents[1] / "configs" / "experiments"


@pytest.mark.parametrize("name", ["exp01", "exp02", "exp03", "exp04", "exp07", "exp13"])
def test_phase_nine_configs_resolve_to_thirty_ordered_seeds(name):
    config = load_config(CONFIG_DIR / f"{name}.yaml")

    assert config.exp_id == name
    assert config.seeds == tuple(range(30))
    assert config.split.protocol == "paper_90_10"
    assert config.bootstrap_replicates == 2000
    assert config.detector_grid == {} if name != "exp01" else "lof" in config.detector_grid


def test_config_resolves_relative_paths_from_project_root(tmp_path):
    raw = {
        "exp_id": "exp01",
        "orgs": ["S1"],
        "seeds": "0..29",
        "paths": {"input_root": "data/benchmark", "output_root": "results/runs"},
        "split": {"protocol": "paper_90_10"},
        "methods": ["node2vec"],
        "metrics": ["recall"],
    }

    config = resolve_config(raw, base_dir=tmp_path)

    assert config.input_root == (tmp_path / "data/benchmark").resolve()
    assert config.output_root == (tmp_path / "results/runs").resolve()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("seeds", [0, 0], "duplicates"),
        ("seeds", [1, 0], "ascending"),
        ("methods", ["not-a-method"], "unsupported"),
        ("detector", "not-a-detector", "unsupported"),
    ],
)
def test_config_rejects_invalid_contract_values(field, value, message):
    raw = {
        "exp_id": "exp01",
        "orgs": ["S1"],
        "seeds": "0..29",
        "split": {"protocol": "paper_90_10"},
        "methods": ["node2vec"],
        "metrics": ["recall"],
    }
    raw[field] = value

    with pytest.raises(ValueError, match=message):
        resolve_config(raw)


def test_config_rejects_duplicate_organizations():
    with pytest.raises(ValueError, match="orgs must not contain duplicates"):
        resolve_config(
            {
                "exp_id": "exp01",
                "orgs": ["S1", "S1"],
                "seeds": "0..29",
                "methods": ["node2vec"],
                "metrics": ["recall"],
            }
        )
