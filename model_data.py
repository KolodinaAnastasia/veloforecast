from datetime import timedelta

import pandas as pd

from features import features_for_hours, load_history
from weather_store import DATABASE


# Правая граница каждого периода исключается.
PERIODS = {
    "train": ("2025-07-04", "2025-09-01"),
    "validation": ("2025-09-05", "2025-11-01"),
    "test": ("2025-11-05", "2026-01-01"),
}


def first_issue(split: str) -> pd.Timestamp:
    start, _ = PERIODS[split]
    return pd.Timestamp(start, tz="UTC") - timedelta(hours=1)


def build_model_data() -> None:
    history = load_history(2025)
    label_cutoffs = {
        "train": first_issue("validation"),
        "validation": first_issue("test"),
    }
    parts = []

    for split, (start, end) in PERIODS.items():
        days = pd.date_range(start, end, freq="D", tz="UTC", inclusive="left")

        for day in days:
            issued_at = day - timedelta(hours=1)
            hours = pd.date_range(day, periods=24, freq="h")
            facts = history.loc[hours]
            cutoff = label_cutoffs.get(split)

            if cutoff is not None and (facts["available_utc"] > cutoff).any():
                raise ValueError(
                    f"{split}: поездки за {day.date()} опубликованы после {cutoff}."
                )

            features = features_for_hours(hours, issued_at, history, history)
            features["issued_utc"] = issued_at
            features["split"] = split
            features["rides"] = facts["rides"]
            parts.append(features.dropna(subset=["rides"]))

    dataset = pd.concat(parts, verify_integrity=True).sort_index()
    output = DATABASE.parent / "datasets" / "2025-model-rows.csv"
    temporary = output.with_suffix(".csv.part")
    dataset.to_csv(temporary, index_label="hour_utc")
    temporary.replace(output)

    for split in PERIODS:
        rows = dataset.loc[dataset["split"] == split]
        print(f"{split}: {len(rows)} часов | {rows.index[0]} — {rows.index[-1]}")
    print(f"Файл сохранён: {output.name}")


if __name__ == "__main__":
    build_model_data()