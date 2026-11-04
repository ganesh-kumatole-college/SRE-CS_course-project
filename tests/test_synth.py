import csv

from misdet.synth.generator import generate_benchmark, write_benchmark
from misdet.synth.labels import LABEL_COLUMNS, build_label_rows


def test_generate_benchmark_is_deterministic():
    first = generate_benchmark(seed=7)
    second = generate_benchmark(seed=7)

    assert first["seed"] == 7
    assert first["org_profiles"].keys() == second["org_profiles"].keys()
    assert first["policies"] == second["policies"]
    assert first["labels"] == second["labels"]


def test_generate_benchmark_builds_expected_artifacts():
    benchmark = generate_benchmark(seed=7)

    assert len(benchmark["policies"]) == 18
    assert len(benchmark["entities"]) == 9
    assert len(benchmark["attachments"]) == 18
    assert len(benchmark["labels"]) == 18
    assert {row["policy_id"] for row in benchmark["labels"]} == {
        policy["policy_id"] for policy in benchmark["policies"]
    }
    assert {row["org"] for row in benchmark["labels"]} == {"alpha", "beta", "gamma"}


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
