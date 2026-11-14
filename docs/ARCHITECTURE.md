# ARCHITECTURE.md

## Shape of the system

```
 web (Vite + React)                         api (FastAPI)
 ┌───────────────────────┐   REST + SSE   ┌─────────────────────────────────────────┐
 │ /console  (ops view)  │ ─────────────▶ │ routes/  ── scenario runner (clock)      │
 │ /merchant (phone view)│ ◀───────────── │   │                                      │
 │ /adjuster (batch)     │   /api/stream  │   ▼                                      │
 └───────────────────────┘                │ detector/ (pure rules, tested)           │
                                          │   │                                      │
                                          │   ▼                                      │
                                          │ agents/graph.py (LangGraph)              │
                                          │  sense → confirm → ask → file → payback  │
                                          │   │        │        │      │       │     │
                                          │   ▼        ▼        ▼      ▼       ▼     │
                                          │ db   weather.py  sarvam  pdf   paytm.py  │
                                          └─────────────────────────────────────────┘
                                               │            │                 │
                                     Supabase Postgres  Open-Meteo, Sarvam,  Paytm PG
                                     (SQLite offline)   LLM API             STAGING only
```

One process for the API, one for the web app. No queues, no workers. The scenario runner drives everything from a simulated clock, which makes the demo repeatable.

## Repo layout

```
silent-claim/
├─ AGENTS.md  README.md  .env.example  .gitignore
├─ .agents/rules/          # Antigravity rules that load by path (frontend, backend, money)
├─ docs/                   # this folder
├─ api/
│  ├─ pyproject.toml
│  ├─ app/
│  │  ├─ main.py           # FastAPI app, CORS, routers, startup guards
│  │  ├─ config.py         # pydantic-settings; reads .env
│  │  ├─ db.py  models.py  # SQLAlchemy 2 models (below)
│  │  ├─ events.py         # in-process event bus → SSE
│  │  ├─ scenario.py       # simulated clock: replays street.csv hour by hour
│  │  ├─ detector/
│  │  │  ├─ config.py      # thresholds + RULES_VERSION
│  │  │  ├─ baseline.py    # trading-day median
│  │  │  └─ rules.py       # decide(), eligibility, quorum, payout cap (pure)
│  │  ├─ agents/
│  │  │  ├─ state.py       # ClaimState (Pydantic)
│  │  │  ├─ graph.py       # LangGraph wiring
│  │  │  └─ nodes.py       # one function per node
│  │  ├─ integrations/
│  │  │  ├─ paytm.py       # staging client + checksum, idempotent refunds
│  │  │  ├─ sarvam.py      # TTS + STT (Tamil)
│  │  │  ├─ llm.py         # cause classifier + evidence summary (JSON only)
│  │  │  ├─ weather.py     # Open-Meteo archive
│  │  │  └─ replay.py      # serves recorded fixtures when DEMO_OFFLINE=1
│  │  ├─ evidence/pdf.py   # reportlab evidence pack
│  │  └─ routes/           # scenario.py, shops.py, claims.py, adjuster.py, stream.py
│  ├─ scripts/  gen_data.py  eval.py  record_fixtures.py  spikes/
│  ├─ data/                # generated; small, committed for demo determinism
│  └─ tests/  unit/  contract/  fixtures/
└─ web/
   ├─ src/
   │  ├─ app/routes/       # Console.tsx, Lab.tsx, Merchant.tsx, Adjuster.tsx, Privacy.tsx, DevKit.tsx
   │  ├─ components/       # Shopfront, Shutter, RoadBand, CaseFile, Receipt, PhoneFrame, ConsentButton, ...
   │  ├─ components/glyphs/ # our ~12 SVG glyphs (no icon library)
   │  ├─ components/ui/    # shadcn primitives (generated, then restyled)
   │  ├─ lib/api.ts  lib/stream.ts  lib/format.ts
   │  └─ styles/tokens.css # design tokens (DESIGN_SYSTEM.md)
   ├─ scripts/design-lint.mjs # fails on anti-patterns (DESIGN_SYSTEM.md)
   └─ e2e/demo.spec.ts     # Playwright demo path
```

