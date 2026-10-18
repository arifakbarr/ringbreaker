"""L2 logistic regression — numpy/sklearn, no torch."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression


@dataclass
class LogisticModel:
    weights: np.ndarray
    bias: float
    version: str = "lr-v1"
    feature_mean: np.ndarray | None = None
    feature_std: np.ndarray | None = None

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        Xn = self._norm(X)
        z = Xn @ self.weights + self.bias
        return 1.0 / (1.0 + np.exp(-np.clip(z, -50, 50)))

    def _norm(self, X: np.ndarray) -> np.ndarray:
        if self.feature_mean is None or self.feature_std is None:
            return X
        return (X - self.feature_mean) / np.maximum(self.feature_std, 1e-6)

    def to_update(self, bank_id: str, round_i: int, n_samples: int) -> dict:
        return {
            "bank_id": bank_id,
            "round": round_i,
            "n_samples": n_samples,
            "weights": self.weights.tolist(),
            "bias": float(self.bias),
            "clip_norm": 0.0,
            "noise_sigma": 0.0,
        }


def train_local_logreg(
    X: np.ndarray,
    y: np.ndarray,
    *,
    class_weight: str | dict = "balanced",
    seed: int = 0,
) -> LogisticModel:
    if len(np.unique(y)) < 2:
        # Degenerate: return near-zero model
        return LogisticModel(
            weights=np.zeros(X.shape[1]),
            bias=-3.0,
            feature_mean=X.mean(axis=0),
            feature_std=X.std(axis=0) + 1e-6,
        )
    mean = X.mean(axis=0)
    std = X.std(axis=0) + 1e-6
    Xn = (X - mean) / std
    clf = LogisticRegression(
        penalty="l2",
        C=1.0,
        class_weight=class_weight,
        max_iter=500,
        random_state=seed,
        solver="lbfgs",
    )
    clf.fit(Xn, y)
    return LogisticModel(
        weights=clf.coef_.ravel().astype(np.float64),
        bias=float(clf.intercept_[0]),
        feature_mean=mean,
        feature_std=std,
    )


def calibrate_scores(
    model: LogisticModel,
    X: np.ndarray,
    y: np.ndarray,
    seed: int = 0,
) -> LogisticModel:
    """Optional Platt via sklearn wrapper on raw scores — keep weights, store bias shift lightly."""
    if len(np.unique(y)) < 2 or len(y) < 20:
        return model
    raw = model.predict_proba(X).reshape(-1, 1)
    # Recalibrate by fitting LR on raw score
    cal = LogisticRegression(max_iter=200, random_state=seed)
    cal.fit(raw, y)
    # Compose: new_score = sigmoid(a * old + b) — approximate by scaling weights
    a = float(cal.coef_.ravel()[0])
    b = float(cal.intercept_[0])
    return LogisticModel(
        weights=model.weights * a,
        bias=model.bias * a + b,
        version=model.version + "+platt",
        feature_mean=model.feature_mean,
        feature_std=model.feature_std,
    )


def threshold_at_fpr(scores: np.ndarray, y: np.ndarray, target_fpr: float = 0.005) -> float:
    """Choose score threshold so FPR on negatives ≈ target_fpr."""
    neg = scores[y == 0]
    if len(neg) == 0:
        return 0.5
    return float(np.quantile(neg, 1.0 - target_fpr))
