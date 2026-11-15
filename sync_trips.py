import argparse
import sqlite3
from contextlib import closing

import pandas as pd

from citibike import ARCHIVE_DIR
from trip_hourly import aggregate_trips
from weather_store import DATABASE, SCHEMA, finish_run, utc_now



def sync_trip_month(db, month: pd.Period) -> None:
    with db:
        run_id = db.execute(
            """
            INSERT INTO load_log (source, period, started_at, status)
            VALUES ('citibike', ?, ?, 'running')
            """,
            (str(month), utc_now()),
        ).lastrowid

    key = month.strftime("%Y%m")
    hourly_path = ARCHIVE_DIR / f"{key}-hourly.csv"

    try:
        if hourly_path.exists():
            status, added = "skipped", 0
        else:
            archive_path = ARCHIVE_DIR / f"{key}-citibike-tripdata.zip"
            if not archive_path.is_file():
                raise FileNotFoundError(f"Отсутствует локальный архив: {archive_path}")

            aggregate_trips(month)
            added = len(pd.read_csv(hourly_path, usecols=["hour_utc"]))
            status = "loaded"
    except Exception as error:
        finish_run(db, run_id, "failed", 0, str(error))
        raise

    finish_run(db, run_id, status, added)
    print(f"Citi Bike | {month} | {status} | добавлено часов: {added}")


def main():
    parser = argparse.ArgumentParser(description="Загрузка почасовых поездок Citi Bike")
    parser.add_argument("--month", required=True, help="Месяц в формате ГГГГ-ММ")
    args = parser.parse_args()
    month = pd.Period(args.month, freq="M")

    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DATABASE)) as db:
        db.executescript(SCHEMA)
        sync_trip_month(db, month)


if __name__ == "__main__":
    main()