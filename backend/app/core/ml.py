"""Classical ML re-ranker: a compact logistic-regression drug-likeness model.

Trained at startup (deterministically, in a few milliseconds) on an embedded
dataset of approved oral drugs (positives) and curated non-drug-like chemicals
(reactive, PAINS-like, industrial) — 11 RDKit descriptor features per molecule.
It is an honest, transparent illustration of the classical-ML re-ranking stage;
a production deployment would swap in a trained QSAR/ADMET ensemble.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .config import DATA_DIR

_FEATURES = [
    "mw", "logp", "tpsa", "hbd", "hba", "rotb",
    "aromatic_rings", "fraction_csp3", "heavy_atoms", "formal_charge", "esol_log_s",
]


class DruglikenessModel:
    def __init__(self, weights_path: Path | None = None):
        weights_path = weights_path or DATA_DIR / "ml_model.json"
        with open(weights_path, "r", encoding="utf-8") as fh:
            blob = json.load(fh)
        self.feature_names = blob["feature_names"]
        self._w = np.array(blob["weights"], dtype=float)
        self._b = float(blob["bias"])
        self._mu = np.array(blob["mean"], dtype=float)
        self._sigma = np.array(blob["std"], dtype=float)
        self.meta = blob.get("meta", {})

    def predict_proba(self, features: dict) -> float:
        x = np.array([float(features.get(k, 0.0)) for k in self.feature_names])
        z = ((x - self._mu) / self._sigma) @ self._w + self._b
        return float(1.0 / (1.0 + np.exp(-z)))

    @classmethod
    def train(cls, X: np.ndarray, y: np.ndarray, feature_names: list[str],
              lr: float = 0.08, epochs: int = 4000, l2: float = 1e-3,
              seed: int = 42) -> "DruglikenessModel":
        rng = np.random.default_rng(seed)
        mu, sigma = X.mean(axis=0), X.std(axis=0) + 1e-9
        Xs = (X - mu) / sigma
        n, d = Xs.shape
        w = rng.normal(0, 0.01, size=d)
        b = 0.0
        for _ in range(epochs):
            z = Xs @ w + b
            p = 1.0 / (1.0 + np.exp(-z))
            grad_w = Xs.T @ (p - y) / n + l2 * w
            grad_b = float(np.mean(p - y))
            w -= lr * grad_w
            b -= lr * grad_b
        model = cls.__new__(cls)
        model.feature_names = feature_names
        model._w = w
        model._b = b
        model._mu = mu
        model._sigma = sigma
        model.meta = {"trained_samples": int(n), "positives": int(y.sum())}
        return model

    def export(self) -> dict:
        return {
            "feature_names": self.feature_names,
            "weights": [round(v, 6) for v in self._w],
            "bias": round(self._b, 6),
            "mean": [round(v, 6) for v in self._mu],
            "std": [round(v, 6) for v in self._sigma],
            "meta": self.meta,
        }


def load_model() -> DruglikenessModel:
    return DruglikenessModel()
