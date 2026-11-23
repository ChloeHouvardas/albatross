"""Intern Radar: fetch -> filter -> dedupe -> notify -> save."""
import argparse
import json
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

import notify
from filters import is_summer_2027, matches
from jobs import Job, norm_url
from sources import custom
from sources.ats import FETCHERS
from sources.github_lists import LISTS

ROOT = Path(__file__).parent
SEEN = ROOT / "data" / "seen.json"
HEALTH = ROOT / "data" / "health.json"
ROLES = ROOT / "data" / "roles.json"   # tracker feed for the Google Sheet (scripts/tracker.gs)
PRUNE_DAYS = 180
FLOOD_CAP = 30       # more new matches than this from one source in one run = probably a feed change
PUSH_CAP = 8         # individual phone pushes per run before collapsing into one summary push
FAIL_ALERT_AT = 3    # consecutive failures before #bot-health hears about it


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def norm_name(s):
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("&", "and"))


def build_tasks(companies, only=None):
    """-> list of (key, display_name, callable)."""
    tasks = []
    for name, fn in LISTS.items():
        tasks.append((f"list:{name}", name, fn))
    for c in companies:
        ats, slug, name = c.get("ats"), c.get("slug"), c["name"]
        if ats in FETCHERS and slug:
            tasks.append((f"{ats}:{slug}", name, lambda f=FETCHERS[ats], n=name, s=slug: f(n, s)))
        elif ats == "custom" and slug in custom.READERS:
            tasks.append((f"custom:{slug}", name, lambda f=custom.READERS[slug], n=name: f(n)))
    if only:
        tasks = [t for t in tasks if only.lower() in t[0].lower() or only.lower() in t[1].lower()]
    return tasks


def run_all(tasks):
    results, errors = {}, {}

    def one(t):
        key, _, fn = t
        start = time.time()
        try:
            return key, fn(), None, time.time() - start
        except Exception as e:  # one broken source must never stop the run
            return key, None, f"{type(e).__name__}: {str(e)[:200]}", time.time() - start

    with ThreadPoolExecutor(max_workers=24) as pool:
        for key, jobs, err, secs in pool.map(one, tasks):
            if err:
                errors[key] = err
            else:
                results[key] = jobs
    return results, errors


def fmt_company(job: Job, label: str) -> str:
    loc = job.location_text or "location n/a"
    return f"{label} **{job.company}** — [{job.title}](<{job.url}>) · {loc}"


def fmt_repo(job: Job) -> str:
    loc = job.location_text or "n/a"
    return f"**{job.company}** — [{job.title}](<{job.url}>) · {loc}"


def flood(companies, tasks, results):
    """Dump everything open right now to #dump: company matches first, then all GitHub-list listings."""
    direct = {norm_name(n) for k, n, _ in tasks if not k.startswith("list:")}
    indirect = {norm_name(a) for c in companies if norm_name(c["name"]) not in direct for a in [c["name"], *c.get("aliases", [])]}
    company, listings, seen_urls, seen_keys = [], [], set(), set()
    for key, jobs in results.items():
        for j in jobs:
            if key.startswith("list:"):
                k = (norm_url(j.url), norm_name(j.company) + "|" + norm_name(j.title))
                if k[0] not in seen_keys and k[1] not in seen_keys:
                    seen_keys.update(k)
                    listings.append(j)
                if norm_name(j.company) not in indirect or j.source == "negar":
                    continue
            label = matches(j)
            if label and norm_url(j.url) not in seen_urls:
                seen_urls.add(norm_url(j.url))
                company.append((j, label))
    company.sort(key=lambda x: (not x[1].startswith("🔥"), not x[1].startswith("🍁"), x[0].company.lower()))
    listings.sort(key=lambda j: -(j.posted or 0))
    lines = [f"# 🏢 Company roles open right now ({len(company)})"] + [fmt_company(j, l) for j, l in company]
    lines += [f"# 📋 GitHub-list listings, newest first ({len(listings)})"] + [fmt_repo(j) for j in listings]
    print(f"flood: {len(company)} company roles, {len(listings)} list listings")
    notify.discord("dump", lines)
    notify.push("Intern Radar flood-fill done", f"{len(company)} company roles + {len(listings)} listings posted to #dump", priority=3)


