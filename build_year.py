import sqlite3
from contextlib import closing

import pandas as pd

from build_dataset import build_dataset
from sync_trips import sync_trip_month
from trip_hourly import TIMEZONE
from weather import VARIABLES
from weather_store import DATABASE, SCHEMA, sync_weather_month


def build_year(year: int) -> None:
    months = pd.period_range(f"{year}-01", f"{year}-12", freq="M")


    # Последние часы декабря по Нью-Йорку попадают в январь по UTC.
    weather_months = pd.period_range(f"{year}-01", f"{year + 1}-01", freq="M")
    with closing(sqlite3.connect(DATABASE)) as db:
        db.executescript(SCHEMA)
        for month in weather_months:
            sync_weather_month(db, str(month))

    dataset_dir = DATABASE.parent / "datasets"
    monthly_tables = []

    with closing(sqlite3.connect(DATABASE)) as db:
        for month in months:
            sync_trip_month(db, month)
            build_dataset(month)
            key = month.strftime("%Y%m")
            monthly_tables.append(pd.read_csv(dataset_dir / f"{key}-dataset.csv"))

    dataset = pd.concat(monthly_tables, ignore_index=True)
    actual_hours = pd.DatetimeIndex(pd.to_datetime(dataset["hour_utc"], utc=True))
    expected_hours = pd.date_range(
        pd.Timestamp(f"{year}-01-01", tz=TIMEZONE).tz_convert("UTC"),
        pd.Timestamp(f"{year + 1}-01-01", tz=TIMEZONE).tz_convert("UTC"),
        freq="h",
        inclusive="left",
    )
    if not actual_hours.equals(expected_hours):
        raise ValueError("В годовой таблице часы пропущены, дублируются или идут не по порядку.")

    output = dataset_dir / f"{year}-dataset.csv"
    temporary = output.with_suffix(".csv.part")
    dataset.to_csv(temporary, index=False)
    temporary.replace(output)

    print(f"\nЧасов за год: {len(dataset):,}")
    print(f"Учтено стартов: {int(dataset['rides'].sum()):,}")
    print(f"Часов без значения поездок: {dataset['rides'].isna().sum()}")
    print(f"Пропусков в погодных значениях: {dataset[list(VARIABLES)].isna().sum().sum()}")
    print(f"Годовой файл: {output.name}")


if __name__ == "__main__":
    build_year(2025)