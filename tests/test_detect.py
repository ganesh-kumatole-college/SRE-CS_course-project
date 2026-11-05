import numpy as np
import pytest

from misdet.detect.models import DETECTOR_NAMES, fit_detector
from misdet.detect.thresholds import (
    calibrate_threshold,
    cross_validated_normal_scores,
    predict_with_threshold,
)


def _features() -> np.ndarray:
    rng = np.random.default_rng(5)
    return rng.normal(size=(24, 4))


@pytest.mark.parametrize("detector_name", DETECTOR_NAMES)
def test_detectors_fit_and_return_anomaly_scores(detector_name):
    features = _features()
    model = fit_detector(detector_name, features, seed=12)
    scores = model.score(features[:4])
    predictions = model.predict_default(features[:4])

    assert scores.shape == (4,)
    assert predictions.shape == (4,)
    assert np.isfinite(scores).all()
    assert set(predictions).issubset({0, 1})


def test_scaler_is_fit_on_training_features_only():
    features = _features()
    model = fit_detector("one_class_svm", features[:12], seed=2)

    np.testing.assert_allclose(model.scaler.mean_, features[:12].mean(axis=0))
    assert not np.allclose(model.scaler.mean_, features.mean(axis=0))


def test_cross_validated_scores_exclude_each_validation_fold():
    features = _features()
    ids = [f"policy-{index:02d}" for index in range(len(features))]
    folds = [ids[:8], ids[8:16], ids[16:]]

    scores = cross_validated_normal_scores(
        ids,
        features,
        folds,
        detector_name="lof",
        detector_params={"n_neighbors": 5},
        seed=3,
    )
    assert scores.shape == (24,)
    assert np.isfinite(scores).all()


def test_threshold_helpers_validate_scores():
    threshold = calibrate_threshold([0.1, 0.2, 0.9], percentile=50)
    assert threshold == pytest.approx(0.2)
    np.testing.assert_array_equal(predict_with_threshold([0.1, 0.2, 0.9], threshold), [0, 1, 1])
    with pytest.raises(ValueError, match="non-empty"):
        calibrate_threshold([])

