import argparse
import sqlite3
from calendar import monthrange
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from weather import load_archived_weather


DATABASE = Path(__file__).resolve().parent / "state" / "veloforecast.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS weather_hourly (
    hour_utc TEXT PRIMARY KEY,
    temperature_2m REAL,
    precipitation REAL,
    wind_speed_10m REAL
);

CREATE TABLE IF NOT EXISTS load_log (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    period TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    rows_added INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def missing_ranges(first_day, last_day, complete_days):
    """Объединяет соседние недостающие дни в один запрос."""
    start = None
    day = first_day
    one_day = timedelta(days=1)

    while day <= last_day:
        if day.isoformat() not in complete_days:
            if start is None:
                start = day
        elif start is not None:
            yield start, day - one_day
            start = None
        day += one_day

    if start is not None:
        yield start, last_day


def sync_weather_month(db, month):
    first_day = date.fromisoformat(f"{month}-01")
    last_day = first_day.replace(day=monthrange(first_day.year, first_day.month)[1])
    next_month = last_day + timedelta(days=1)

    with db:
        run_id = db.execute(
            """
            INSERT INTO load_log (source, period, started_at, status)
            VALUES ('open_meteo', ?, ?, 'running')
            """,
            (month, utc_now()),
        ).lastrowid

    added = 0
    try:
        complete_days = {
            day
            for (day,) in db.execute(
                """
                SELECT substr(hour_utc, 1, 10)
                FROM weather_hourly
                WHERE hour_utc >= ? AND hour_utc < ?
                GROUP BY substr(hour_utc, 1, 10)
                HAVING COUNT(*) = 24
                """,
                (first_day.isoformat(), next_month.isoformat()),
            )
        }

        for start, end in missing_ranges(first_day, last_day, complete_days):
            print(f"Запрос Open-Meteo: {start} — {end}", flush=True)
            weather = load_archived_weather(start.isoformat(), end.isoformat())
            weather["hour_utc"] = weather["hour_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            with db:
                cursor = db.executemany(
                    """
                    INSERT INTO weather_hourly
                        (hour_utc, temperature_2m, precipitation, wind_speed_10m)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(hour_utc) DO NOTHING
                    """,
                    weather.itertuples(index=False, name=None),
                )
            added += cursor.rowcount

    except Exception as error:
        finish_run(db, run_id, "failed", added, str(error))
        raise

    status = "loaded" if added else "skipped"
    finish_run(db, run_id, status, added)
    print(f"{month}: добавлено часов: {added}. Статус: {status}.")


def finish_run(db, run_id, status, added, error=None):
    with db:
        db.execute(
            """
            UPDATE load_log
            SET finished_at = ?, status = ?, rows_added = ?, error = ?
            WHERE id = ?
            """,
            (utc_now(), status, added, error, run_id),
        )


def show_log(db):
    for started, period, status, added, error in db.execute(
        """
        SELECT started_at, period, status, rows_added, error
        FROM load_log
        ORDER BY id DESC
        LIMIT 10
        """
    ):
        print(f"{started} | {period} | {status} | добавлено: {added}")
        if error:
            print(f"  Ошибка: {error}")


def main():
    parser = argparse.ArgumentParser(description="Загрузка погоды Open-Meteo")
    parser.add_argument("--month", default="2025-01", help="Месяц в формате ГГГГ-ММ")
    parser.add_argument("--log", action="store_true", help="Показать журнал загрузок")
    args = parser.parse_args()

    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DATABASE)) as db:
        db.executescript(SCHEMA)
        if args.log:
            show_log(db)
        else:
            sync_weather_month(db, args.month)


if __name__ == "__main__":
    main()