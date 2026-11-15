import argparse
import math

import joblib
import pandas as pd

from baseline import MODEL_DATA
from evaluate import EVALUATION_PATH, predict_candidate
from models import CATEGORICAL
from trip_hourly import TIMEZONE


def explain_ridge(fitted, columns, training, row):
    typical = {}
    for column in columns:
        values = training[column].dropna()
        if values.empty:
            typical[column] = float("nan")
        elif column in CATEGORICAL:
            typical[column] = values.mode().iloc[0]
        else:
            typical[column] = values.median()

    reference = pd.DataFrame([typical], columns=columns)
    base = float(fitted.predict(reference)[0])
    contributions = {}

    for column in columns:
        variant = reference.copy()
        variant[column] = row[column].iloc[0]
        contributions[column] = float(fitted.predict(variant)[0]) - base

    raw_prediction = float(fitted.predict(row[columns])[0])
    if raw_prediction < 0:
        contributions["Ограничение прогноза нулём"] = -raw_prediction

    return base, contributions


def main():
    parser = argparse.ArgumentParser(description="Вклад признаков в прогноз Ridge")
    parser.add_argument("--hour", default="2025-11-11T22:00:00Z", help="Целевой час в UTC")
    args = parser.parse_args()
    hour = pd.to_datetime(args.hour, utc=True)

    data = pd.read_csv(MODEL_DATA, index_col="hour_utc")
    data.index = pd.to_datetime(data.index, utc=True)
    training = data.loc[data["split"].isin(["train", "validation"])]
    test = data.loc[data["split"] == "test"]
    if hour not in test.index:
        raise ValueError(f"Час {hour.isoformat()} отсутствует в отложенном тесте.")

    row = test.loc[[hour]]
    evaluation = joblib.load(EVALUATION_PATH)
    entry = evaluation["models"]["Ridge"]
    config = entry["config"]
    fitted = entry["fitted"]
    base, contributions = explain_ridge(fitted, config["columns"], training, row)
    prediction = float(predict_candidate(config, fitted, row).iloc[0])

    if not math.isclose(base + sum(contributions.values()), prediction, abs_tol=1e-6):
        raise ValueError("Сумма вкладов отличается от прогноза Ridge.")

    local_hour = hour.tz_convert(TIMEZONE)
    print(f"Целевой час: {local_hour:%d.%m.%Y %H:%M %Z}")
    print(f"Базовое значение: {base:.2f} поездки")
    print("Вклад признаков, поездок:")
    for name, effect in sorted(contributions.items(), key=lambda item: -abs(item[1])):
        print(f"  {name:30} {effect:+.2f}")
    print(f"Прогноз Ridge: {prediction:.2f} поездки")
    print(f"Факт: {row['rides'].iloc[0]:.0f} поездок")
    print("Сумма вкладов сверена с прогнозом.")


if __name__ == "__main__":
    main()