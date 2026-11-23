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
    """Retry timeouts / 5xx once and rate limits (429) up to 3x — transient blips shouldn't fail a source."""
    for attempt in range(4):
        try:
            r = client.request(method, url, **kw)
            if r.status_code == 429 and attempt < 3:
                time.sleep(min(float(r.headers.get("retry-after", 0) or 0) or 10 * (attempt + 1), 60))
                continue
            if r.status_code in (500, 502, 503, 504) and attempt == 0:
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
