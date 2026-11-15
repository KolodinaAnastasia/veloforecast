from html import escape

import pandas as pd

from evaluate import PREDICTIONS_PATH
from trip_hourly import TIMEZONE


MODEL_NAMES = ("Naive", "Ridge", "Boosting")

CHART_CSS = """
section + section { margin-top: 18px; }
.chart-controls { display: flex; align-items: end; gap: 14px; flex-wrap: wrap; }
.chart-controls label { display: grid; gap: 5px; }
.chart-controls input, .chart-controls select, .chart-controls button {
    font: inherit; padding: 7px 10px; border: 1px solid #adbfba;
    border-radius: 7px; background: white; color: inherit;
}
.chart-controls button { background: #e8f5ed; cursor: pointer; }
.chart-key { display: flex; gap: 16px; }
.chart-key span::before {
    content: ""; display: inline-block; width: 12px; height: 12px; margin-right: 6px;
}
.chart-area { overflow-x: auto; }
.chart-hours {
    display: grid; grid-auto-flow: column; grid-auto-columns: minmax(24px, 1fr);
    gap: 4px; min-width: 670px;
}
.hour { text-align: center; font-size: 12px; }
.hour-bars {
    display: flex; justify-content: center; align-items: end;
    gap: 3px; height: 200px; margin-bottom: 5px;
    border-bottom: 1px solid #adbfba;
}
.hour-bars i { width: 36%; border-radius: 3px 3px 0 0; }
.actual, .chart-key .actual-key::before { background: #137a67; }
.predicted, .chart-key .prediction-key::before { background: #c25a2d; }
"""


def load_predictions() -> pd.DataFrame:
    data = pd.read_csv(PREDICTIONS_PATH)
    local = pd.to_datetime(data["hour_utc"], utc=True).dt.tz_convert(TIMEZONE)
    return data.assign(
        day=local.dt.strftime("%Y-%m-%d"),
        hour=local.dt.strftime("%H"),
        local_time=local.dt.strftime("%H:%M %Z"),
    )


def render_chart(data: pd.DataFrame, day: str, model: str) -> str:
    days = data.groupby("day").size()
    if day not in days.index:
        full_days = days[days == 24]
        day = str(full_days.index[0] if not full_days.empty else days.index[0])
    if model not in MODEL_NAMES:
        model = "Ridge"

    daily = data.loc[data["day"] == day]
    scale = max(1.0, float(daily[["actual", model]].max().max()))
    bars = []

    for _, row in daily.iterrows():
        actual = float(row["actual"])
        predicted = float(row[model])
        details = escape(
            f"{row['local_time']} · факт {actual:,.0f} · прогноз {predicted:,.0f}"
        )
        bars.append(
            f'<div class="hour" title="{details}">'
            f'<div class="hour-bars">'
            f'<i class="actual" style="height:{100 * actual / scale:.2f}%"></i>'
            f'<i class="predicted" style="height:{100 * predicted / scale:.2f}%"></i>'
            f'</div>{row["hour"]}</div>'
        )

    options = "".join(
        f'<option value="{name}"{" selected" if model == name else ""}>{name}</option>'
        for name in MODEL_NAMES
    )

    return f"""
    <section>
        <h2>Факт и прогноз по часам</h2>
        <form class="chart-controls" action="/" method="get">
            <label>Дата в Нью-Йорке
                <input type="date" name="day" value="{day}"
                       min="{days.index[0]}" max="{days.index[-1]}" required>
            </label>
            <label>Модель <select name="model">{options}</select></label>
            <button type="submit">Показать</button>
        </form>
        <p class="chart-key">
            <span class="actual-key">Факт</span>
            <span class="prediction-key">Прогноз</span>
        </p>
        <div class="chart-area">
            <div class="chart-hours">{"".join(bars)}</div>
        </div>
        <p>Часов в выборке: {len(daily)}</p>
    </section>"""