import argparse

import joblib
import pandas as pd
import requests

from citibike import ARCHIVE_DIR
from evaluate import EVALUATION_PATH
from forecast import make_forecast
from trip_hourly import TIMEZONE
from weather import VARIABLES

from http_client import get_json


WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
LIVE_PATH = EVALUATION_PATH.parent / "latest-live-forecast.csv"


def load_current_weather() -> pd.DataFrame:
    data = get_json(
        WEATHER_URL,
        params={
            "latitude": 40.75,
            "longitude": -73.98,
            "timezone": "GMT",
            "hourly": ",".join(VARIABLES),
            "forecast_days": 3,
        },
        timeout=(10, 30),
    )
    hourly = data["hourly"]
    frame = pd.DataFrame({
        "hour_utc": pd.to_datetime(hourly["time"], utc=True),
        **{name: hourly[name] for name in VARIABLES},
    })
    return frame.set_index("hour_utc", verify_integrity=True).sort_index()


def run_live(month: pd.Period) -> None:
    key = month.strftime("%Y%m")
    history = pd.read_csv(ARCHIVE_DIR / f"{key}-hourly.csv")
    history["hour_utc"] = pd.to_datetime(history["hour_utc"], utc=True)
    history = history.set_index("hour_utc", verify_integrity=True).sort_index()

    evaluation = joblib.load(EVALUATION_PATH)
    weather = load_current_weather()
    issued_at = pd.Timestamp.now(tz="UTC")
    hours = pd.date_range(issued_at.floor("h"), periods=25, freq="h")[1:]

    if weather.reindex(hours)[list(VARIABLES)].isna().any().any():
        raise ValueError("Погодный прогноз не покрывает все 24 целевых часа.")
    if history.empty or history.index[-1] >= issued_at:
        raise ValueError("Для прогноза требуется история за завершённый месяц.")

    # Этот локальный архив уже прочитан к моменту выпуска.
    history["available_utc"] = issued_at
    last_fact = history["rides"].last_valid_index()
    if last_fact is None:
        raise ValueError("В почасовой таблице нет фактических поездок.")

    forecast = make_forecast(issued_at, weather, history, evaluation)
    forecast["history_month"] = str(month)
    forecast["last_fact_utc"] = last_fact
    forecast["mode"] = "live"

    temporary = LIVE_PATH.with_suffix(".csv.part")
    forecast.to_csv(temporary, index=False)
    temporary.replace(LIVE_PATH)

    peak = forecast.loc[forecast["predicted_rides"].idxmax()]
    local_peak = peak["hour_utc"].tz_convert(TIMEZONE)
    print(f"Выпуск UTC: {issued_at:%d.%m.%Y %H:%M}")
    print(f"Модель: {forecast['model'].iloc[0]} | Часов: {len(forecast)}")
    print(f"Последний факт: {last_fact.tz_convert(TIMEZONE):%d.%m.%Y %H:%M %Z}")
    print(f"Пик: {local_peak:%d.%m.%Y %H:%M %Z} | {peak['predicted_rides']:.0f} поездок")
    print(f"Файл: {LIVE_PATH.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Прогноз спроса Citi Bike на 24 часа")
    parser.add_argument("--month", required=True, help="Месяц истории в формате ГГГГ-ММ")
    args = parser.parse_args()
    run_live(pd.Period(args.month, freq="M"))