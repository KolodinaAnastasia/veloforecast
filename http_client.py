import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def make_http_session() -> requests.Session:
    retry = Retry(
        total=3,
        allowed_methods={"GET", "HEAD"},
        status_forcelist=(429, 500, 502, 503, 504),
        backoff_factor=1,
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def get_json(url: str, params: dict, timeout: tuple[int, int]) -> dict:
    with make_http_session() as session:
        with session.get(url, params=params, timeout=timeout) as response:
            response.raise_for_status()
            return response.json()