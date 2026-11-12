# Silent Claim

**When the Soundbox goes silent, that is the claim.**

A feature concept for Paytm for Business. When a merchant's Paytm payments stop and most of their street goes quiet on a day of heavy rain, an agent asks them one question in Tamil, takes one tap of consent, files an evidence-backed income-protection claim for a human adjuster, and refunds that month's plan fee at once on Paytm's staging gateway.

Built for the Paytm Build for India AI Hackathon, Chennai, Track 2: AI-Powered Financial Journeys.

## What is real and what is simulated

| Real | Simulated (labelled in the UI) |
|---|---|
| Rainfall (Open-Meteo archive), the detection rules, Tamil voice (Sarvam), the reply classifier, the evidence PDF, the Paytm staging payment and refund | The 12 shops' payment history, the insurer's intake, the claim payout, the app shell |

## Run it

Needs Python 3.11 with `uv`, Node 20+ with `pnpm`, and keys in `api/.env` (copy `.env.example`).

```bash
cd api && uv sync
uv run python scripts/gen_data.py
uv run uvicorn app.main:app --port 8000

cd web && pnpm i && pnpm dev
# open http://localhost:5173/console and http://localhost:5173/merchant
```

Offline demo (no network needed): set `DEMO_OFFLINE=1` in `api/.env` and restart. The UI then shows "Replay" labels.

Tests: `cd api && uv run pytest -q` · Eval: `uv run python scripts/eval.py` · E2E: `cd web && pnpm test:e2e`.

## Docs

Start with [AGENTS.md](AGENTS.md). Product, architecture, design, plan, tests, security and the demo script are in [docs/](docs/).

## Data

All merchants and payments are synthetic. No real Paytm data is used. Sources for the figures in the pitch: Mathrubhumi (21 Oct 2026), WRI India (2024), Mint (June 2026), Paytm press release (3 July 2024), Paytm Q2 FY27 results as reported by YourStory.
