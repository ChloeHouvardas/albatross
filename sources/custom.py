"""Readers for companies with their own career sites. Each: (company_name) -> list[Job].

Microsoft and Meta block unauthenticated API access; their roles arrive via the GitHub lists
(main.py forwards matching list roles for companies without a direct reader to #company-roles).
"""
import json
import re
from datetime import datetime

from jobs import Job
from sources.http import get_json, get_text


def amazon(company):
    out, seen = [], set()
    for q in ("intern", "co-op"):
        for offset in range(0, 500, 100):
            d = get_json("https://www.amazon.jobs/en/search.json",
                         params={"base_query": q, "result_limit": 100, "offset": offset, "sort": "recent"})
            for j in d.get("jobs", []):
                if j["id_icims"] in seen:
                    continue
                seen.add(j["id_icims"])
                try:
                    ts = int(datetime.strptime(j.get("posted_date", ""), "%B %d, %Y").timestamp())
                except ValueError:
                    ts = None
                out.append(Job("amazon", company, j["id_icims"], j["title"].strip(),
                               "https://www.amazon.jobs" + j["job_path"],
                               [j.get("normalized_location") or j.get("location", "")], ts))
            if offset + 100 >= d.get("hits", 0):
                break
    return out


def _google_page(q, page):
    h = get_text("https://www.google.com/about/careers/applications/jobs/results",
                 params={"q": q, "target_level": "INTERN_AND_APPRENTICE", "page": page, "sort_by": "date"})
    m = re.search(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(.*?), sideChannel", h, re.S)
    return json.loads(m.group(1))


def google(company):
    out = []
    for page in range(1, 11):
        d = _google_page("", page)
        rows = d[0] or []
        for j in rows:
            locs = [l[0] for l in (j[9] or [])]
            ts = j[12][0] if j[12] else None
            out.append(Job("google", company, j[0], j[1],
                           f"https://www.google.com/about/careers/applications/jobs/results/{j[0]}", locs, ts))
        if len(rows) < 20 or page * 20 >= (d[2] or 0):
            break
    if not out:
        raise RuntimeError("Google page parsed but no jobs found — layout may have changed")
    return out


def apple(company):
    out = []
    for page in range(1, 16):
        h = get_text("https://jobs.apple.com/en-us/search",
                     params={"team": "internships-STDNT-INTRN", "sort": "newest", "page": page})
        raw = re.search(r'__staticRouterHydrationData = JSON.parse\((".*?")\);', h, re.S).group(1)
        s = json.loads(json.loads(raw))["loaderData"]["search"]
        rows = s.get("searchResults") or []
        for j in rows:
            locs = [", ".join(x for x in (l.get("city"), l.get("stateProvince"), l.get("countryName")) if x)
                    for l in j.get("locations") or []]
            out.append(Job("apple", company, j["positionId"], j["postingTitle"],
                           f"https://jobs.apple.com/en-us/details/{j['positionId']}/{j.get('transformedPostingTitle', '')}",
                           locs))
        if len(rows) < 20 or page * 20 >= s.get("totalRecords", 0):
            break
    return out


READERS = {"amazon": amazon, "google": google, "apple": apple}
