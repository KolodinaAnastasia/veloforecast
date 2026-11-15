import argparse
import hashlib
import io
import json
import math
from importlib.metadata import version

import pandas as pd

from baseline import MODEL_DATA, score_predictions
from evaluate import fit_candidate, predict_candidate
from experiments import JOURNAL
from models import SEED


def replay(experiment_id: str) -> None:
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    experiments = {row["id"]: row for row in journal["experiments"]}
    if experiment_id not in experiments:
        raise ValueError(f"Эксперимент отсутствует в журнале: {experiment_id}")
    config = experiments[experiment_id]

    raw_data = MODEL_DATA.read_bytes()
    if hashlib.sha256(raw_data).hexdigest() != journal["data_sha256"]:
        raise ValueError("Версия данных отличается от версии в журнале.")
    if journal["seed"] != SEED:
        raise ValueError("Случайное зерно отличается от значения в журнале.")
    for package, recorded in journal["versions"].items():
        current = version(package)
        if current != recorded:
            raise ValueError(f"Версия {package}: установлена {current}, в журнале {recorded}.")

    data = pd.read_csv(io.BytesIO(raw_data), index_col="hour_utc")
    train = data.loc[data["split"] == "train"]
    validation = data.loc[data["split"] == "validation"]
    fitted = fit_candidate(config, train)
    prediction = predict_candidate(config, fitted, validation)
    scores = score_predictions(validation["rides"], prediction)

    print(f"Эксперимент: {experiment_id}")
    for metric, value in scores.items():
        recorded = config[metric]
        print(f"{metric}: повтор {value:.2f} | журнал {recorded:.2f}")
        if not math.isclose(value, recorded, rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError(f"{metric} отличается от результата в журнале.")

    print("Метрики совпали с журналом.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Воспроизведение эксперимента")
    parser.add_argument("--id", required=True, help="Идентификатор из журнала")
    args = parser.parse_args()
    replay(args.id)