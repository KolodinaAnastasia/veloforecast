from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import joblib
from dashboard_live import render_live_forecast
from dashboard_explain import load_explanation_data, render_explanation
from dashboard_importance import render_importance
from dashboard_dependence import render_dependence

from evaluate import EVALUATION_PATH

from urllib.parse import parse_qs, urlsplit

from dashboard_chart import CHART_CSS, load_predictions, render_chart

def render_dashboard(evaluation, chart, live, explanation):
    winner = escape(next(
        name
        for name, entry in evaluation["models"].items()
        if entry["config"]["id"] == evaluation["winner"]
    ))
    rows = []

    for row in sorted(evaluation["metrics"], key=lambda item: item["MAE"]):
        model = escape(row["model"])
        rows.append(
            f"<tr><th scope='row'>{model}</th>"
            f"<td>{row['MAE']:.2f}</td>"
            f"<td>{row['RMSE']:.2f}</td>"
            f"<td>{row['mae_saved']:+.2f}</td></tr>"
        )

    return f"""<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Veloforecast · Спрос на велопрокат</title>
    <style>
        body {{ margin: 0; background: #eef4ef; color: #152b27;
                font: 16px Inter, "Segoe UI", sans-serif; }}
        header {{ background: #142f2a; color: #fff; padding: 28px 20px; }}
        .wrap {{ max-width: 960px; margin: 0 auto; }}
        h1 {{ margin: 6px 0; font-size: clamp(24px, 5vw, 42px); }}
        main {{ padding: 20px; }}
        section {{ background: white; border: 1px solid #dce6e0;
                   border-radius: 14px; padding: 20px; overflow-x: auto; }}
        h2 {{ margin-top: 0; }}
        table {{ width: 100%; border-collapse: collapse;
                 font-variant-numeric: tabular-nums; }}
        th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #dce6e0; }}
        thead {{ background: #eef4ef; }}
        {CHART_CSS}
    </style>
</head>
<body>
    <header><div class="wrap">
        <div>Citi Bike · Нью-Йорк</div>
        <h1>Спрос на велопрокат</h1>
    </div></header>
    <main class="wrap">
    {live}
    {chart}
        <section>
            <h2>Качество на отложенном тесте</h2>
            <p>Часов в тесте: {evaluation["test_hours"]}. Модель для прогноза: <strong>{winner}</strong>.</p>
            <table>
                <thead><tr>
                    <th scope="col">Модель</th>
                    <th scope="col">MAE, поездок/ч</th>
                    <th scope="col">RMSE, поездок/ч</th>
                    <th scope="col">Снижение MAE к Naive, поездок/ч</th>
                </tr></thead>
                <tbody>{"".join(rows)}</tbody>
            </table>
        </section>
        {explanation}
    </main>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        if url.path != "/":
            self.send_error(404)
            return

        query = parse_qs(url.query)
        day = query.get("day", [""])[0]
        model = query.get("model", ["Ridge"])[0]
        chart = render_chart(self.server.predictions, day, model)
        live = render_live_forecast()
        explanation = render_explanation(
            self.server.explanation_data,
            self.server.evaluation,
            query.get("ex_day", ["2025-11-11"])[0],
            query.get("ex_hour", ["17"])[0],
            day,
            model,
        )
        dependence = render_dependence(
            self.server.explanation_data[1], self.server.evaluation, query
        )
        content = render_dashboard(
            self.server.evaluation,
            chart,
            live,
            explanation + self.server.importance + dependence,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main():
    evaluation = joblib.load(EVALUATION_PATH)
    with ThreadingHTTPServer(("127.0.0.1", 8765), DashboardHandler) as server:
        server.evaluation = evaluation
        server.predictions = load_predictions()
        server.explanation_data = load_explanation_data()
        server.importance = render_importance(server.explanation_data[1], evaluation)
        print("Дашборд запущен — http://127.0.0.1:8765", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nДашборд остановлен.")


if __name__ == "__main__":
    main()