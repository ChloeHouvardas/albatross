"""One-off: build companies.yaml from the PRD company list.

1. Mine ATS board slugs from SimplifyJobs listing URLs.
2. Probe Greenhouse/Lever/Ashby with name-derived slugs for anything unmapped.
3. Verify every mapping returns data. Unmapped -> ats: none (covered by GitHub lists).
Run: python scripts/discover.py  (rewrites companies.yaml, keeps manual entries marked `manual: true`)
"""
import collections
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sources.ats import FETCHERS  # noqa: E402
from sources.github_lists import SIMPLIFY  # noqa: E402
from sources.http import client, get_json  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CUSTOM = {"Amazon": "amazon", "Google": "google", "Apple": "apple"}
# Extra names companies go by in the GitHub lists / on their boards.
ALIASES = {
    "RBC": ["Royal Bank of Canada"], "TD": ["TD Bank", "TD Securities"], "BMO": ["Bank of Montreal", "BMO Financial"],
    "Scotiabank": ["Bank of Nova Scotia"], "CIBC": ["Canadian Imperial Bank of Commerce"], "EA": ["Electronic Arts"],
    "Susquehanna": ["Susquehanna International Group", "SIG"], "Manulife": ["Manulife Financial"],
    "Sun Life": ["Sun Life Financial"], "Millennium": ["Millennium Management"], "Five Rings": ["Five Rings Capital"],
    "Akuna": ["Akuna Capital"], "Tower Research": ["Tower Research Capital"], "D. E. Shaw": ["D.E. Shaw", "DE Shaw"],
    "Bridgewater": ["Bridgewater Associates"], "Jump Trading": ["Jump"], "Optiver": ["Optiver US"],
    "IMC": ["IMC Trading"], "Virtu": ["Virtu Financial"], "National Bank": ["National Bank of Canada"],
    "Desjardins": ["Desjardins Group", "Mouvement Desjardins"], "CPP Investments": ["CPP Investment Board"],
    "JPMorgan Chase": ["JPMorgan", "JP Morgan", "J.P. Morgan"], "Goldman Sachs": ["Goldman"],
    "Block": ["Square"], "Meta": ["Facebook"], "Google": ["Alphabet"], "Snap": ["Snapchat"],
    "Blizzard": ["Blizzard Entertainment", "Activision Blizzard"], "Riot Games": ["Riot"],
    "Epic Games": ["Epic"], "Cockroach Labs": ["CockroachDB"], "Hudson River Trading": ["HRT"],
    "Ecobee": ["ecobee"], "Lightspeed": ["Lightspeed Commerce"], "Applied Intuition": [],
    "AMD": ["Advanced Micro Devices"], "Wave": ["Wave Financial"], "Maple": ["Maple Health"],
}
MANUAL = {  # sites discovery can't infer
    "AMD": {"ats": "jibe", "slug": "careers.amd.com"},
    "Kinaxis": {"ats": "jibe", "slug": "kinaxis.jibeapply.com"},
}
SUFFIX = re.compile(r"\b(inc|llc|ltd|corp|corporation|co|company|group|holdings|technologies|technology|labs|"
                    r"the|plc|lp|l p|na|n a|us|usa|canada|careers)\b")


def key(name):
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = SUFFIX.sub(" ", s)
    return re.sub(r"\s+", "", s)


def prd_companies():
    text = (ROOT / "docs" / "PRD.md").read_text().split("## Companies", 1)[1]
    out = []
    for line in text.splitlines():
        m = re.match(r"- \*\*[^*]+:\*\* (.+)", line)
        if not m:
            continue
        for raw in m.group(1).split(", "):
            raw = raw.strip()
            aliases = re.findall(r"\(([^)]+)\)", raw)
            name = re.sub(r"\s*\([^)]*\)", "", raw).strip()
            if "/" in name:
                parts = name.split("/")
                name, aliases = parts[0], aliases + parts[1:]
            aliases = list(dict.fromkeys(aliases + ALIASES.get(name, [])))
            out.append({"name": name, "aliases": aliases})
    return out


