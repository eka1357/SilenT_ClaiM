# PREFLIGHT.md: what to check before the demo, and what we skip

This adapts the common "before you launch" and "is your app secure" checklists to a hackathon demo that runs on one laptop. Items that do not apply are listed at the end with the reason, so no agent spends time on them.

## The night before

- [ ] **Credits.** Check the balance on the LLM and Sarvam accounts. Set a spending cap or budget alert in each console. Keep a second key ready in a password manager, not in the repo.
- [ ] **Free tiers.** Free Supabase projects can be paused when idle: open the project and run a query the day before. Check the Sarvam and LLM rate limits against the demo (about 15 calls per run). If in doubt, run with `DEMO_OFFLINE=1`.
- [ ] **Keys.** `PAYTM_MODE=pending` until the staging keys arrive on finals day, then `staging`. No production keys on the laptop. The API's startup guard must refuse anything else.
- [ ] **Fixtures.** `scripts/record_fixtures.py` has been run against the live services, and `DEMO_OFFLINE=1 uv run pytest tests/contract` passes with Wi-Fi off.
- [ ] **Cold run (our beta test).** Someone who has not seen the project clones the repo, follows only README.md, and runs the demo. Fix whatever confused them.
- [ ] **Personas (our demo accounts).** The 12 shops are seeded. On finals day, once keys arrive, make Selvi's ₹35 plan-fee payment on Paytm staging and put its order ID in `data/shops.csv`.

## Morning of the event

- [ ] `uv run pytest -m live`: one real call per integration passes.
- [ ] Phone hotspot ready, laptop and phone charged, chargers packed.
- [ ] Browser: a clean profile with only the demo tabs, zoom at 100%, notifications off, autofill off.
- [ ] TTS audio for every prompt generated once and cached, so the demo makes no repeat TTS calls.

## Thirty minutes before judging

- [ ] **Code freeze** (the "no Fridays" rule): no code changes after the freeze, only configuration, and only if something is down.
- [ ] Reset the scenario, then run the full demo once.
- [ ] Backup video of the full demo is on the laptop and on the phone.
- [ ] Kill switches known by heart: `DEMO_OFFLINE=1` (all external calls served from fixtures) and `PAYBACK_ENABLED=0` (refunds blocked, the UI says so).

## What we do, and why

| From the checklists | For this project |
|---|---|
| Beta test | The cold run above |
| Privacy policy | A `/privacy` page and the "What we share" consent disclosure: consent is the product, so this strengthens the pitch |
| Cap API spend, LLM credit balance, billing alerts | Spending caps, budget alerts, TTS caching, rate limits (SECURITY.md) |
| Upgrade from the free tier | Not paying; instead the Supabase pause check and the offline fallback |
| Database restore | "Reset and run the flood" plus `gen_data.py`: the whole state is rebuilt from the seed in seconds |
| Kill switch | `DEMO_OFFLINE` and `PAYBACK_ENABLED` |
| Demo account | Fixed personas and Paytm's staging test credentials |
| Swap test keys | The reverse for us: test (staging) keys only, enforced in code |
| No Fridays | The code freeze |
| HTTPS | Only if we deploy a link for judges: use a host with HTTPS by default. All calls to Paytm, Sarvam, the LLM and Open-Meteo are HTTPS already |
| Least-privilege database key | The API connects with a Postgres role that can only read and write our tables, never the Supabase `service_role` key. The browser never talks to the database |
| No tokens or card numbers in logs | Keys, checksums and raw audio are never logged; logs hold IDs only (SECURITY.md) |
| Input validation | Pydantic on every request; audio uploads limited by type, size and length |
| Rate limiting | On the endpoints that cost money: voice upload, scenario run and consent |

## What we skip, and why

| Item | Why it does not apply |
|---|---|
| Crash reporting (Sentry and similar) | One laptop, one run; errors show in the UI and the API log |
| Delete-account button, test signup, password hashing, session expiry, password-reset links | There are no accounts or logins. The demo uses fixed personas |
| CSRF tokens | The API uses JSON with no cookies, and CORS allows only our own origin, so there is no session for another site to ride on |
| CAPTCHA and honeypot fields | There are no public forms |
| Declaring SDKs, phased release, over-the-air hotfixes, restore purchases | App-store concerns; we ship no mobile app |
| SPF, DKIM, DMARC, support email | We send no email |
| Automated backups | The state is rebuilt from the seed script and git. Copy the fixtures and the backup video to a phone |
| Terms of service | Not needed for a demo of synthetic data |

One item in the source checklist ("Use Agent Add…") was cut off in the screenshot, so it is not covered here.
