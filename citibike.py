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


def download_january() -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    path = ARCHIVE_DIR / "202501-citibike-tripdata.zip"
    metadata = path.with_suffix(".json")
    if path.exists() and metadata.exists():
        print("Архив уже скачан.")
        return path

    url = ARCHIVE_URL + path.name
    partial = path.with_suffix(".zip.part")
    print(f"Скачиваю {path.name}…", flush=True)

    try:
        with requests.get(url, stream=True, timeout=(10, 60)) as response:
            response.raise_for_status()
            last_modified = response.headers.get("Last-Modified")
            with partial.open("wb") as output:
                for block in response.iter_content(chunk_size=1024 * 1024):
                    output.write(block)

        csv_members(partial)
        metadata.write_text(
            json.dumps({"url": url, "last_modified": last_modified}, indent=2),
            encoding="utf-8",
        )
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)

    return path


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

    archive_path = args.local if args.local is not None else download_january()
    preview_trips(archive_path)