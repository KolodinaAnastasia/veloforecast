import json
from pathlib import Path

import requests
from shapely import Point, prepare
from shapely.geometry import shape


BOUNDARIES_URL = (
    "https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/"
    "NYC_Borough_Boundary/FeatureServer/0/query"
)
BOUNDARIES_PATH = Path(__file__).resolve().parent / "state" / "nyc_boroughs.geojson"
BOROUGHS = {"Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"}


def load_boroughs():
    cached = BOUNDARIES_PATH.exists()
    if cached:
        data = json.loads(BOUNDARIES_PATH.read_text(encoding="utf-8"))
    else:
        response = requests.get(
            BOUNDARIES_URL,
            params={
                "where": "1=1",
                "outFields": "BoroName",
                "outSR": 4326,
                "f": "geojson",
            },
            timeout=(10, 90),
        )
        response.raise_for_status()
        data = response.json()

    if data.get("type") != "FeatureCollection":
        raise ValueError(f"Сервер не вернул GeoJSON: {data.get('error')}")

    boroughs = {
        feature["properties"]["BoroName"]: shape(feature["geometry"])
        for feature in data["features"]
    }
    if set(boroughs) != BOROUGHS:
        raise ValueError(f"Ожидались пять районов Нью-Йорка, получены {sorted(boroughs)}.")

    for geometry in boroughs.values():
        if geometry.is_empty or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("В GeoJSON обнаружена пустая или неподходящая геометрия.")
        prepare(geometry)

    if not cached:
        BOUNDARIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = BOUNDARIES_PATH.with_suffix(".part")
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        temporary.replace(BOUNDARIES_PATH)

    return boroughs


def find_borough(boroughs, latitude: float, longitude: float) -> str | None:
    point = Point(longitude, latitude)
    for name, geometry in boroughs.items():
        if geometry.covers(point):
            return name
    return None


if __name__ == "__main__":
    boroughs = load_boroughs()
    print(f"Районов загружено: {len(boroughs)}")
    print(f"Старт из CSV: {find_borough(boroughs, 40.742388, -73.997262)}")
    outside = find_borough(boroughs, 40.7282, -74.0776)
    print(f"Контрольная точка в Джерси-Сити: {outside or 'вне Нью-Йорка'}")