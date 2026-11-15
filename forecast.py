import joblib
import numpy as np
import pandas as pd

from evaluate import EVALUATION_PATH, PREDICTIONS_PATH, predict_candidate
from features import features_for_hours, load_history
from trip_hourly import TIMEZONE


FORECAST_PATH = EVALUATION_PATH.parent / "latest-forecast.csv"


def make_forecast(issued_at, weather, history, evaluation):
    hours = pd.date_range(issued_at.floor("h"), periods=25, freq="h")[1:]
    features = features_for_hours(hours, issued_at, weather, history)
    selected = next(
        entry
        for entry in evaluation["models"].values()
        if entry["config"]["id"] == evaluation["winner"]
    )
    config = selected["config"]
    predictions = predict_candidate(config, selected["fitted"], features)

    return pd.DataFrame({
        "hour_utc": hours,
        "issued_utc": issued_at,
        "model": config["model"],
        "predicted_rides": predictions.to_numpy(),
    })


def run_replay():
    issued_at = pd.Timestamp("2025-11-10T23:00:00Z")
    evaluation = joblib.load(EVALUATION_PATH)
    history = load_history(2025)
    forecast = make_forecast(issued_at, history, history, evaluation)
    model = forecast["model"].iloc[0]

    reference = pd.read_csv(PREDICTIONS_PATH)
    reference.index = pd.to_datetime(reference.pop("hour_utc"), utc=True)
    expected = reference.loc[forecast["hour_utc"], model]
    np.testing.assert_allclose(forecast["predicted_rides"], expected, atol=1e-8)

    forecast["mode"] = "replay"
    temporary = FORECAST_PATH.with_suffix(".csv.part")
    forecast.to_csv(temporary, index=False)
    temporary.replace(FORECAST_PATH)

    peak = forecast.loc[forecast["predicted_rides"].idxmax()]
    peak_local = peak["hour_utc"].tz_convert(TIMEZONE)
    print(f"Архивный выпуск: {issued_at.isoformat()}")
    print(f"Модель: {model} | Часов: {len(forecast)}")
    print(f"Пик: {peak_local:%d.%m.%Y %H:%M %Z} | {peak['predicted_rides']:.0f} поездок")
    print("Все 24 значения совпали с сохранённым тестовым прогнозом.")
    print(f"Файл: {FORECAST_PATH.name}")


if __name__ == "__main__":
    run_replay()