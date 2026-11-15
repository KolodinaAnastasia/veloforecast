import hashlib
import io
import json
from importlib.metadata import version

import pandas as pd

from baseline import MODEL_DATA, fit_naive, predict_naive, score_predictions
from models import (
    FEATURE_COLUMNS,
    FEATURE_GROUPS,
    MODEL_PARAMS,
    SEED,
    fit_regressor,
    predict_regressor,
)


JOURNAL = MODEL_DATA.parent / "2025-experiments.json"

PARAMETER_GRID = {
    "Ridge": [MODEL_PARAMS["Ridge"], {"alpha": 100.0}],
    "Boosting": [
        MODEL_PARAMS["Boosting"],
        {**MODEL_PARAMS["Boosting"], "max_depth": 2},
    ],
}

FEATURE_SETS = {"all": FEATURE_COLUMNS}
for group, columns in FEATURE_GROUPS.items():
    FEATURE_SETS[f"without_{group}"] = tuple(
        column for column in FEATURE_COLUMNS if column not in columns
    )


def run_search() -> None:
    raw_data = MODEL_DATA.read_bytes()
    data = pd.read_csv(io.BytesIO(raw_data), index_col="hour_utc")
    train = data.loc[data["split"] == "train"]
    validation = data.loc[data["split"] == "validation"]
    actual = validation["rides"]

    naive = predict_naive(validation, fit_naive(train, train["rides"]))
    experiments = [{
        "id": "naive",
        "model": "Naive",
        "parameters": {},
        "feature_set": "baseline",
        "columns": ["weekday", "hour_local", "lag_same_weekday_hour"],
        **score_predictions(actual, naive),
    }]

    for name, choices in PARAMETER_GRID.items():
        for number, params in enumerate(choices, start=1):
            for feature_set, columns in FEATURE_SETS.items():
                experiment_id = f"{name.lower()}-{number}-{feature_set}"
                model = fit_regressor(name, train, columns, params)
                predicted = predict_regressor(model, validation, columns)
                scores = score_predictions(actual, predicted)

                experiments.append({
                    "id": experiment_id,
                    "model": name,
                    "parameters": params,
                    "feature_set": feature_set,
                    "columns": list(columns),
                    **scores,
                })
                print(
                    f"{experiment_id:30} | MAE {scores['MAE']:8.2f} "
                    f"| RMSE {scores['RMSE']:8.2f}",
                    flush=True,
                )

    ranked = sorted(experiments, key=lambda row: (row["MAE"], row["RMSE"]))
    best_by_model = {}
    for row in ranked:
        best_by_model.setdefault(row["model"], row["id"])

    result = {
        "seed": SEED,
        "data_sha256": hashlib.sha256(raw_data).hexdigest(),
        "versions": {
            package: version(package)
            for package in ("numpy", "pandas", "scikit-learn")
        },
        "train_hours": len(train),
        "validation_hours": len(validation),
        "winner": ranked[0]["id"],
        "best_by_model": best_by_model,
        "experiments": experiments,
    }
    temporary = JOURNAL.with_suffix(".json.part")
    temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
    temporary.replace(JOURNAL)

    print(f"\nКонфигураций проверено: {len(experiments)}")
    print("Лучший вариант каждой модели:")
    by_id = {row["id"]: row for row in experiments}
    for name in ("Naive", "Ridge", "Boosting"):
        row = by_id[best_by_model[name]]
        print(f"  {row['id']} | MAE {row['MAE']:.2f} | RMSE {row['RMSE']:.2f}")

    print("\nИзменение MAE при удалении группы. Плюс означает рост ошибки.")
    for name in PARAMETER_GRID:
        best = by_id[best_by_model[name]]
        same_params = {
            row["feature_set"]: row["MAE"]
            for row in experiments
            if row["model"] == name and row["parameters"] == best["parameters"]
        }
        changes = ", ".join(
            f"{group}: {same_params[f'without_{group}'] - same_params['all']:+.2f}"
            for group in FEATURE_GROUPS
        )
        print(f"  {name} | {changes}")

    print(f"\nПобедитель валидации: {result['winner']}")
    print(f"Журнал сохранён: {JOURNAL.name}")


if __name__ == "__main__":
    run_search()