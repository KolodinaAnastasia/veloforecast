import argparse
import sqlite3
from contextlib import closing

import pandas as pd

from citibike import ARCHIVE_DIR
from weather import VARIABLES
from weather_store import DATABASE


def build_dataset(month: pd.Period) -> None:
    month_key = month.strftime("%Y%m")
    trips_path = ARCHIVE_DIR / f"{month_key}-hourly.csv"
    trips = pd.read_csv(trips_path)

    with closing(sqlite3.connect(DATABASE)) as db:
        weather = pd.read_sql_query(
            """
            SELECT hour_utc, temperature_2m, precipitation, wind_speed_10m
            FROM weather_hourly
            WHERE hour_utc >= ? AND hour_utc <= ?
            ORDER BY hour_utc
            """,
            db,
            params=(trips["hour_utc"].min(), trips["hour_utc"].max()),
        )

    dataset = trips.merge(
        weather, on="hour_utc", how="left", validate="one_to_one", indicator=True
    )
    missing_hours = dataset.loc[dataset["_merge"] == "left_only", "hour_utc"]
    if not missing_hours.empty:
        raise ValueError(
            f"Для {len(missing_hours)} часов нет погодных записей. "
            f"Первый час без погоды: {missing_hours.iloc[0]}"
        )

    dataset = dataset.drop(columns="_merge")
    output = DATABASE.parent / "datasets" / f"{month_key}-dataset.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".csv.part")
    dataset.to_csv(temporary, index=False)
    temporary.replace(output)

    print(f"Часов в датасете: {len(dataset)}")
    print(f"Стартов после объединения: {int(dataset['rides'].sum()):,}")
    print(f"Пропусков в погодных значениях: {dataset[list(VARIABLES)].isna().sum().sum()}")
    print(f"Файл сохранён: {output.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Объединение поездок и погоды")
    parser.add_argument("--month", default="2025-01", help="Месяц в формате ГГГГ-ММ")
    args = parser.parse_args()
    build_dataset(pd.Period(args.month, freq="M"))