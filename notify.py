import os
import time

from sources.http import client

WEBHOOKS = {
    "company": os.environ.get("DISCORD_COMPANY", ""),
    "repo": os.environ.get("DISCORD_REPO_FEED", ""),
    "health": os.environ.get("DISCORD_HEALTH", ""),
}
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
DRY_RUN = False


def _post(url, payload):
    for _ in range(5):
        r = client.post(url, json=payload)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 2)) + 0.25)
            continue
        r.raise_for_status()
        # stay under Discord's ~5 req / 2 s per-webhook limit
        if r.headers.get("x-ratelimit-remaining") == "0":
            time.sleep(float(r.headers.get("x-ratelimit-reset-after", 1)))
        return
    raise RuntimeError("Discord rate limited 5x in a row")


def discord(channel: str, lines: list[str]):
    """Post lines to a channel, packed into messages under Discord's 2000-char limit."""
    if not lines:
        return
    if DRY_RUN or not WEBHOOKS[channel]:
        for l in lines:
            print(f"[{channel}] {l}")
        return
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > 1900:
            _post(WEBHOOKS[channel], {"content": chunk, "flags": 4})  # 4 = suppress link embeds
            chunk = ""
        chunk += line + "\n"
    if chunk:
        _post(WEBHOOKS[channel], {"content": chunk, "flags": 4})


def push(title: str, message: str, click: str = "", priority: int = 4):
    if DRY_RUN or not NTFY_TOPIC:
        print(f"[push] {title} — {message}")
        return
    body = {"topic": NTFY_TOPIC, "title": title, "message": message, "priority": priority, "tags": ["briefcase"]}
    if click:
        body["click"] = click
    client.post("https://ntfy.sh/", json=body).raise_for_status()
