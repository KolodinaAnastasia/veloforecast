import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

from weather_store import DATABASE


SLOT_COLUMNS = ["weekday", "hour_local"]
MODEL_DATA = DATABASE.parent / "datasets" / "2025-model-rows.csv"


def fit_naive(features: pd.DataFrame, rides: pd.Series) -> tuple[pd.Series, float]:
    slot_medians = rides.groupby(
        [features["weekday"], features["hour_local"]]
    ).median()
    return slot_medians, float(rides.median())


def predict_naive(
    features: pd.DataFrame, profile: tuple[pd.Series, float]
) -> pd.Series:
    slot_medians, overall_median = profile
    slots = pd.MultiIndex.from_frame(features[SLOT_COLUMNS])
    fallback = pd.Series(
        slot_medians.reindex(slots).to_numpy(),
        index=features.index,
    ).fillna(overall_median)

    return features["lag_same_weekday_hour"].fillna(fallback)


def score_predictions(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    return {
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(root_mean_squared_error(actual, predicted)),
    }


if __name__ == "__main__":
    data = pd.read_csv(MODEL_DATA, index_col="hour_utc")
    train = data.loc[data["split"] == "train"]
    validation = data.loc[data["split"] == "validation"]

    profile = fit_naive(train, train["rides"])
    predicted = predict_naive(validation, profile)
    scores = score_predictions(validation["rides"], predicted)

    print(f"Naive | валидация: {len(validation)} часов")
    print(f"MAE:  {scores['MAE']:.2f} поездок/ч")
    print(f"RMSE: {scores['RMSE']:.2f} поездок/ч")