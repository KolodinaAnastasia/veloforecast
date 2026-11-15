import pandas as pd
import requests
from datetime import date, timedelta
from http_client import get_json

ARCHIVE_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
VARIABLES = ("temperature_2m", "precipitation", "wind_speed_10m")
SUFFIX = "_previous_day1"


def load_archived_weather(start_date: str, end_date: str) -> pd.DataFrame:
    data = get_json(
        ARCHIVE_URL,
        params={
            "latitude": 40.75,
            "longitude": -73.98,
            "timezone": "GMT",
            "start_date": start_date,
            "end_date": end_date,
            "hourly": ",".join(name + SUFFIX for name in VARIABLES),
        },
        timeout=(10, 30),
    )
    hourly = data["hourly"]

    weather = pd.DataFrame({
        "hour_utc": pd.to_datetime(hourly["time"], utc=True),
        **{name: hourly[name + SUFFIX] for name in VARIABLES},
    })

    expected = pd.date_range(
        start=pd.Timestamp(start_date, tz="UTC"),
        end=pd.Timestamp(date.fromisoformat(end_date) + timedelta(days=1), tz="UTC"),
        freq="h",
        inclusive="left",
    )
    if not pd.DatetimeIndex(weather["hour_utc"]).equals(expected):
        raise ValueError("Open-Meteo вернул неполный или несогласованный ряд часов.")

    return weather


if __name__ == "__main__":
    weather = load_archived_weather("2025-01-15", "2025-01-15")
    print(weather.head().to_string(index=False))
    print(f"\nЧасов получено: {len(weather)}")
    print(f"Пропусков в погодных значениях: {weather[list(VARIABLES)].isna().sum().sum()}")