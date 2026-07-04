def test_train_mlflow(trained_model):
    # The session fixture already ran ml/train.py; assert on its captured output.
    assert trained_model.result.returncode == 0, trained_model.result.stderr
    assert "Run ID:" in trained_model.result.stdout
