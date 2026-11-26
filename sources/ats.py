"""Public job-board feeds. Each fetcher: (company_name, slug) -> list[Job]."""
from datetime import datetime

from jobs import Job
import html as htmllib
import re

from sources.http import client, get_json, get_text, post_json


def _clean(s):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _ts(s):
    if not s:
        return None
    if isinstance(s, (int, float)):
        return int(s / 1000 if s > 1e11 else s)
    try:
        return int(datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def greenhouse(company, slug):
    data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    return [
        Job("greenhouse", company, str(j["id"]), j["title"], j["absolute_url"],
            [(j.get("location") or {}).get("name", "")], _ts(j.get("first_published") or j.get("updated_at")))
        for j in data.get("jobs", [])
    ]


def lever(company, slug):
    data = get_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    out = []
    for j in data:
        cat = j.get("categories") or {}
        locs = cat.get("allLocations") or [cat.get("location", "")]
        out.append(Job("lever", company, j["id"], j["text"], j["hostedUrl"], locs, _ts(j.get("createdAt")),
                       extra=cat.get("commitment", "") or ""))
    return out


def ashby(company, slug):
    data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        out.append(Job("ashby", company, j["id"], j["title"], j["jobUrl"], locs, _ts(j.get("publishedAt"))))
    return out


def workday(company, slug):
    """slug = 'tenant|wdN|site' e.g. 'nvidia|wd5|NVIDIAExternalCareerSite'."""
    tenant, wd, site = slug.split("|")
    base = f"https://{tenant}.{wd}.myworkdayjobs.com"
    out, seen = [], set()
    for query in ("intern", "co-op", "summer analyst"):
        offset = 0
        while offset < 200:
            data = post_json(f"{base}/wday/cxs/{tenant}/{site}/jobs",
                             {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": query},
                             headers={"Origin": base, "Referer": f"{base}/{site}", "Accept-Language": "en-US",
                                      "Accept": "application/json", "Content-Type": "application/json"})
            posts = data.get("jobPostings", [])
            for j in posts:
                path = j.get("externalPath", "")
                if not path or path in seen:
                    continue
                seen.add(path)
                loc = j.get("locationsText", "")
                if loc and loc.split()[0].isdigit() and "location" in loc.lower():
                    loc = ""  # "3 Locations" -> unknown
                out.append(Job("workday", company, path.rsplit("_", 1)[-1], j.get("title", ""),
                               f"{base}/{site}{path}", [loc], extra=" ".join(j.get("bulletFields") or [])))
            offset += 20
            if len(posts) < 20 or offset >= data.get("total", 0):
                break
    return out


def smartrecruiters(company, slug):
    out, offset = [], 0
    while offset < 500:
        data = get_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                        params={"limit": 100, "offset": offset, "q": "intern"})
        for j in data.get("content", []):
            loc = j.get("location") or {}
            locs = [loc.get("fullLocation") or ", ".join(x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x)]
            out.append(Job("smartrecruiters", company, str(j["id"]), j["name"],
                           f"https://jobs.smartrecruiters.com/{slug}/{j['id']}", locs, _ts(j.get("releasedDate"))))
        offset += 100
        if offset >= data.get("totalFound", 0):
            break
    return out


def workable(company, slug):
    data = get_json(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    out = []
    for j in data.get("jobs", []):
        locs = [", ".join(x for x in (l.get("city"), l.get("region"), l.get("country")) if x) for l in j.get("locations") or []]
        locs = locs or [", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)]
        out.append(Job("workable", company, j["shortcode"], j["title"],
                       j.get("url") or f"https://apply.workable.com/{slug}/j/{j['shortcode']}", locs, _ts(j.get("published_on"))))
    return out


def bamboohr(company, slug):
    data = get_json(f"https://{slug}.bamboohr.com/careers/list")
    out = []
    for j in data.get("result", []):
        loc = j.get("location") or {}
        ats = j.get("atsLocation") or {}
        locs = [", ".join(x for x in (loc.get("city"), loc.get("state"), ats.get("country")) if x)]
        out.append(Job("bamboohr", company, str(j["id"]), j["jobOpeningName"],
                       f"https://{slug}.bamboohr.com/careers/{j['id']}", locs))
    return out


def recruitee(company, slug):
    data = get_json(f"https://{slug}.recruitee.com/api/offers/")
    out = []
    for j in data.get("offers", []):
        locs = [l.get("name") or ", ".join(x for x in (l.get("city"), l.get("state"), l.get("country")) if x)
                for l in j.get("locations") or []] or [j.get("location", "")]
        out.append(Job("recruitee", company, str(j["id"]), j["title"], j["careers_url"], locs, _ts(j.get("published_at"))))
    return out


def oracle(company, slug):
    """Oracle HCM Candidate Experience. slug = 'host|siteNumber' e.g. 'jpmc.fa.oraclecloud.com|CX_1001'."""
    host, site = slug.split("|")
    out, seen = [], set()
    for kw in ("intern", "summer analyst"):
        url = (f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
               f"?onlyData=true&expand=requisitionList.secondaryLocations"
               f'&finder=findReqs;siteNumber={site},keyword="{kw}",limit=200,sortBy=POSTING_DATES_DESC')
        data = get_json(url)
        for item in data.get("items", []):
            for j in item.get("requisitionList", []):
                if j["Id"] in seen:
                    continue
                seen.add(j["Id"])
                locs = [j.get("PrimaryLocation", "")] + [s.get("Name", "") for s in j.get("secondaryLocations") or []]
                out.append(Job("oracle", company, str(j["Id"]), j["Title"],
                               f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{j['Id']}",
                               locs, _ts(j.get("PostedDate"))))
    return out


def jibe(company, slug):
    """Jibe/iCIMS Attract career sites. slug = host, e.g. 'careers.amd.com' or 'kinaxis.jibeapply.com'."""
    out, seen = [], set()
    for kw in ("intern", "co-op"):
        for page in range(1, 6):
            data = get_json(f"https://{slug}/api/jobs", params={"keywords": kw, "limit": 100, "page": page})
            rows = data.get("jobs", [])
            for r in rows:
                j = r["data"]
                if j["req_id"] in seen:
                    continue
                seen.add(j["req_id"])
                locs = [j.get("full_location") or ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)]
                out.append(Job("jibe", company, j["req_id"], j["title"],
                               j.get("canonical_url") or f"https://{slug}/jobs/{j['req_id']}", locs, _ts(j.get("posted_date"))))
            if len(rows) < 100:
                break
    return out


def gem(company, slug):
    data = get_json(f"https://api.gem.com/job_board/v0/{slug}/job_posts/")
    out = []
    for j in data:
        locs = [(o.get("location") or {}).get("name", "") for o in j.get("offices") or []] or [(j.get("location") or {}).get("name", "")]
        out.append(Job("gem", company, j["id"], j["title"], j["absolute_url"], locs,
                       _ts(j.get("first_published_at")), extra=j.get("employment_type", "")))
    return out


def rippling(company, slug):
    data = get_json(f"https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs")
    return [Job("rippling", company, j["uuid"], j["name"], j["url"], [(j.get("workLocation") or {}).get("label", "")])
            for j in data]


def eightfold(company, slug):
    """Eightfold sites that expose the public v2 API. slug = 'host|domain' e.g. 'career.mlp.com|mlp.com'."""
    host, domain = slug.split("|")
    out = []
    for start in range(0, 500, 100):
        d = get_json(f"https://{host}/api/apply/v2/jobs",
                     params={"domain": domain, "query": "intern", "start": start, "num": 100, "sort_by": "timestamp"})
        rows = d.get("positions") or []
        for j in rows:
            out.append(Job("eightfold", company, str(j["id"]), j["name"],
                           j.get("canonicalPositionUrl") or f"https://{host}/careers/job/{j['id']}",
                           j.get("locations") or [j.get("location", "")], j.get("t_create")))
        if len(rows) < 100:
            break
    return out


def eightfold_pcsx(company, slug):
    """Newer Eightfold sites (Microsoft, Qualcomm, PayPal) where /api/apply/v2 is blocked. slug = 'host|domain'."""
    host, domain = slug.split("|")
    out, seen = [], set()
    for start in range(0, 400, 10):  # pcsx pages are fixed at 10
        d = get_json(f"https://{host}/api/pcsx/search",
                     params={"domain": domain, "query": "intern", "start": start, "sort_by": "timestamp"})["data"]
        rows = d.get("positions") or []
        for j in rows:
            if j["id"] in seen:
                continue
            seen.add(j["id"])
            out.append(Job("eightfold", company, str(j["id"]), j["name"], f"https://{host}{j['positionUrl']}",
                           j.get("standardizedLocations") or j.get("locations") or [], j.get("postedTs")))
        if len(rows) < 10 or start + 10 >= (d.get("count") or 0):
            break
    return out


def icims(company, slug):
    """iCIMS career portal search pages. slug = host, e.g. 'careers-sig.icims.com'."""
    out, seen = [], set()
    for page in range(0, 10):
        h = get_text(f"https://{slug}/jobs/search",
                     params={"ss": 1, "searchKeyword": "intern", "in_iframe": 1, "pr": page})
        links = list(re.finditer(rf'href="(https://{re.escape(slug)}/jobs/(\d+)/[^"]+)"', h))
        new = 0
        for i, m in enumerate(links):
            url, jid = m.group(1).split("?")[0], m.group(2)
            if jid in seen:
                continue
            chunk = h[m.start(): links[i + 1].start() if i + 1 < len(links) else m.start() + 6000]
            title = re.search(r"<h3[^>]*>(.*?)</h3>", chunk, re.S)
            if not title:
                continue
            seen.add(jid)
            new += 1
            text = _clean(chunk)
            loc = re.search(r"Location\s*:?\s*((?:[A-Z]{2}-[\w .-]+(?:\s*\|\s*)?)+|[^|]{3,60}?)(?=\s{2}|$| [A-Z][a-z]+ [A-Z][a-z]+\b)", text)
            out.append(Job("icims", company, jid, _clean(title.group(1)), url, [loc.group(1).strip() if loc else ""]))
        if new == 0:
            break
    return out


def avature(company, slug):
    """Avature career sites. slug = search page URL without scheme, e.g. 'bloomberg.avature.net/careers/SearchJobs'."""
    out, seen, offset = [], set(), 0
    for _ in range(40):
        h = get_text(f"https://{slug}", params={"search": "intern", "jobRecordsPerPage": 50, "jobOffset": offset})
        arts = re.findall(r"<article[^>]*>.*?</article>", h, re.S)
        offset += max(len(arts), 1)
        new = 0
        for a in arts:
            m = re.search(r'href="([^"]+/JobDetail/[^"]+?/(\d+))"[^>]*>(.*?)</a>', a, re.S)
            if not m or m.group(2) in seen:
                continue
            seen.add(m.group(2))
            new += 1
            parts = [p for p in (_clean(x) for x in re.split(r"<[^>]+>", a)) if p]
            title = _clean(m.group(3))
            after = parts[parts.index(title) + 1:] if title in parts else parts
            loc = next((p for p in after if p.lower() not in ("apply", "save", "view role")), "")
            out.append(Job("avature", company, m.group(2), title, m.group(1), [loc]))
        if new == 0:
            break
    return out


def successfactors(company, slug):
    """SAP SuccessFactors RMK career sites via their RSS feed. slug = host, e.g. 'jobs.scotiabank.com'."""
    out = []
    for kw in ("intern", "co-op"):
        x = get_text(f"https://{slug}/services/rss/job/", params={"locale": "en_US", "keywords": kw})
        for item in re.findall(r"<item>(.*?)</item>", x, re.S):
            title = _clean(re.sub(r"<!\[CDATA\[|\]\]>", "", re.search(r"<title>(.*?)</title>", item, re.S).group(1)))
            link = _clean(re.search(r"<link>(.*?)</link>", item, re.S).group(1))
            m = re.match(r"(.*?)\s*\(([^()]*)\)\s*$", title)  # "Title (City, ST, CA, POSTAL)"
            title, loc = (m.group(1), m.group(2)) if m else (title, "")
            jid = re.search(r"/(\d+)/?$", link)
            out.append(Job("successfactors", company, jid.group(1) if jid else link, title, link, [loc]))
    return list({j.native_id: j for j in out}.values())


def radancy(company, slug):
    """Radancy (TMP) career sites, e.g. jobs.intuit.com. slug = host."""
    out, seen = [], set()
    for page in range(1, 11):
        d = get_json(f"https://{slug}/search-jobs/results", headers={"X-Requested-With": "XMLHttpRequest"},
                     params={"ActiveFacetID": 0, "CurrentPage": page, "RecordsPerPage": 100, "Keywords": "intern",
                             "SearchResultsModuleName": "Search Results", "SearchFiltersModuleName": "Search Filters",
                             "SortCriteria": 0, "SortDirection": 0, "SearchType": 5})
        new = 0
        for li in re.findall(r"<li.*?</li>", d.get("results") or "", re.S):
            m = re.search(r'href="(/job/[^"]+/(\d+))"', li)
            if not m or m.group(2) in seen:
                continue
            seen.add(m.group(2))
            new += 1
            title = re.search(r"<h2[^>]*>(.*?)</h2>", li, re.S)
            loc = re.search(r'class="job-location[^"]*"[^>]*>(.*?)</span>', li, re.S)
            parts = [p for p in (_clean(x) for x in re.split(r"<[^>]+>", li)) if p and p != "Save"]
            out.append(Job("radancy", company, m.group(2), _clean(title.group(1)) if title else parts[0],
                           f"https://{slug}{m.group(1)}", [_clean(loc.group(1)) if loc else (parts[1] if len(parts) > 1 else "")]))
        if new == 0:
            break
    return out


def atlassian(company, slug):
    data = get_json("https://www.atlassian.com/endpoint/careers/listings")
    return [Job("atlassian", company, str(j["id"]), j["title"], (j.get("portalJobPost") or {}).get("portalUrl") or j.get("applyUrl", ""),
                j.get("locations") or []) for j in data]


FETCHERS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "workday": workday,
    "smartrecruiters": smartrecruiters,
    "workable": workable,
    "bamboohr": bamboohr,
    "recruitee": recruitee,
    "oracle": oracle,
    "jibe": jibe,
    "gem": gem,
    "rippling": rippling,
    "eightfold": eightfold,
    "eightfold_pcsx": eightfold_pcsx,
    "icims": icims,
    "avature": avature,
    "successfactors": successfactors,
    "radancy": radancy,
    "atlassian": atlassian,
}
