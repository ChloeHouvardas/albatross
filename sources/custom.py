"""Readers for companies with their own career sites. Each: (company_name) -> list[Job].

Meta and Tesla block unauthenticated access; their roles arrive via the GitHub lists
(main.py forwards matching list roles for companies without a direct reader to #company-roles).
"""
import json
import re
import time
from datetime import datetime

from jobs import Job
from sources.http import get_json, get_text, post_json


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


def _citadel(company, base, listing):
    """Next.js page embeds every posting as escaped JSON objects starting with {"_id":"career-..."."""
    try:
        h = get_text(base + listing)
    except Exception:  # bot protection 403s now and then; one slow retry
        time.sleep(8)
        h = get_text(base + listing)
    h = h.replace('\\"', '"')
    out, seen, dec = [], set(), json.JSONDecoder()
    for m in re.finditer(r'\{"_id":"career-', h):
        try:
            j, _ = dec.raw_decode(h, m.start())
        except ValueError:
            continue
        if j["_id"] in seen or "title" not in j:
            continue
        seen.add(j["_id"])
        locs = [", ".join(x for x in (l.get("city"), l.get("country")) if x) for l in j.get("locations") or []]
        ts = j.get("publishedAt")
        out.append(Job("citadel", company, j["_id"], j["title"], base + j["href"], locs,
                       int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()) if ts else None,
                       extra=j.get("experience", "")))
    return out


def citadel(company):
    return _citadel(company, "https://www.citadel.com", "/careers/open-opportunities/?type=students")


def citadel_securities(company):
    return _citadel(company, "https://www.citadelsecurities.com", "/careers/open-opportunities/students/")


_DESHAW = re.compile(r'href="/careers/([a-z0-9-]+-(\d+))".{0,1500}?job-display-name">([^<]+)<', re.S)


def deshaw(company):
    """Server-rendered list; the office is in the title, e.g. 'Software Developer Intern (New York) – Summer 2027'."""
    out, seen = [], set()
    for slug, jid, title in _DESHAW.findall(get_text("https://www.deshaw.com/careers/choose-your-path")):
        if jid in seen:
            continue
        seen.add(jid)
        title = title.strip()
        loc = re.findall(r"\(([^)]+)\)", title)
        out.append(Job("deshaw", company, jid, title, f"https://www.deshaw.com/careers/{slug}", loc[:1]))
    return out


def ibm(company):
    """careers.ibm.com is backed by IBM's public site-search API (also covers HashiCorp, now part of IBM)."""
    out = []
    for start in range(0, 600, 100):
        d = post_json("https://www-api.ibm.com/search/api/v2", {
            "appId": "careers", "scopes": ["careers2"], "size": 100, "from": start,
            "query": {"bool": {"must": [{"simple_query_string": {"query": "intern", "fields": ["title^3", "description"]}}]}},
            "_source": ["title", "url", "field_keyword_19", "field_keyword_18"]})
        hits = d["hits"]["hits"]
        for h in hits:
            x = h["_source"]
            jid = x["url"].rsplit("=", 1)[-1]
            out.append(Job("ibm", company, jid, x["title"], x["url"], [x.get("field_keyword_19", "")],
                           extra=x.get("field_keyword_18", "")))
        if len(hits) < 100:
            break
    return out


READERS = {"amazon": amazon, "google": google, "apple": apple, "citadel": citadel,
           "citadel_securities": citadel_securities, "deshaw": deshaw, "ibm": ibm}
