"""Optional DP noise on FedAvg updates — ablation only, not a formal guarantee."""

from __future__ import annotations

import numpy as np


def clip_and_noise(
    weights: np.ndarray,
    clip_norm: float,
    noise_sigma: float,
    rng: np.random.Generator,
) -> np.ndarray:
    norm = float(np.linalg.norm(weights))
    if norm > clip_norm > 0:
        weights = weights * (clip_norm / norm)
    if noise_sigma > 0:
        weights = weights + rng.normal(0.0, noise_sigma, size=weights.shape)
    return weights
