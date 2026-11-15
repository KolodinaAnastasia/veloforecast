from html import escape

import numpy as np

from baseline import score_predictions
from dashboard_explain import feature_label
from evaluate import predict_candidate
from models import SEED


def ridge_weights(fitted):
    preprocessing = fitted.named_steps["columntransformer"]
    coefficients = np.abs(fitted.named_steps["ridge"].coef_)
    steps = {name: (transformer, columns)
             for name, transformer, columns in preprocessing.transformers_}

    _, numeric = steps["numeric"]
    numeric_weights = coefficients[preprocessing.output_indices_["numeric"]]
    weights = dict(zip(numeric, numeric_weights))

    encoder, categorical = steps["categorical"]
    if categorical:
        categorical_weights = coefficients[preprocessing.output_indices_["categorical"]]
        offset = 0
        for column, categories in zip(categorical, encoder.categories_):
            end = offset + len(categories)
            weights[column] = float(np.linalg.norm(categorical_weights[offset:end]))
            offset = end

    return weights


def permutation_mae(config, fitted, data):
    rng = np.random.default_rng(SEED)
    actual = data["rides"]
    baseline = score_predictions(actual, predict_candidate(config, fitted, data))["MAE"]
    result = {}

    for column in config["columns"]:
        variant = data.copy()
        changes = []
        for _ in range(5):
            variant[column] = rng.permutation(data[column].to_numpy())
            predictions = predict_candidate(config, fitted, variant)
            changes.append(score_predictions(actual, predictions)["MAE"] - baseline)
        result[column] = float(np.mean(changes))

    return result


def render_importance(test, evaluation):
    entry = evaluation["models"]["Ridge"]
    config, fitted = entry["config"], entry["fitted"]
    weights = ridge_weights(fitted)
    overall = permutation_mae(config, fitted, test)
    monthly = {
        period: permutation_mae(config, fitted, rows)
        for period, rows in test.groupby(test["local_day"].str[:7])
    }

    headers = "".join(f'<th scope="col">Δ MAE · {period}</th>' for period in monthly)
    rows = []
    for column in sorted(overall, key=overall.get, reverse=True):
        monthly_cells = "".join(f"<td>{values[column]:+.1f}</td>" for values in monthly.values())
        rows.append(
            f'<tr><th scope="row">{escape(feature_label(column))}</th>'
            f"<td>{weights[column]:.1f}</td><td>{overall[column]:+.1f}</td>"
            f"{monthly_cells}</tr>"
        )

    return f"""
    <section>
        <h2>Важность признаков Ridge</h2>
        <p>Δ MAE — изменение ошибки после перемешивания признака, в поездках за час.
        Положительное значение означает рост ошибки.</p>
        <table>
            <thead><tr>
                <th scope="col">Признак</th>
                <th scope="col">Модуль коэффициента</th>
                <th scope="col">Δ MAE · весь тест</th>
                {headers}
            </tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
    </section>
    """