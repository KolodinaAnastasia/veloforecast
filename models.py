import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from baseline import MODEL_DATA, fit_naive, predict_naive, score_predictions
from features import BOROUGH_NAMES, HISTORY_FEATURES
from weather import VARIABLES


SEED = 42
CATEGORICAL = ("hour_local", "weekday", "month")

FEATURE_GROUPS = {
    "calendar": (*CATEGORICAL, "weekend"),
    "weather": VARIABLES,
    "history": HISTORY_FEATURES,
    "geography": tuple(f"share_{name}" for name in BOROUGH_NAMES),
}
FEATURE_COLUMNS = tuple(
    column
    for group in FEATURE_GROUPS.values()
    for column in group
)

MODEL_PARAMS = {
    "Ridge": {"alpha": 10.0},
    "Boosting": {
        "n_estimators": 160,
        "max_depth": 3,
        "min_samples_leaf": 15,
    },
}


def fit_regressor(name, train, columns, params):
    categorical = [column for column in columns if column in CATEGORICAL]
    numeric = [column for column in columns if column not in CATEGORICAL]

    numeric_steps = [SimpleImputer(strategy="median", keep_empty_features=True)]
    if name == "Ridge":
        numeric_steps.append(StandardScaler())
        regressor = Ridge(**params)
    elif name == "Boosting":
        regressor = GradientBoostingRegressor(random_state=SEED, **params)
    else:
        raise ValueError(f"Неизвестная модель: {name}")

    preprocessing = ColumnTransformer([
        ("numeric", make_pipeline(*numeric_steps), numeric),
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical),
    ])
    model = make_pipeline(preprocessing, regressor)
    return model.fit(train[list(columns)], train["rides"])


def predict_regressor(model, data, columns):
    values = model.predict(data[list(columns)])
    return pd.Series(values, index=data.index).clip(lower=0)


def compare_on_validation():
    data = pd.read_csv(MODEL_DATA, index_col="hour_utc")
    train = data.loc[data["split"] == "train"]
    validation = data.loc[data["split"] == "validation"]

    predictions = {
        "Naive": predict_naive(validation, fit_naive(train, train["rides"])),
    }
    for name, params in MODEL_PARAMS.items():
        model = fit_regressor(name, train, FEATURE_COLUMNS, params)
        predictions[name] = predict_regressor(model, validation, FEATURE_COLUMNS)

    print(f"Валидация: {len(validation)} часов")
    for name, predicted in predictions.items():
        scores = score_predictions(validation["rides"], predicted)
        print(f"{name:8} | MAE {scores['MAE']:8.2f} | RMSE {scores['RMSE']:8.2f}")


if __name__ == "__main__":
    compare_on_validation()