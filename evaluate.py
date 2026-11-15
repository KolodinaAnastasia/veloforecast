import hashlib
import io
import json

import joblib
import pandas as pd

from baseline import MODEL_DATA, fit_naive, predict_naive, score_predictions
from experiments import JOURNAL
from models import fit_regressor, predict_regressor


EVALUATION_PATH = MODEL_DATA.parent / "2025-evaluation.joblib"
PREDICTIONS_PATH = MODEL_DATA.parent / "2025-test-predictions.csv"


def fit_candidate(config, data):
    name = config["model"]
    if name == "Naive":
        return fit_naive(data, data["rides"])
    return fit_regressor(name, data, config["columns"], config["parameters"])


def predict_candidate(config, fitted, data):
    if config["model"] == "Naive":
        return predict_naive(data, fitted)
    return predict_regressor(fitted, data, config["columns"])


def evaluate() -> None:
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    raw_data = MODEL_DATA.read_bytes()
    data_hash = hashlib.sha256(raw_data).hexdigest()
    if data_hash != journal["data_sha256"]:
        raise ValueError("Данные изменились после подбора. Снова запусти experiments.py.")

    data = pd.read_csv(io.BytesIO(raw_data), index_col="hour_utc")
    training = data.loc[data["split"].isin(["train", "validation"])]
    test = data.loc[data["split"] == "test"]
    experiments = {entry["id"]: entry for entry in journal["experiments"]}

    predictions = test[["issued_utc", "rides"]].rename(columns={"rides": "actual"})
    fitted_models = {}
    results = []

    for name, experiment_id in journal["best_by_model"].items():
        config = experiments[experiment_id]
        fitted = fit_candidate(config, training)
        predicted = predict_candidate(config, fitted, test)

        fitted_models[name] = {"config": config, "fitted": fitted}
        predictions[name] = predicted
        results.append({
            "model": name,
            "experiment_id": experiment_id,
            **score_predictions(test["rides"], predicted),
        })

    naive_mae = next(row["MAE"] for row in results if row["model"] == "Naive")
    for row in results:
        row["mae_saved"] = naive_mae - row["MAE"]
        row["mae_saved_pct"] = 100 * row["mae_saved"] / naive_mae if naive_mae else None

    temporary_csv = PREDICTIONS_PATH.with_suffix(".csv.part")
    predictions.to_csv(temporary_csv, index_label="hour_utc")
    temporary_csv.replace(PREDICTIONS_PATH)

    temporary_bundle = EVALUATION_PATH.with_suffix(".joblib.part")
    joblib.dump({
        "winner": journal["winner"],
        "data_sha256": data_hash,
        "models": fitted_models,
        "metrics": results,
        "test_hours": len(test),
    }, temporary_bundle, compress=3)
    temporary_bundle.replace(EVALUATION_PATH)

    print(f"Отложенный тест: {len(test)} часов")
    print(f"Модель, выбранная на валидации: {journal['winner']}")
    for row in results:
        print(
            f"{row['model']:8} | MAE {row['MAE']:8.2f} | RMSE {row['RMSE']:8.2f} "
            f"| снижение MAE к Naive: {row['mae_saved']:+.2f} поездок/ч"
        )
    print(f"Почасовые результаты: {PREDICTIONS_PATH.name}")
    print(f"Оценка и модели: {EVALUATION_PATH.name}")


if __name__ == "__main__":
    evaluate()