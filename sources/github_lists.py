"""Community internship lists -> #repo-feed (unfiltered except for Summer 2027 + still open)."""
import re

from jobs import Job, norm_url
from sources.http import get_json, get_text

SIMPLIFY = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"
VANSH = "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/.github/scripts/listings.json"
NEGAR = "https://raw.githubusercontent.com/negarprh/Canadian-Tech-Internships-2027/main/README.md"


def _listings(source, url, keep):
    out = []
    for x in get_json(url):
        if not (x.get("active") and x.get("is_visible", True) and keep(x)):
            continue
        out.append(Job(source, x["company_name"], x["id"], x["title"], x["url"], x.get("locations") or [],
                       x.get("date_posted"), extra=" ".join(x.get("terms") or []) or x.get("season", "")))
    return out


def simplify():
    return _listings("simplify", SIMPLIFY, lambda x: "Summer 2027" in (x.get("terms") or []))


def vansh():
    return _listings("vansh", VANSH, lambda x: "Summer" in (x.get("season") or ""))


_LINK = re.compile(r"\]\((https?://[^)\s]+)\)\s*$")


def parse_negar(md):
    out, company = [], ""
    for line in md.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or set(cells[0]) <= set("-: ") or cells[0] == "Company":
            continue
        name, role, loc, apply = cells[0], cells[1], cells[2], cells[3]
        if name != "↳":
            company = re.sub(r"\*|\[([^\]]*)\]\([^)]*\)", r"\1", name).strip()
        m = _LINK.search(apply)
        if not m or "🔒" in apply:
            continue
        url = m.group(1)
        out.append(Job("negar", company, norm_url(url), role, url, [l.strip() for l in loc.split("/")]))
    return out


def negar():
    return parse_negar(get_text(NEGAR))


LISTS = {"simplify": simplify, "vansh": vansh, "negar": negar}
