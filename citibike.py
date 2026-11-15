import json
from pathlib import Path
from zipfile import ZipFile

import requests

import argparse

import pandas as pd


ARCHIVE_DIR = Path(__file__).resolve().parent / "state" / "citibike"
ARCHIVE_URL = "https://s3.amazonaws.com/tripdata/"


def csv_members(path: Path) -> list[str]:
    with ZipFile(path) as archive:
        files = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".csv")
            and not name.startswith("__MACOSX/")
            and not Path(name).name.startswith("._")
        ]
    if not files:
        raise ValueError("В архиве Citi Bike не найдено ни одного CSV.")
    return files





def preview_trips(path: Path) -> None:
    columns = ["ride_id", "started_at", "start_lat", "start_lng"]
    members = csv_members(path)
    print(f"Архив: {path.name}")
    print(f"CSV внутри: {len(members)}")

    with ZipFile(path) as archive:
        for name in members:
            print(f"\n{name}")
            with archive.open(name) as source:
                sample = pd.read_csv(source, usecols=columns, nrows=5)

            if sample.empty:
                raise ValueError(f"В файле {name} нет поездок.")
            print(sample[columns].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Проверка архива Citi Bike")
    parser.add_argument("--local", type=Path, help="Путь к скачанному ZIP")
    args = parser.parse_args()

    archive_path = args.local or (ARCHIVE_DIR / "202501-citibike-tripdata.zip")
    preview_trips(archive_path)