def update_tracker(results, now, companies):
    """Every open matching role from any source, merged by company+title, with first-seen / open-closed status."""
    roles = load(ROLES, {})
    listed = {norm_name(a) for c in companies for a in [c["name"], *c.get("aliases", [])]}
    current = {}
    for key, jobs in results.items():
        for j in jobs:
            label = matches(j)
            if not label:
                continue
            rid = norm_name(j.company) + "|" + norm_name(j.title)
            r = current.setdefault(rid, {"company": j.company, "title": j.title, "url": j.url, "label": label,
                                         "locations": [], "posted": j.posted, "srcs": []})
            if not key.startswith("list:") and r["srcs"] and all(s.startswith("list:") for s in r["srcs"]):
                r["url"], r["company"] = j.url, j.company  # prefer the company's own posting link
            r["srcs"] = sorted(set(r["srcs"]) | {key})
            for loc in j.locations:
                if loc and loc not in r["locations"]:
                    r["locations"].append(loc)
            if label.startswith("🔥") or (label.startswith("🍁") and not r["label"].startswith("🔥")):
                r["label"] = label
            if j.posted and (not r["posted"] or j.posted < r["posted"]):
                r["posted"] = j.posted
    for rid, r in current.items():
        old = roles.get(rid, {})
        locs = r.pop("locations")
        roles[rid] = {**r, "location": " / ".join(locs)[:200], "listed": norm_name(r["company"]) in listed,
                      "first_seen": old.get("first_seen", now), "last_seen": now, "status": "open"}
    ok = set(results)
    for rid, r in roles.items():
        # only close a role if its sources were fetched fine this run (a broken feed != a closed role)
        if rid not in current and r["status"] == "open" and set(r.get("srcs", [])) <= ok:
            r["status"], r["closed"] = "closed", now
    cutoff = now - 45 * 86400
    roles = {k: v for k, v in roles.items() if v["status"] == "open" or v.get("closed", now) >= cutoff}
    ROLES.write_text(json.dumps(roles, indent=0, sort_keys=True, ensure_ascii=False))
    print(f"tracker: {sum(r['status'] == 'open' for r in roles.values())} open, {len(roles)} total")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print alerts, don't post or save")
    ap.add_argument("--no-seed", action="store_true", help="treat everything as new (implies --dry-run)")
    ap.add_argument("--only", help="only run sources whose key/name contains this")
    ap.add_argument("--test-alert", action="store_true", help="send one test message to every channel + phone")
    ap.add_argument("--flood", action="store_true", help="post EVERY currently open match + list listing to #dump; doesn't touch seen.json")
    args = ap.parse_args()
    if args.no_seed:
        args.dry_run = True
    notify.DRY_RUN = args.dry_run

    if args.test_alert:
        for ch in ("company", "repo", "health"):
            notify.discord(ch, [f"✅ Intern Radar test message for this channel ({ch})"])
        notify.push("Intern Radar test", "If you see this, phone pushes work ✅")
        return

    companies = yaml.safe_load((ROOT / "companies.yaml").read_text()) or []
    seen = load(SEEN, {"seeded": [], "company": {}, "repo": {}})
    health = load(HEALTH, {"fails": {}, "last_summary": ""})
    seeded = set() if args.no_seed else set(seen["seeded"])
    now = int(time.time())

    tasks = build_tasks(companies, args.only)
    names = {k: n for k, n, _ in tasks}
    t0 = time.time()
    results, errors = run_all(tasks)
    print(f"fetched {len(results)}/{len(tasks)} sources in {time.time() - t0:.0f}s, {len(errors)} errors")
    if args.flood:
        return flood(companies, tasks, results)

    # Companies with no direct reader still get #company-roles alerts via the GitHub lists.
    direct = {norm_name(n) for k, n, _ in tasks if not k.startswith("list:")}
    indirect = {norm_name(c["name"]): c["name"] for c in companies if norm_name(c["name"]) not in direct}
    for c in companies:
        for alias in c.get("aliases", []):
            if norm_name(c["name"]) in indirect:
                indirect[norm_name(alias)] = c["name"]

    company_new, repo_new = [], []
    live = set()  # every id seen this run; live ids are never pruned

    for key, jobs in results.items():
        is_list = key.startswith("list:")
        first = key not in seeded and not args.no_seed
        src_new = []

        if is_list:
            for j in jobs:
                # vansh uses short links, so also dedupe on company+title across lists
                keys = (norm_url(j.url), "t:" + norm_name(j.company) + "|" + norm_name(j.title))
                live.update(keys)
                if any(k in seen["repo"] for k in keys):
                    continue
                for k in keys:
                    seen["repo"][k] = now
                if not first:
                    repo_new.append(j)
            # fallback: listed roles at target companies that have no direct reader
            cand = []
            for j in jobs:
                if norm_name(j.company) in indirect and j.source != "negar":
                    label = matches(j)
                    if label:
                        cand.append((j, label))
            jobs_for_company = cand
        else:
            jobs_for_company = [(j, l) for j in jobs if (l := matches(j))]

        for j, label in jobs_for_company:
            k = norm_url(j.url) if is_list else j.id
            live.add(k)
            if k in seen["company"]:
                continue
            seen["company"][k] = now
            if not first:
                src_new.append((j, label))

        if len(src_new) > FLOOD_CAP:
            notify.discord("health", [f"⚠️ `{key}` returned {len(src_new)} 'new' matching roles at once — "
                                      f"looks like a feed change, suppressed. Check {names.get(key, key)} manually."])
        else:
            company_new.extend(src_new)
        seeded.add(key)
        if first and not args.no_seed:
            print(f"seeded {key}: {len(jobs)} jobs ({len(jobs_for_company)} matching)")

    # alerts
    company_new.sort(key=lambda x: (not x[1].startswith("🔥"), x[0].company))
    notify.discord("company", [fmt_company(j, l) for j, l in company_new])
    notify.discord("repo", [fmt_repo(j) for j in repo_new])
    for j, l in company_new[:PUSH_CAP]:
        notify.push(f"{j.company} · {l}", f"{j.title}\n{j.location_text}", j.url)
    if len(company_new) > PUSH_CAP:
        notify.push(f"+{len(company_new) - PUSH_CAP} more intern roles", "See #company-roles on Discord")
    print(f"new: {len(company_new)} company-roles, {len(repo_new)} repo-feed")

    for key, err in sorted(errors.items()):
        print(f"ERROR {key}: {err}")
    if args.dry_run:
        return

    # health
    fails = health["fails"]
    broken = []
    for key in results:
        fails.pop(key, None)
    for key, err in errors.items():
        fails[key] = fails.get(key, 0) + 1
        if fails[key] == FAIL_ALERT_AT or (fails[key] > FAIL_ALERT_AT and fails[key] % 12 == 0):
            broken.append(f"🔴 `{key}` ({names.get(key, '')}) failed {fails[key]} runs in a row: {err}")
    notify.discord("health", broken)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if datetime.now(timezone.utc).hour >= 13 and health.get("last_summary") != today:
        day_ago = now - 86400
        n_company = sum(1 for t in seen["company"].values() if t >= day_ago)
        n_repo = sum(1 for t in seen["repo"].values() if t >= day_ago)
        failing = sorted(k for k, n in fails.items() if n >= FAIL_ALERT_AT)
        notify.discord("health", [
            f"📊 **Daily summary** — {len(results)}/{len(tasks)} sources OK. "
            f"Roles first seen in last 24h: {n_company} company / {n_repo} repo-feed (incl. seeding).",
            f"Failing: {', '.join(f'`{k}`' for k in failing) if failing else 'none'}",
        ])
        health["last_summary"] = today

    update_tracker(results, now, companies)

    # save (prune old ids so the file doesn't grow forever)
    cutoff = now - PRUNE_DAYS * 86400
    for ch in ("company", "repo"):
        seen[ch] = {k: t for k, t in seen[ch].items() if t >= cutoff or k in live}
    seen["seeded"] = sorted(seeded)
    SEEN.parent.mkdir(exist_ok=True)
    SEEN.write_text(json.dumps(seen, indent=0, sort_keys=True))
    HEALTH.write_text(json.dumps(health, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
