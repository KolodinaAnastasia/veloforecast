from html import escape

import pandas as pd

from baseline import MODEL_DATA
from evaluate import predict_candidate
from explain_forecast import explain_ridge
from trip_hourly import TIMEZONE


LABELS = {
    "lag_same_weekday_hour": "Последний аналог по дню недели и часу",
    "lag_24_from_last_fact": "Поездки за 24 часа до последнего факта",
    "mean_last_24h": "Среднее за последние доступные сутки",
    "mean_last_168h": "Среднее за последнюю доступную неделю",
    "fact_age_hours": "Давность последнего факта",
    "temperature_2m": "Температура",
    "precipitation": "Осадки",
    "wind_speed_10m": "Скорость ветра",
}


def feature_label(name: str) -> str:
    if name.startswith("share_"):
        return f"Доля стартов: {name.removeprefix('share_')}"
    return LABELS.get(name, name)


def load_explanation_data():
    data = pd.read_csv(MODEL_DATA, index_col="hour_utc")
    data.index = pd.to_datetime(data.index, utc=True)
    training = data.loc[data["split"].isin(["train", "validation"])]
    test = data.loc[data["split"] == "test"].copy()
    local = test.index.tz_convert(TIMEZONE)
    test["local_day"] = local.strftime("%Y-%m-%d")
    test["local_hour"] = local.strftime("%H")
    return training, test


def render_explanation(data, evaluation, day, hour, chart_day, chart_model):
    training, test = data
    day_min = test["local_day"].min()
    day_max = test["local_day"].max()
    options = "".join(
        f'<option value="{h:02d}"{" selected" if hour == f"{h:02d}" else ""}>'
        f'{h:02d}:00</option>'
        for h in range(24)
    )

    row = test.loc[(test["local_day"] == day) & (test["local_hour"] == hour)]
    content = "<p>Для выбранного часа нет данных отложенного теста.</p>"
    if len(row) == 1:
        entry = evaluation["models"]["Ridge"]
        config, fitted = entry["config"], entry["fitted"]
        base, contributions = explain_ridge(fitted, config["columns"], training, row)
        prediction = float(predict_candidate(config, fitted, row).iloc[0])
        actual = float(row["rides"].iloc[0])
        rows = "".join(
            f'<tr><th scope="row">{escape(feature_label(name))}</th><td>{effect:+.1f}</td></tr>'
            for name, effect in sorted(contributions.items(), key=lambda item: -abs(item[1]))
        )
        content = f"""
        <p>Базовое значение: {base:.1f} · Прогноз: {prediction:.1f} · Факт: {actual:.0f}</p>
        <table>
            <thead><tr><th scope="col">Признак</th><th scope="col">Вклад, поездок</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
        """

    return f"""
    <section id="explanation">
        <h2>Вклад признаков в прогноз Ridge</h2>
        <form class="chart-controls" action="/#explanation" method="get">
            <input type="hidden" name="day" value="{escape(chart_day)}">
            <input type="hidden" name="model" value="{escape(chart_model)}">
            <label>Дата в Нью-Йорке
                <input type="date" name="ex_day" value="{escape(day)}"
                       min="{day_min}" max="{day_max}" required>
            </label>
            <label>Час <select name="ex_hour">{options}</select></label>
            <button type="submit">Показать вклад</button>
        </form>
        {content}
    </section>
    """