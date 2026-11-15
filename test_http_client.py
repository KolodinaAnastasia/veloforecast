import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import requests

from http_client import get_json, make_http_session


@contextmanager
def test_server(statuses):
    responses = iter(statuses)
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status = next(responses, 500)
            calls.append(status)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if status == 429:
                self.send_header("Retry-After", "1")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/weather", calls
        finally:
            server.shutdown()
            worker.join()


class HttpClientTests(unittest.TestCase):
    def request(self, url):
        with make_http_session() as session:
            # Для локального теста используем тот же адаптер по HTTP.
            session.mount("http://127.0.0.1", session.get_adapter("https://"))
            with patch("http_client.make_http_session", return_value=session):
                return get_json(url, {}, timeout=(2, 2))

    def test_recovers_after_temporary_errors(self):
        with test_server([503, 429, 200]) as (url, calls):
            self.assertEqual(self.request(url), {"ok": True})
            self.assertEqual(calls, [503, 429, 200])

    def test_does_not_retry_not_found(self):
        with test_server([404]) as (url, calls):
            with self.assertRaises(requests.HTTPError):
                self.request(url)
            self.assertEqual(calls, [404])

    def test_stops_after_retry_limit(self):
        with test_server([503, 503, 503, 503]) as (url, calls):
            with self.assertRaises(requests.exceptions.RetryError):
                self.request(url)
            self.assertEqual(calls, [503, 503, 503, 503])


if __name__ == "__main__":
    unittest.main()