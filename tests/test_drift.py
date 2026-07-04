import subprocess
import sys

import pandas as pd


def test_drift_script(tmp_path):
    base = tmp_path / "baseline.csv"
    newb = tmp_path / "new.csv"

    # Create tiny numeric data with slight distribution shift
    pd.DataFrame({"x": [0, 1, 2, 3, 4, 5]}).to_csv(base, index=False)
    pd.DataFrame({"x": [10, 11, 12, 13, 14, 15]}).to_csv(newb, index=False)

    res = subprocess.run(
        [
            sys.executable,
            "ml/drift.py",
            "--baseline",
            str(base),
            "--input",
            str(newb),
            "--threshold",
            "0.0",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # Threshold 0.0 guarantees non-zero exit (drift)
    assert res.returncode != 0
    assert "retrain recommended" in res.stdout.lower()
