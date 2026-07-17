#!/usr/bin/env python3
"""Seed MLflow with a realistic MLOps demo: a fraud-scoring model.

Trains a few gradient-boosting variants on a synthetic (deterministic) dataset,
logs hyperparameters, metrics and the model artifact to MLflow, and registers the
best run in the MLflow Model Registry. This gives the MLflow UI concrete content
that demonstrates the platform's MLOps story (experiment tracking, model registry)
alongside the LLMOps features shown elsewhere.

Usage:  backend/.venv/bin/python scripts/seed_mlflow_demo.py
        (MLflow reachable at http://localhost:5001 — see docker-compose)
"""

import os
import tempfile

import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5001")
EXPERIMENT = "fraud-scoring"


def _dataset(seed: int = 42) -> tuple:
    """Deterministic synthetic transaction dataset (no external data needed)."""
    rng = np.random.default_rng(seed)
    n = 6000
    # Features: amount, hour, num_countries_24h, device_age_days, velocity
    x = rng.normal(0, 1, size=(n, 5))
    # Fraud signal: high amount + high velocity + many countries, with noise.
    logits = 1.4 * x[:, 0] + 1.1 * x[:, 4] + 0.9 * x[:, 2] - 0.6 * x[:, 3]
    proba = 1 / (1 + np.exp(-logits))
    y = (proba > rng.uniform(0.55, 0.95, size=n)).astype(int)
    return train_test_split(x, y, test_size=0.25, random_state=seed)


def main() -> int:
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT)
    x_train, x_test, y_train, y_test = _dataset()

    grid = [
        {"n_estimators": 80, "max_depth": 2, "learning_rate": 0.10},
        {"n_estimators": 150, "max_depth": 3, "learning_rate": 0.08},
        {"n_estimators": 250, "max_depth": 3, "learning_rate": 0.05},
    ]

    best = {"auc": 0.0, "run_id": None, "params": None}
    for i, params in enumerate(grid, start=1):
        with mlflow.start_run(run_name=f"gbc-v{i}") as run:
            model = GradientBoostingClassifier(random_state=42, **params)
            model.fit(x_train, y_train)
            proba = model.predict_proba(x_test)[:, 1]
            preds = (proba >= 0.5).astype(int)
            metrics = {
                "auc": float(roc_auc_score(y_test, proba)),
                "precision": float(precision_score(y_test, preds, zero_division=0)),
                "recall": float(recall_score(y_test, preds, zero_division=0)),
                "f1": float(f1_score(y_test, preds, zero_division=0)),
            }
            mlflow.log_params(params)
            mlflow.log_metrics(metrics)
            mlflow.set_tags({
                "use_case": "banking / transaction fraud",
                "risk_level": "high",
                "framework": "scikit-learn",
                "owner": "Hadirou Tamdamba",
            })
            # Log the model as a classic artifact (compatible across MLflow
            # client/server versions) rather than the newer logged-models API.
            with tempfile.TemporaryDirectory() as tmp:
                model_dir = os.path.join(tmp, "model")
                mlflow.sklearn.save_model(model, model_dir)
                mlflow.log_artifacts(model_dir, artifact_path="model")
            print(f"  run {run.info.run_id[:8]} · {params} · AUC={metrics['auc']:.3f}")
            if metrics["auc"] > best["auc"]:
                best = {"auc": metrics["auc"], "run_id": run.info.run_id, "params": params}

    # Register the best run in the MLflow Model Registry.
    result = mlflow.register_model(f"runs:/{best['run_id']}/model", "fraud-scoring")
    print(f"\n✓ Best AUC={best['auc']:.3f} → registered 'fraud-scoring' v{result.version}")
    print(f"✓ MLflow UI: {TRACKING_URI} → experiment '{EXPERIMENT}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
