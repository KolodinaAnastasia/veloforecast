from datetime import timedelta

import pandas as pd

from trip_hourly import TIMEZONE
from weather import VARIABLES
from weather_store import DATABASE


BOROUGH_NAMES = ("Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island")
HISTORY_FEATURES = (
    "lag_same_weekday_hour",
    "lag_24_from_last_fact",
    "mean_last_24h",
    "mean_last_168h",
    "fact_age_hours",
)


def load_history(year: int) -> pd.DataFrame:
    directory = DATABASE.parent / "datasets"
    history = pd.read_csv(directory / f"{year}-dataset.csv")
    history["hour_utc"] = pd.to_datetime(history["hour_utc"], utc=True)
    history = history.set_index("hour_utc", verify_integrity=True).sort_index()

    availability = pd.read_csv(directory / f"{year}-trip-availability.csv")
    availability["available_utc"] = pd.to_datetime(availability["available_utc"], utc=True)
    by_month = availability.set_index("month", verify_integrity=True)["available_utc"]
    local_months = history.index.tz_convert(TIMEZONE).strftime("%Y-%m")
    history["available_utc"] = by_month.reindex(local_months).array

    if history["available_utc"].isna().any():
        raise ValueError("В таблице доступности не хватает дат публикации архивов.")
    return history


def features_for_hours(
    target_hours: pd.DatetimeIndex,
    issued_at: pd.Timestamp,
    weather: pd.DataFrame,
    history: pd.DataFrame,
) -> pd.DataFrame:
    if (target_hours <= issued_at).any():
        raise ValueError("Целевые часы должны идти после выпуска прогноза.")

    local = target_hours.tz_convert(TIMEZONE)
    features = weather.reindex(target_hours)[list(VARIABLES)].copy()
    features["hour_local"] = local.hour
    features["weekday"] = local.dayofweek
    features["month"] = local.month
    features["weekend"] = (local.dayofweek >= 5).astype(int)

    share_columns = [f"share_{name}" for name in BOROUGH_NAMES]
    for name in (*HISTORY_FEATURES, *share_columns):
        features[name] = float("nan")

    available = history.loc[
        (history.index < issued_at)
        & (history["available_utc"] <= issued_at)
        & history["rides"].notna()
    ]
    if available.empty:
        return features

    last_hour = available.index[-1]
    last_day = available.loc[last_hour - timedelta(hours=23):last_hour]
    last_week = available.loc[last_hour - timedelta(hours=167):last_hour]

    previous_local = available.index.tz_convert(TIMEZONE)
    previous_slots = available["rides"].groupby(
        [previous_local.dayofweek, previous_local.hour]
    ).last()
    target_slots = pd.MultiIndex.from_arrays([local.dayofweek, local.hour])
    features["lag_same_weekday_hour"] = previous_slots.reindex(target_slots).to_numpy()
    features["lag_24_from_last_fact"] = available["rides"].get(
        last_hour - timedelta(hours=24), float("nan")
    )
    features["mean_last_24h"] = last_day["rides"].mean()
    features["mean_last_168h"] = last_week["rides"].mean()
    features["fact_age_hours"] = (issued_at - last_hour).total_seconds() / 3600

    week_total = last_week["rides"].sum()
    if week_total > 0:
        for borough in BOROUGH_NAMES:
            features[f"share_{borough}"] = last_week[borough].sum() / week_total

    return features


if __name__ == "__main__":
    history = load_history(2025)

    for day in ("2025-07-02", "2025-07-04"):
        issued_at = pd.Timestamp(f"{day}T23:00:00Z")
        hours = pd.date_range(issued_at, periods=25, freq="h")[1:]
        features = features_for_hours(hours, issued_at, history, history)
        count = features["lag_same_weekday_hour"].notna().sum()
        print(f"Выпуск {day}: исторический аналог есть для {count} из 24 часов.")

    changed = history.copy()
    unavailable = (changed.index >= issued_at) | (changed["available_utc"] > issued_at)
    changed.loc[unavailable, "rides"] += 1_000_000

    recalculated = features_for_hours(hours, issued_at, history, changed)
    pd.testing.assert_frame_equal(features, recalculated)
    print("Проверка пройдена: недоступные на момент выпуска поездки не влияют на признаки.")