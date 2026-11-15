import json
from html import escape

from experiments import JOURNAL


FEATURE_LABELS = {
    "baseline": "Последний доступный аналог",
    "all": "Все признаки",
    "without_calendar": "Без календарных признаков",
    "without_weather": "Без погоды",
    "without_history": "Без лагов и окон",
    "without_geography": "Без долей по районам",
}

PARAMETER_LABELS = {
    "alpha": "α",
    "n_estimators": "Деревьев",
    "max_depth": "Глубина",
    "min_samples_leaf": "Минимум наблюдений в листе",
}


def render_experiments(evaluation):
    if not JOURNAL.is_file():
        return ""

    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    if (
        journal["data_sha256"] != evaluation["data_sha256"]
        or journal["winner"] != evaluation["winner"]
    ):
        return """
        <section>
            <h2>Журнал экспериментов</h2>
            <p>Журнал и отложенный тест рассчитаны для разных версий результатов.</p>
        </section>
        """

    experiments = sorted(journal["experiments"], key=lambda row: (row["MAE"], row["RMSE"]))
    rows = []
    for row in experiments:
        experiment_id = escape(row["id"])
        if row["id"] == journal["winner"]:
            experiment_id = f"<strong>{experiment_id}</strong>"

        parameters = ", ".join(
            f"{PARAMETER_LABELS.get(key, key)} = {value}"
            for key, value in row["parameters"].items()
        ) or "—"
        features = FEATURE_LABELS.get(row["feature_set"], row["feature_set"])

        rows.append(
            f'<tr><th scope="row">{experiment_id}</th>'
            f'<td>{escape(row["model"])}</td>'
            f"<td>{escape(features)}</td>"
            f"<td>{escape(parameters)}</td>"
            f'<td>{row["MAE"]:.2f}</td><td>{row["RMSE"]:.2f}</td></tr>'
        )

    return f"""
    <section>
        <h2>Журнал экспериментов</h2>
        <p>Валидация: {journal["validation_hours"]:,} ч.
        Выбранная конфигурация: <strong>{escape(journal["winner"])}</strong>.</p>
        <details>
            <summary>Сравнение конфигураций ({len(experiments)})</summary>
            <table>
                <thead><tr>
                    <th scope="col">ID</th>
                    <th scope="col">Модель</th>
                    <th scope="col">Признаки</th>
                    <th scope="col">Параметры</th>
                    <th scope="col">MAE, поездок/ч</th>
                    <th scope="col">RMSE, поездок/ч</th>
                </tr></thead>
                <tbody>{"".join(rows)}</tbody>
            </table>
        </details>
    </section>
    """