## Data model (SQLAlchemy 2)

| Table | Key columns |
|---|---|
| `shops` | `id`, `name`, `owner`, `category`, `street_id`, `lat`, `lon`, `plan_active`, `staging_order_id` (the ₹35 plan-fee payment made on Paytm staging) |
| `streets` | `id`, `name`, `lat`, `lon` |
| `payments_hourly` | `shop_id`, `ts_hour` (IST), `n_payments`, `amount_paise` |
| `detections` | `id`, `shop_id`, `day`, `baseline_paise`, `day_income_paise`, `dropped`, `eligible`, `quorum_share`, `rain_mm`, `rain_source`, `decision`, `reason`, `rules_version` |
| `asks` | `id`, `detection_id`, `prompt_text_ta`, `prompt_audio_path`, `reply_type` (`tap` or `voice`), `transcript`, `cause_label`, `confidence`, `answered_at` |
| `claims` | `id`, `shop_id`, `detection_id`, `status` (`filed`, `approved`, `rejected`, `paid_sim`), `consent_at`, `evidence_pdf_path`, `batch_id` |
| `batches` | `id`, `status`, `approved_by`, `approved_at` |
| `refunds` | `id`, `claim_id`, `paytm_order_id`, `refund_id` (unique: idempotency), `amount_paise` (always 3500), `status`, `raw_response` (JSON with secrets redacted) |
| `audit_log` | `id`, `ts`, `actor` (`agent`, `merchant`, `adjuster`, `system`), `action`, `payload` |

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/scenario/reset` | Reload seed data, clear detections, claims and refunds (refunds sent to Paytm staging are archived to `api/runs/live_refunds.jsonl`) |
| `POST` | `/api/scenario/run` | Body `{ "day": "2026-10-21", "speed": 60 }`. Replays the day; 1 simulated hour = 1 second at speed 60 |
| `GET` | `/api/street/{id}` | Shops with current status, today's hourly series and baseline |
| `GET` | `/api/claims` | Claims with status and evidence links |
| `POST` | `/api/asks/{id}/consent` | The merchant's "Yes, file it" tap |
| `POST` | `/api/asks/{id}/voice` | Multipart audio upload → STT → classifier |
| `GET` | `/api/asks/{id}/audio` | Tamil prompt audio (wav) |
| `POST` | `/api/batches/{id}/approve` | The adjuster approves the batch, which triggers pay back |
| `GET` | `/api/evidence/{claim_id}.pdf` | Evidence pack |
| `GET` | `/api/metrics` | Forms 0, taps, time to file, eval rates, live/replay flags |
| `POST` | `/api/lab/decide` | Stateless what-if evaluation calling `detector/rules.py` `decide()` on synthetic 12-shop street histories (never writes asks, claims, or refunds) |
| `GET` | `/api/stream` | SSE |
| `GET` | `/api/health` | Which integrations are live, replay or failing |

## SSE events (`event:` name, `data:` JSON)

`clock.tick {ts}` · `shop.status {shop_id, status: trading|quiet|dropped}` · `detector.decision {shop_id, decision, reason, quorum_share, rain_mm}` · `agent.step {claim_id?, node, status: start|ok|error, detail, live: bool}` · `ask.sent {ask_id, shop_id}` · `ask.answered {ask_id, reply_type, cause_label?}` · `claim.filed {claim_id}` · `batch.ready {batch_id, n}` · `batch.approved {batch_id}` · `refund.status {claim_id, status, refund_id}` · `integration.health {name, mode: live|replay|down}`

The client reconnects automatically. Every event has an `id` so a reconnect can resume.

## Agent graph (LangGraph)

State: `ClaimState { shop_id, day, detection, ask, claim, refund, errors[], live_flags{} }`.

| Node | Does | Calls | Can fail to |
|---|---|---|---|
| `sense` | Baseline + drop for the shop and day | `detector` (pure) | n/a |
| `confirm` | Quorum + rain gate + eligibility → `decide()` | `weather.py` | replay cache, then `ask` with reason `rain_unavailable` |
| `ask` | Builds the Tamil prompt, TTS, emits `ask.sent`, waits for an answer (interrupt) | `sarvam.py` | text-only prompt, still answerable |
| `classify` | Voice note → STT → `llm.classify()` → enum label | `sarvam.py`, `llm.py` | label `other` → human review |
| `file` | Creates the claim, builds the evidence PDF (+ an LLM summary, which is cosmetic) | `pdf.py`, `llm.py` | PDF without the summary |
| `payback` | After batch approval only, and only if `PAYBACK_ENABLED=1`: idempotent ₹35 staging refund, then polls status | `paytm.py` | marks `refund_failed`, shows it honestly, never retries with a new refund ID |

Routing: `decide()` returns `file` → `ask(consent)` → `file`. Returns `ask` → `ask(voice)` → `classify` → `flood_closure` goes to `file`, and anything else goes to `close` or `human_review`. The LLM output never sets an amount or skips a rule; it only picks a route from a closed enum.

Use LangGraph `interrupt()` for the merchant's answer, with a checkpointer (in-memory is fine for the demo) so `/consent` resumes the thread.

## Integrations (read these docs, do not guess)

- **Paytm Payment Gateway, staging:** https://www.paytmpayments.com/docs/getting-started and test details at https://www.paytmpayments.com/docs/test-instruments/testing-integration. Two documented staging hosts only (`securestage.paytmpayments.com` for `initiateTransaction` and `securegw-stage.paytmpayments.in` for `v3/order/status`, `refund/apply`, and `v2/refund/status`, with automatic single retry onto the other staging host on DNS/connection/404 failure). Use the official checksum library (`paytmchecksum` + `pycryptodome`). Needed calls: initiate transaction (or payment link) for the ₹35 plan fee during setup, transaction status, refund, refund status. Refund ID = `SC-{claim_id}`, so a retry can never double-refund. Test UPI `7777777777@paytm`. Hosted MCP access needs an email to devsupport@paytmpayments.com; wrap the REST calls yourself instead, and expose them to the agent as tools. Staging keys arrive only on finals day, so the client has two modes: `PAYTM_MODE=pending` builds and signs every request but never sends it, and returns a response marked simulated; `PAYTM_MODE=staging` sends it.
- **Sarvam AI:** https://docs.sarvam.ai: text-to-speech and speech-to-text for `ta-IN`. Check current model names and limits in the docs.
- **LLM:** a thin wrapper in `llm.py`, with provider and model set by `LLM_PROVIDER` and `LLM_MODEL` in `.env`. JSON output validated against a Pydantic schema; one retry, then label `other`.
- **Open-Meteo archive:** https://open-meteo.com/en/docs/historical-weather-api, `daily=precipitation_sum`, `timezone=Asia/Kolkata`, lat 13.04, lon 80.25.

## Demo mode and resilience

- `DEMO_OFFLINE=1`: every integration reads from `tests/fixtures/*.json` and `*.wav` made by `scripts/record_fixtures.py`. The UI label reads "Replay".
- **Auto fallback:** if a live call takes more than 4 s or fails, use the fixture, set the label to "Replay" and log it. The demo never stalls.
- **Paytm refund:** never shown as real unless it is. In `PAYTM_MODE=pending` the label reads "Simulated: Paytm keys pending" and can never read "Live". If staging is down on the day, the UI shows "Paytm staging unavailable" and the recorded run from rehearsal, labelled with its time.
- **One button:** "Reset and run the flood" on `/console` resets state and replays 21 Oct at speed 60.
- **Kill switches:** `PAYBACK_ENABLED=0` blocks refunds (the UI says "Refunds paused"); `DEMO_OFFLINE=1` serves everything from fixtures. Both are read at startup and shown in `/api/health`.
- **Cost:** TTS audio is cached on disk by a hash of its text, and the money-costing endpoints are rate-limited (SECURITY.md).

## Non-functional targets

Console first paint under 1.5 s on the demo laptop. SSE event to on-screen change under 200 ms. Full flood run (reset to all claims filed, without waiting for the human tap) under 25 s. Zero console errors during the demo path.
