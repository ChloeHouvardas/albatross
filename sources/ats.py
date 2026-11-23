"""Public job-board feeds. Each fetcher: (company_name, slug) -> list[Job]."""
from datetime import datetime

from jobs import Job
from sources.http import client, get_json, post_json


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
}
