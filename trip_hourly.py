import argparse

import pandas as pd
from shapely import points

from citibike import ARCHIVE_DIR, ZipFile, csv_members
from geo import load_boroughs


TIMEZONE = "America/New_York"
COLUMNS = ["ride_id", "started_at", "start_lat", "start_lng"]


def aggregate_trips(month: pd.Period) -> None:
    month_key = month.strftime("%Y%m")
    archive_path = ARCHIVE_DIR / f"{month_key}-citibike-tripdata.zip"
    boroughs = load_boroughs()
    names = sorted(boroughs)

    start = month.start_time.tz_localize(TIMEZONE).tz_convert("UTC")
    end = (month + 1).start_time.tz_localize(TIMEZONE).tz_convert("UTC")
    hours = pd.date_range(start, end, freq="h", inclusive="left")
    totals = pd.DataFrame(0, index=hours, columns=names, dtype="int64")

    seen = set()
    read_rows = 0

    with ZipFile(archive_path) as archive:
        for member in csv_members(archive_path):
            print(f"Обрабатываю {member}", flush=True)
            with archive.open(member) as source:
                chunks = pd.read_csv(
                    source,
                    usecols=COLUMNS,
                    dtype={"ride_id": "string"},
                    chunksize=150_000,
                )
                for chunk in chunks:
                    read_rows += len(chunk)
                    started = pd.to_datetime(chunk["started_at"], format="mixed", errors="coerce")
                    local = started.dt.tz_localize(
                        TIMEZONE, ambiguous="NaT", nonexistent="NaT"
                    )
                    hour = local.dt.tz_convert("UTC").dt.floor("h")
                    lat = pd.to_numeric(chunk["start_lat"], errors="coerce")
                    lng = pd.to_numeric(chunk["start_lng"], errors="coerce")

                    valid = (
                        chunk["ride_id"].notna()
                        & (hour >= start)
                        & (hour < end)
                        & lat.between(-90, 90)
                        & lng.between(-180, 180)
                    )
                    rows = chunk.loc[valid, ["ride_id"]].assign(
                        hour=hour, lat=lat, lng=lng
                    )
                    rows = rows.loc[~rows["ride_id"].isin(seen)].drop_duplicates("ride_id")
                    seen.update(rows["ride_id"])

                    coordinates = points(rows["lng"].to_numpy(), rows["lat"].to_numpy())
                    district = pd.Series(pd.NA, index=rows.index, dtype="string")
                    for name in names:
                        covered = boroughs[name].covers(coordinates)
                        district.loc[covered & district.isna()] = name

                    counted = rows.assign(borough=district).groupby(["hour", "borough"]).size()
                    counts = counted.unstack(fill_value=0)
                    totals += counts.reindex(index=hours, columns=names, fill_value=0)

    totals["rides"] = totals[names].sum(axis=1)
    included = int(totals["rides"].sum())
    if included == 0:
        raise ValueError("За выбранный месяц не удалось учесть ни одной поездки.")

    # При осеннем переводе часов в CSV нет смещения UTC для различения двух часов.
    local_hours = hours.tz_convert(TIMEZONE).tz_localize(None)
    totals = totals.astype("Int64")
    totals.loc[local_hours.duplicated(keep=False), :] = pd.NA
    totals.index = hours.strftime("%Y-%m-%dT%H:%M:%SZ")

    output = ARCHIVE_DIR / f"{month_key}-hourly.csv"
    temporary = output.with_suffix(".csv.part")
    totals.to_csv(temporary, index_label="hour_utc")
    temporary.replace(output)

    print(f"Строк прочитано: {read_rows:,}")
    print(f"Стартов учтено: {included:,}")
    print(f"Часов в таблице: {len(totals)}")
    print(f"Файл сохранён: {output.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Почасовые старты Citi Bike")
    parser.add_argument("--month", default="2025-01", help="Месяц в формате ГГГГ-ММ")
    args = parser.parse_args()
    aggregate_trips(pd.Period(args.month, freq="M"))