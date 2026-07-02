import os

import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from mlflow.models.signature import infer_signature

EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "ai-architect")
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "./.mlruns")

# Recent MLflow releases put the filesystem tracking backend in maintenance mode
# and raise unless this opt-out is set. The local file store is intentional here
# (zero-setup local runs); migration to a sqlite backend is planned.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")


def load_or_generate_data() -> tuple[pd.DataFrame, pd.Series]:
    # Generate small synthetic dataset (binary classification)
    X, y = make_classification(
        n_samples=300,
        n_features=8,
        n_informative=5,
        n_redundant=1,
        random_state=42,
    )
    cols = [f"f{i}" for i in range(X.shape[1])]
    df = pd.DataFrame(X, columns=cols)
    target = pd.Series(y, name="target")
    return df, target


def main():
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    df, y = load_or_generate_data()
    X_train, X_test, y_train, y_test = train_test_split(
        df, y, test_size=0.25, random_state=42
    )

    with mlflow.start_run() as run:
        params = {"C": 1.0, "max_iter": 200, "solver": "lbfgs"}
        model = LogisticRegression(**params)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        acc = float(accuracy_score(y_test, y_pred))
        auc = float(roc_auc_score(y_test, y_proba))

        mlflow.log_params(params)
        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("auc", auc)

        # Log model signature and feature order for serving alignment
        signature = infer_signature(X_train, model.predict(X_train))
        # Include a small input example for clarity
        input_example = X_train.head(2)
        mlflow.sklearn.log_model(model, artifact_path="model", signature=signature, input_example=input_example)
        # Log feature order as a simple artifact for serving-time enforcement
        try:
            mlflow.log_dict({"feature_order": list(df.columns)}, "feature_order.json")
        except Exception:
            pass

        print(f"Run ID: {run.info.run_id}, accuracy={acc:.3f}, auc={auc:.3f}")


if __name__ == "__main__":
    main()
