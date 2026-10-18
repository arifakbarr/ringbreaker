"""FedAvg coordinator (weighted by sample count)."""

from __future__ import annotations

import numpy as np

from ringbreaker.fed.models import LogisticModel


class FedAvgCoordinator:
    def __init__(self, n_features: int) -> None:
        self.global_model = LogisticModel(
            weights=np.zeros(n_features),
            bias=0.0,
            version="fed-r0",
        )
        self.round = 0

    def aggregate(self, updates: list[dict]) -> LogisticModel:
        if not updates:
            return self.global_model
        total = sum(u["n_samples"] for u in updates) or 1
        w = np.zeros_like(self.global_model.weights)
        b = 0.0
        for u in updates:
            frac = u["n_samples"] / total
            w = w + frac * np.asarray(u["weights"], dtype=np.float64)
            b = b + frac * float(u["bias"])
        self.round += 1
        self.global_model = LogisticModel(
            weights=w,
            bias=b,
            version=f"fed-r{self.round}",
            feature_mean=self.global_model.feature_mean,
            feature_std=self.global_model.feature_std,
        )
        return self.global_model

    def set_norm_stats(self, mean: np.ndarray, std: np.ndarray) -> None:
        self.global_model = LogisticModel(
            weights=self.global_model.weights,
            bias=self.global_model.bias,
            version=self.global_model.version,
            feature_mean=mean,
            feature_std=std,
        )
