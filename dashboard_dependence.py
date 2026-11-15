from html import escape

import numpy as np

from dashboard_explain import feature_label
from evaluate import predict_candidate
from models import CATEGORICAL


UNITS = {
    "temperature_2m": "°C",
    "precipitation": "мм",
    "wind_speed_10m": "км/ч",
    "fact_age_hours": "ч",
    "lag_same_weekday_hour": "поездок",
    "lag_24_from_last_fact": "поездок",
    "mean_last_24h": "поездок/ч",
    "mean_last_168h": "поездок/ч",
}


def format_value(column, value):
    if column.startswith("share_"):
        return f"{100 * value:.2f} %"
    if column in CATEGORICAL:
        return escape(str(value))
    unit = UNITS.get(column)
    return f"{value:.2f} {unit}" if unit else f"{value:.2f}"


def render_dependence(test, evaluation, query):
    entry = evaluation["models"]["Ridge"]
    config, fitted = entry["config"], entry["fitted"]
    columns = config["columns"]
    feature = query.get("feature", ["temperature_2m"])[0]
    if feature not in columns:
        feature = columns[0]

    observed = test[feature].dropna()
    if feature in CATEGORICAL:
        values = sorted(observed.unique())
    else:
        values = observed.quantile(np.linspace(0, 1, 11)).dropna().unique()

    rows = []
    variant = test.copy()
    for value in values:
        variant[feature] = value
        average = predict_candidate(config, fitted, variant).mean()
        rows.append(
            f'<tr><th scope="row">{format_value(feature, value)}</th>'
            f"<td>{average:.1f}</td></tr>"
        )

    options = "".join(
        f'<option value="{escape(column)}"{" selected" if column == feature else ""}>'
        f'{escape(feature_label(column))}</option>'
        for column in columns
    )
    carried = "".join(
        f'<input type="hidden" name="{key}" value="{escape(query[key][0])}">'
        for key in ("day", "model", "ex_day", "ex_hour")
        if key in query
    )

    result = "<p>У признака нет наблюдаемых значений в тесте.</p>"
    if rows:
        result = f"""
        <table>
            <thead><tr>
                <th scope="col">Значение признака</th>
                <th scope="col">Средний прогноз, поездок/ч</th>
            </tr></thead>
            <tbody>{"".join(rows)}</tbody>
        </table>
        """

    return f"""
    <section id="dependence">
        <h2>Зависимость прогноза от признака</h2>
        <form class="chart-controls" action="/#dependence" method="get">
            {carried}
            <label>Признак <select name="feature">{options}</select></label>
            <button type="submit">Рассчитать</button>
        </form>
        <p>Средний прогноз Ridge по тестовым часам при подстановке выбранного значения.</p>
        {result}
    </section>
    """