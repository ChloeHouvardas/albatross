import time

import httpx

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

client = httpx.Client(
    timeout=httpx.Timeout(45.0, connect=10.0),
    headers={"User-Agent": UA, "Accept": "application/json, text/html;q=0.9, */*;q=0.8"},
    follow_redirects=True,
    limits=httpx.Limits(max_connections=32, max_keepalive_connections=32),
)


def _req(method, url, **kw):
    """One retry on timeouts / 5xx / 429 — transient blips shouldn't count as a failed source."""
    for attempt in range(2):
        try:
            r = client.request(method, url, **kw)
            if r.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(3)
                continue
            r.raise_for_status()
            return r
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt:
                raise
            time.sleep(3)


def get_json(url, **kw):
    return _req("GET", url, **kw).json()


def post_json(url, body, **kw):
    return _req("POST", url, json=body, **kw).json()


def get_text(url, **kw):
    return _req("GET", url, **kw).text
