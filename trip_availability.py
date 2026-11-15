from email.utils import parsedate_to_datetime

import pandas as pd
import requests

from citibike import ARCHIVE_URL
from trip_hourly import TIMEZONE
from weather_store import DATABASE


def save_trip_availability(year: int) -> None:
    months = pd.period_range(f"{year}-01", f"{year}-12", freq="M")
    records = []

    with requests.Session() as client:
        for month in months:
            filename = f"{month.strftime('%Y%m')}-citibike-tripdata.zip"
            url = ARCHIVE_URL + filename

            with client.head(url, allow_redirects=True, timeout=(10, 30)) as response:
                response.raise_for_status()
                header = response.headers.get("Last-Modified")

            if header is None:
                raise ValueError(f"Сервер не указал Last-Modified для {filename}.")

            modified = pd.Timestamp(parsedate_to_datetime(header)).tz_convert("UTC")
            month_end = (month + 1).start_time.tz_localize(TIMEZONE).tz_convert("UTC")
            available = max(modified, month_end)

            records.append({
                "month": str(month),
                "last_modified_utc": modified.isoformat(),
                "available_utc": available.isoformat(),
                "source_url": url,
            })
            print(f"{month} | доступен с {available.isoformat()}", flush=True)

    output = DATABASE.parent / "datasets" / f"{year}-trip-availability.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".csv.part")
    pd.DataFrame(records).to_csv(temporary, index=False)
    temporary.replace(output)
    print(f"Месяцев записано: {len(records)}")


if __name__ == "__main__":
    save_trip_availability(2025)