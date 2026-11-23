# PRD: Intern Radar

**Goal:** Never miss a Summer 2027 SWE internship. Every new matching role lands in Discord within ~2 hours of being posted.

## Goals
1. **Catch roles early.** Check ~250 target companies' career pages directly, every 2 hours.
2. **Miss nothing.** Also pull every Summer 2027 listing from the big GitHub internship lists.
3. **Notify on everything.** Every matching role from any listed company gets a phone push and a Discord post. No company is ranked above another.
4. **No noise.** Each role alerts once, and the first run doesn't flood me with existing roles.
5. **Free and low-maintenance.** Runs on GitHub Actions; adding a company is one line in a config file.

## What it watches
- **Company career pages:** the companies in `companies.yaml`, read through their job systems' public feeds: Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, BambooHR and Recruitee.
- **Custom career sites:** companies that run their own careers site get a small dedicated reader each: big tech (Google, Amazon, Meta, Apple, Microsoft), quant firms (Jane Street, Citadel, Two Sigma, D. E. Shaw, Hudson River Trading and others) and banks (Goldman Sachs, JPMorgan, Morgan Stanley, Bloomberg, Scotiabank and others).
- **GitHub lists:** [SimplifyJobs/Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships) and [vanshb03/Summer2027-Internships](https://github.com/vanshb03/Summer2027-Internships) (both `.github/scripts/listings.json`, same format), and [negarprh/Canadian-Tech-Internships-2027](https://github.com/negarprh/Canadian-Tech-Internships-2027) (README table).

## What counts as a match (company pages)
- **Role:** any Summer 2027 software/tech intern role: SWE, backend, frontend, full-stack, mobile (iOS/Android), infrastructure/platform, DevOps/SRE, security, quant (developer/researcher/trader) and "technology" intern programs. No PhD/MBA roles, no other terms, no non-tech roles (mechanical, marketing, sales, HR and similar).
- **Location:** anywhere in Canada (Toronto, Vancouver and Montreal labelled 🔥), NYC, Bay Area/California, Seattle or Boston. Anything else is dropped.
- GitHub list roles skip these filters (see `#repo-feed`).

## Where alerts go
| Channel | What |
|---|---|
| Phone push (ntfy) + `#company-roles` | Every match from company career pages, any company. Location shown as a label (🔥 TOR/VAN/MTL, 🍁 Canada, 🇺🇸 US) |
| `#repo-feed` | Every new Summer 2027 listing from the GitHub lists, unfiltered |
| `#bot-health` | A source keeps failing; daily summary |

## Done when
- A new role at any listed company triggers a phone push and a Discord post within one 2-hour cycle.
- No role alerts twice in the same channel.
- I can add a company by adding its name to `companies.yaml`.
- I get told when a source breaks.

## Not building
Auto-apply, a web dashboard, application tracking, or scraping LinkedIn, hiring.cafe, intern-list, SWEList or simplify.jobs. Those email alerts stay as separate sign-ups.

## Build order
1. GitHub lists + Greenhouse/Lever/Ashby + Discord + phone push
2. Workday, SmartRecruiters, Workable, BambooHR, Recruitee, health alerts
3. Custom readers: Amazon, Google, then the top quant firms and banks
4. Custom readers: Meta, Apple, Microsoft, remaining quant firms and banks

## Tech
Python, GitHub Actions every 2 hours (private repo is fine), seen roles stored in a JSON file in the repo, Discord webhooks and the ntfy topic stored as repo secrets.

## Companies (all treated equally)
- **Big tech:** Google, Amazon, Microsoft, Meta, Apple, Netflix, NVIDIA, LinkedIn, Salesforce, Adobe, Oracle, IBM, Intel, AMD, Qualcomm, Cisco, Uber, Airbnb, Tesla, SpaceX, Waymo, Intuit, ServiceNow, Workday, Broadcom, Snap, Spotify, Atlassian
- **AI:** OpenAI, Anthropic, Cohere, Scale AI, Databricks, Perplexity, xAI, Hugging Face, Glean, Harvey, Anysphere (Cursor), Character.AI, Runway, Cerebras, Groq, Together AI, Pinecone, Waabi, Ada
- **Quant:** Jane Street, Citadel, Citadel Securities, Hudson River Trading, Two Sigma, D. E. Shaw, Jump Trading, Optiver, IMC, Susquehanna (SIG), Tower Research, Five Rings, DRW, Akuna, Virtu, Point72/Cubist, Millennium, Bridgewater, AQR
- **Canada tech:** Shopify, 1Password, Clio, Lightspeed, Coveo, D2L, OpenText, Kinaxis, Ciena, BlackBerry, Arctic Wolf, Benevity, Thinkific, PointClickCare, Ecobee, Hootsuite, Wattpad, Autodesk, SAP, Unity
- **Startups:** Cognition, Replit, Modal, Baseten, Fireworks AI, Decagon, Sierra, Hebbia, Mercor, ElevenLabs, Suno, Luma AI, Vanta, Drata, Deel, Clay, PostHog, Warp, Zed, Railway, Render, Neon, Convex, Resend, Clerk, Mintlify, Browserbase, Watershed, Rogo, Abridge
- **Canadian startups:** Tenstorrent, Xanadu, Untether AI, Sanctuary AI, Float, Wave, Hopper, Jane App, Klue, Clutch, Borrowell, Maple
- **Infra & dev tools:** Snowflake, Stripe, Cloudflare, Datadog, MongoDB, Confluent, HashiCorp, GitLab, Vercel, Supabase, Sentry, Cockroach Labs, Elastic, Twilio, Okta, CrowdStrike, Palo Alto Networks, Zscaler, Fastly, DigitalOcean, Grafana Labs, Temporal, Retool, Postman, Docker, Tailscale, Linear, Figma, Notion, Airtable, Asana, Dropbox, Canva, Miro
- **Fintech:** Plaid, Ramp, Brex, Mercury, Coinbase, Robinhood, Chime, Affirm, SoFi, Block, PayPal, Visa, Mastercard, Kraken, Circle, Marqeta, Toast, Wealthsimple, Neo Financial, KOHO, Questrade
- **Banks & finance:** Bloomberg, Goldman Sachs, Morgan Stanley, JPMorgan Chase, Capital One, American Express, RBC, TD, BMO, Scotiabank, CIBC, National Bank, Desjardins, Manulife, Sun Life, CPP Investments
- **Consumer:** Pinterest, Lyft, DoorDash, Instacart, Reddit, Discord, Roblox, Duolingo, Twitch, Etsy, eBay, Wayfair, Zillow, Expedia, Faire, Whatnot
- **Enterprise:** Palantir, Rippling, Gusto, HubSpot, Zoom, Samsara, Verkada, Flexport, Anduril
- **Games:** EA, Ubisoft, Riot Games, Epic Games, Blizzard
- **Health & fitness:** Strava, Whoop, Oura, Peloton, Garmin, AllTrails, Zwift, Headspace, Calm, Noom
- **Robotics & hardware:** Zoox, Aurora, Skydio, Applied Intuition, Physical Intelligence, Figure AI, Skild AI, Shield AI, Saronic, Hadrian

Companies with no readable feed (yet) are fine: their roles still arrive through the GitHub lists.