PATTERNS = [
    ("greenhouse", re.compile(r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_app\?for=)?([\w-]+)", re.I)),
    ("lever", re.compile(r"jobs\.lever\.co/([\w.-]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)", re.I)),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([\w-]+)", re.I)),
    ("workable", re.compile(r"apply\.workable\.com/([\w-]+)", re.I)),
    ("bamboohr", re.compile(r"([\w-]+)\.bamboohr\.com", re.I)),
    ("recruitee", re.compile(r"([\w-]+)\.recruitee\.com", re.I)),
    ("workday", re.compile(r"([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)", re.I)),
    ("jibe", re.compile(r"([\w-]+\.jibeapply\.com)", re.I)),
    ("oracle", re.compile(r"([\w.-]+\.oraclecloud\.com)/hcmUI/CandidateExperience/[\w-]+/sites/([\w-]+)", re.I)),
]


def mine(listings):
    hits = collections.defaultdict(collections.Counter)
    for x in listings:
        for ats, pat in PATTERNS:
            m = pat.search(x.get("url", ""))
            if m:
                slug = "|".join(m.groups()) if ats in ("workday", "oracle") else m.group(1)
                if ats == "workday" and m.group(3).lower() in ("job", "details"):
                    continue
                hits[key(x["company_name"])][(ats, slug)] += 1
                break
    return hits


def works(ats, slug):
    try:
        return len(FETCHERS[ats]("probe", slug)) > 0
    except Exception:
        return False


def probe_guess(c):
    names = [c["name"]] + c["aliases"]
    cands = []
    for n in names:
        base = re.sub(r"[^a-z0-9 ]", "", n.lower().replace("&", "and")).strip()
        for s in (base.replace(" ", ""), base.replace(" ", "-"), base.split(" ")[0]):
            if s and s not in cands:
                cands.append(s)
    for s in cands:
        for ats, url in (("greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs"),
                         ("ashby", f"https://api.ashbyhq.com/posting-api/job-board/{s}"),
                         ("lever", f"https://api.lever.co/v0/postings/{s}?mode=json&limit=1")):
            try:
                r = client.get(url)
                if r.status_code == 200:
                    d = r.json()
                    n = len(d.get("jobs", [])) if isinstance(d, dict) else len(d)
                    if n > 0 or ats != "lever":
                        return ats, s
            except Exception:
                pass
    return None


def resolve(c, hits):
    if c["name"] in MANUAL:
        return MANUAL[c["name"]]
    if c["name"] in CUSTOM:
        return {"ats": "custom", "slug": CUSTOM[c["name"]]}
    counter = collections.Counter()
    for n in [c["name"]] + c["aliases"]:
        counter.update(hits.get(key(n), {}))
    for (ats, slug), _ in counter.most_common(4):
        if works(ats, slug):
            return {"ats": ats, "slug": slug}
    g = probe_guess(c)
    if g:
        return {"ats": g[0], "slug": g[1]}
    return {"ats": "none"}


def main():
    path = ROOT / "companies.yaml"
    existing = {c["name"]: c for c in (yaml.safe_load(path.read_text()) or [])} if path.exists() else {}
    hits = mine(get_json(SIMPLIFY))
    companies = prd_companies()
    todo = [c for c in companies if not existing.get(c["name"], {}).get("manual")]
    with ThreadPoolExecutor(16) as pool:
        resolved = dict(zip([c["name"] for c in todo], pool.map(lambda c: resolve(c, hits), todo)))
    lines = ["# One line per company. ats: greenhouse|lever|ashby|workday|smartrecruiters|workable|bamboohr|recruitee|oracle|custom|none",
             "# Workday slug = tenant|wdN|site, Oracle slug = host|siteNumber. `manual: true` = discover.py won't overwrite.",
             "# ats: none -> still covered via the GitHub lists (matching roles forwarded to #company-roles)."]
    for c in companies:
        e = existing[c["name"]] if c["name"] in existing and existing[c["name"]].get("manual") else {"name": c["name"], **resolved[c["name"]]}
        if c["aliases"]:
            e["aliases"] = c["aliases"]
        lines.append("- " + yaml.safe_dump(e, default_flow_style=True, width=1000, allow_unicode=True).strip())
    path.write_text("\n".join(lines) + "\n")
    n = collections.Counter(resolved[c["name"]]["ats"] for c in todo)
    print(f"{len(companies)} companies: {dict(n)}")
    print("unmapped:", ", ".join(c["name"] for c in todo if resolved[c["name"]]["ats"] == "none"))


if __name__ == "__main__":
    main()
