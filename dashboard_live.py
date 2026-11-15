from html import escape

import pandas as pd

from live_forecast import LIVE_PATH
from trip_hourly import TIMEZONE


def format_rides(value: float) -> str:
    return f"{value:,.0f}".replace(",", "\u202f")


def local_time(value) -> str:
    return pd.to_datetime(value, utc=True).tz_convert(TIMEZONE).strftime(
        "%d.%m.%Y %H:%M %Z"
    )


def render_live_forecast() -> str:
    if not LIVE_PATH.exists():
        return """
        <section>
            <h2>Последний прогноз на 24 часа</h2>
            <p>Сохранённых выпусков пока нет.</p>
        </section>
        """

    forecast = pd.read_csv(LIVE_PATH).sort_values("hour_utc")
    first = forecast.iloc[0]
    peak = forecast.loc[forecast["predicted_rides"].idxmax()]
    total = format_rides(forecast["predicted_rides"].sum())
    rows = []

    for row in forecast.itertuples(index=False):
        rows.append(
            f'<tr><th scope="row">{local_time(row.hour_utc)}</th>'
            f"<td>{format_rides(row.predicted_rides)}</td></tr>"
        )

    return f"""
    <section>
        <h2>Последний прогноз на 24 часа</h2>
        <p>Выпуск: {local_time(first["issued_utc"])} · Модель: {escape(first["model"])}</p>
        <p>Последний факт: {local_time(first["last_fact_utc"])}</p>
        <dl>
            <dt>Ожидаемое число стартов за 24 часа</dt>
            <dd><strong>{total}</strong></dd>
            <dt>Пиковый час</dt>
            <dd>{local_time(peak["hour_utc"])} · {format_rides(peak["predicted_rides"])} стартов</dd>
        </dl>
        <details>
            <summary>Прогноз по часам</summary>
            <table>
                <thead>
                    <tr><th scope="col">Час в Нью-Йорке</th><th scope="col">Стартов</th></tr>
                </thead>
                <tbody>{"".join(rows)}</tbody>
            </table>
        </details>
    </section>
    """