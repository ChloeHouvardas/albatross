# Intern Radar

Personal project. Spec: `docs/PRD.md`. Goal over structure: catch every Summer 2027 SWE intern role fast.

## How it works
GitHub Actions (`.github/workflows/radar.yml`) runs `main.py` hourly via a self-dispatching loop (`-f chain=true`; GitHub cron never fired here, kept as backup): fetch all sources concurrently → filter → dedupe against `data/seen.json` → Discord + ntfy → commit `data/` back.
- `sources/ats.py` — greenhouse, lever, ashby, workday, smartrecruiters, workable, bamboohr, recruitee, oracle, jibe. `fn(company, slug) -> list[Job]`.
- `sources/custom.py` — amazon, google, apple, ibm, deshaw (citadel readers exist but Citadel 403s GitHub Actions IPs → lists). Microsoft/Qualcomm/PayPal use `eightfold_pcsx` in ats.py. Meta/Tesla/Shopify/SAP/Coveo etc. are JS-only with private APIs → covered via GitHub lists.
- `sources/github_lists.py` — Simplify, vanshb03, negarprh → `#repo-feed` (unfiltered). Matching list roles for companies with **no direct reader** are also forwarded to `#company-roles`.
- `filters.py` — role/term/location rules. Tune here when noise or misses show up; add a test case in `tests/test_filters.py`.
- `#albatross-toronto` (secret `ALBATROSS_TORONTO` → env `DISCORD_TORONTO`) — matching roles in Toronto/Vancouver/Montreal metros from **every** source plus Canada-only extras (`companies_canada.yaml`, `CA_LISTS` in `github_lists.py`; task keys prefixed `ca:`). Own dedupe (`seen.json["toronto"]`); `ca:` sources never reach other channels, flood or tracker. First run posts the open backlog. Off until the secret exists.
- `companies.yaml` — built by `scripts/discover.py` (mines ATS slugs from Simplify URLs + probes APIs). Mark hand-edited entries `manual: true`.
- `companies_more.yaml` — 340+ extra employers mined from the lists (matching Summer 2027 role in a target city + readable board). Same treatment as companies.yaml; discover.py doesn't touch it.

## Rules
- A source's first successful run seeds silently (key in `seen.json["seeded"]`) — no alert floods.
- One source failing never stops the run; 3 consecutive failures → `#bot-health`.
- >30 "new" matches from one source in one run is suppressed as a probable feed change.
- Never commit `.env` (holds real webhooks). Secrets live in repo secrets.

## Commands
- `.venv/bin/pytest -q`
- `.venv/bin/python main.py --no-seed [--only stripe]` — print everything that matches now (no posting, no saving)
- `.venv/bin/python main.py --dry-run` — print what's new vs seen.json
- `.venv/bin/python scripts/discover.py` — rebuild companies.yaml
- `gh workflow run radar -f test_alert=true` — test message to every channel + phone
