from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
import sqlite3

from weather import load_archived_weather


DATABASE = Path(__file__).resolve().parent / "state" / "veloforecast.sqlite3"


def sync_weather_day(day: str) -> None:
    next_day = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
    DATABASE.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(DATABASE)) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS weather_hourly (
                hour_utc TEXT PRIMARY KEY,
                temperature_2m REAL,
                precipitation REAL,
                wind_speed_10m REAL
            )
        """)

        saved_hours = db.execute("""
            SELECT COUNT(*) FROM weather_hourly
            WHERE hour_utc >= ? AND hour_utc < ?
        """, (day, next_day)).fetchone()[0]

        if saved_hours == 24:
            print(f"{day}: 24 часа уже в базе. Запрос к Open-Meteo пропущен.")
            return

        weather = load_archived_weather(day, day)
        weather["hour_utc"] = weather["hour_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        with db:
            cursor = db.executemany("""
                INSERT INTO weather_hourly
                    (hour_utc, temperature_2m, precipitation, wind_speed_10m)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(hour_utc) DO NOTHING
            """, weather.itertuples(index=False, name=None))

        print(f"{day}: добавлено часов в базу: {cursor.rowcount}.")


if __name__ == "__main__":
    sync_weather_day("2025-01-15")