"""Common adapters for the required scikit-learn anomaly detectors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.covariance import EllipticEnvelope
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

DETECTOR_NAMES = ("lof", "one_class_svm", "isolation_forest", "robust_covariance")


@dataclass(frozen=True)
class DetectorConfig:
    """Resolved detector settings."""

    name: str = "lof"
    scale: bool = True
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class FittedDetector:
    """A fitted detector and its optional train-only feature scaler."""

    name: str
    estimator: Any
    scaler: StandardScaler | None

    def _transform(self, features: np.ndarray) -> np.ndarray:
        values = _validate_features(features)
        return self.scaler.transform(values) if self.scaler is not None else values

    def score(self, features: np.ndarray) -> np.ndarray:
        """Return finite anomaly scores where larger values are more anomalous."""
        values = self._transform(features)
        scores = -np.asarray(self.estimator.decision_function(values), dtype=float)
        if scores.ndim != 1 or not np.isfinite(scores).all():
            raise ValueError("detector produced invalid anomaly scores")
        return scores

    def predict_default(self, features: np.ndarray) -> np.ndarray:
        """Return the estimator's default binary predictions."""
        values = self._transform(features)
        predictions = (np.asarray(self.estimator.predict(values)) == -1).astype(int)
        return predictions


def _validate_features(features: np.ndarray) -> np.ndarray:
    values = np.asarray(features, dtype=float)
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] == 0:
        raise ValueError("features must be a non-empty two-dimensional array")
    if not np.isfinite(values).all():
        raise ValueError("features must contain only finite values")
    return values


def _build_estimator(name: str, params: Mapping[str, Any], seed: int) -> Any:
    if name == "lof":
        if params.get("novelty", True) is not True:
            raise ValueError("LOF must use novelty=True for unseen-policy scoring")
        return LocalOutlierFactor(**dict(params))
    if name == "one_class_svm":
        return OneClassSVM(**dict(params))
    if name == "isolation_forest":
        resolved = dict(params)
        resolved.setdefault("random_state", seed)
        return IsolationForest(**resolved)
    if name == "robust_covariance":
        resolved = dict(params)
        resolved.setdefault("random_state", seed)
        return EllipticEnvelope(**resolved)
    raise ValueError(f"unsupported detector {name!r}; expected one of {DETECTOR_NAMES}")


def fit_detector(
    name: str,
    train_features: np.ndarray,
    *,
    params: Mapping[str, Any] | None = None,
    scale: bool = True,
    seed: int = 42,
) -> FittedDetector:
    """Fit one detector on normal training features only."""
    values = _validate_features(train_features)
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError("seed must be an integer")
    resolved_params = dict(params or {})
    if name == "lof" and "novelty" not in resolved_params:
        resolved_params["novelty"] = True
    scaler = StandardScaler().fit(values) if scale else None
    transformed = scaler.transform(values) if scaler is not None else values
    estimator = _build_estimator(name, resolved_params, seed)
    try:
        estimator.fit(transformed)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"could not fit {name} on training features: {exc}") from exc
    return FittedDetector(name=name, estimator=estimator, scaler=scaler)
