from sources import ats, github_lists
from jobs import norm_url


def test_greenhouse(monkeypatch):
    monkeypatch.setattr(ats, "get_json", lambda url, **kw: {"jobs": [
        {"id": 1, "title": "SWE Intern", "absolute_url": "https://b/1", "location": {"name": "Toronto"},
         "first_published": "2026-11-01T00:00:00Z"}]})
    [j] = ats.greenhouse("Stripe", "stripe")
    assert (j.id, j.locations, j.posted) == ("greenhouse:Stripe:1", ["Toronto"], 1793491200)


def test_lever(monkeypatch):
    monkeypatch.setattr(ats, "get_json", lambda url, **kw: [
        {"id": "a", "text": "SWE Intern", "hostedUrl": "https://l/a", "createdAt": 1793491200000,
         "categories": {"location": "NYC", "allLocations": ["NYC", "SF"], "commitment": "Intern"}}])
    [j] = ats.lever("Palantir", "palantir")
    assert j.locations == ["NYC", "SF"] and j.posted == 1793491200


def test_ashby_skips_unlisted(monkeypatch):
    monkeypatch.setattr(ats, "get_json", lambda url, **kw: {"jobs": [
        {"id": "x", "title": "A", "jobUrl": "u", "location": "SF", "isListed": False},
        {"id": "y", "title": "B", "jobUrl": "u2", "location": "SF", "secondaryLocations": [{"location": "NYC"}]}]})
    [j] = ats.ashby("Ramp", "ramp")
    assert j.native_id == "y" and j.locations == ["SF", "NYC"]


def test_workday_paths_and_multi_location(monkeypatch):
    calls = []

    def fake(url, body, **kw):
        calls.append(body["searchText"])
        return {"total": 1, "jobPostings": [{"title": "SWE Intern", "externalPath": "/job/Toronto/SWE-Intern_R123",
                                             "locationsText": "3 Locations"}]}
    monkeypatch.setattr(ats, "post_json", fake)
    jobs = ats.workday("RBC", "rbc|wd3|Site")
    assert len(jobs) == 1  # deduped across the 3 search queries
    assert jobs[0].url == "https://rbc.wd3.myworkdayjobs.com/Site/job/Toronto/SWE-Intern_R123"
    assert jobs[0].locations == [""] and jobs[0].native_id == "R123"


def test_negar_readme():
    md = """| Company | Role | Location | Apply | Date Posted |
|--------|------|----------|:-----:|--------------|
| Shopify | Software Engineer Intern (Summer 2027) | Montreal, QC / Toronto, ON | [![Apply](https://img)](https://www.shopify.com/careers/x) | Nov 16, 2026 |
 | ↳ | Data Intern | Toronto, ON | [![Apply](https://img)](https://www.shopify.com/careers/y) | Nov 16, 2026 |
| Zurich | Data Intern | Toronto, ON | Closed🔒 | Nov 16, 2026 |
"""
    jobs = github_lists.parse_negar(md)
    assert [(j.company, j.title) for j in jobs] == [("Shopify", "Software Engineer Intern (Summer 2027)"), ("Shopify", "Data Intern")]
    assert jobs[0].locations == ["Montreal, QC", "Toronto, ON"]


def test_norm_url():
    assert norm_url("https://X.com/a/?utm_source=Simplify&ref=Simplify") == "https://x.com/a"
    assert norm_url("https://x.com/a?gh_jid=5&utm_source=y") == "https://x.com/a?gh_jid=5"


def test_successfactors_rss(monkeypatch):
    rss = """<rss><channel><item><title><![CDATA[Software Developer Co-op - Summer 2027 (Toronto, ON, CA, M5H 1H1)]]></title>
<link>https://jobs.scotiabank.com/job/Toronto-Software-Developer/1234567/</link></item></channel></rss>"""
    monkeypatch.setattr(ats, "get_text", lambda url, **kw: rss)
    [j] = ats.successfactors("Scotiabank", "jobs.scotiabank.com")
    assert (j.title, j.locations, j.native_id) == ("Software Developer Co-op - Summer 2027", ["Toronto, ON, CA, M5H 1H1"], "1234567")


def test_avature(monkeypatch):
    page = """<article class="article article--result"><h3><a class="link" href="https://x.avature.net/careers/JobDetail/SWE-Intern/42">
    Software Engineering Internship (Summer 2027) </a></h3><div class="subtitle"><span>United States - NY New York</span></div>
    <a href="#">Apply</a></article>"""
    pages = iter([page, ""])
    monkeypatch.setattr(ats, "get_text", lambda url, **kw: next(pages))
    [j] = ats.avature("Two Sigma", "x.avature.net/careers/SearchJobs")
    assert (j.native_id, j.title, j.locations) == ("42", "Software Engineering Internship (Summer 2027)", ["United States - NY New York"])


def test_zapply_readme():
    md = """| Company | Role | Location | Posted | Visa | **Apply** |
|---------|------|----------|--------|------|----------|
| **Roblox** | \\[Summer 2027 Canada\\] Software Engineer Intern, Engine | Vancouver, BC | 5d |  | [<img src="images/apply.png" width="100" alt="Apply">](https://zapply.jobs/l/d/greenhouse-roblox-1?s=gh) |
"""
    [j] = github_lists.parse_zapply(md)
    assert (j.company, j.title, j.locations) == ("Roblox", "[Summer 2027 Canada] Software Engineer Intern, Engine", ["Vancouver, BC"])


def test_mtl_readme():
    md = """| Employer | Role | Start term | Category | Locations | Posted | Application |
| --- | --- | --- | --- | --- | --- | --- |
| GIRO | Software Developer Intern | Winter 2027 | Software | Montreal, QC, Canada | 2026-08-31 | [Apply](https://giro.example/job/1) |
"""
    [j] = github_lists.parse_mtl(md)
    assert (j.company, j.extra, j.locations, j.url) == ("GIRO", "Winter 2027", ["Montreal, QC, Canada"], "https://giro.example/job/1")
