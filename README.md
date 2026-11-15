# Silent Claim

**When the Soundbox goes silent, that is the claim.**

**Demo video:** https://www.youtube.com/watch?v=f-Xr62rBfBw

A feature concept for Paytm for Business. When a merchant's Paytm payments stop and most of their street goes quiet on a day of heavy rain, an agent asks them one question in Tamil, takes one tap of consent, and files an evidence-backed income-protection claim for a human adjuster. Paytm also refunds that month's ₹35 plan fee the same day, as goodwill; the real money is the insurer's claim payout for the lost day.

Built for the Paytm Build for India AI Hackathon, Chennai, Track 2: AI-Powered Financial Journeys.

## What is real and what is simulated

| Real | Simulated (labelled in the UI) |
|---|---|
| Rainfall (Open-Meteo archive), the detection rules, Tamil voice (Sarvam), the reply classifier, the evidence PDF, Selvi's consent tap | The 12 shops' payment history, the other six consents, Meena's and Kavya's voice replies, the ₹35 plan-fee refunds, the insurer's intake, the claim payout, the app shell |

The refund client is built and checksum-signed for Paytm's staging gateway, and all four endpoints answered our probe. On finals day our staging test account returned error 239, so the refunds ran simulated, and they are labelled that way.

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

## Phone demo (same Wi-Fi or hotspot)

To open Selvi's `/merchant` screen on your phone while running `/console` and `/adjuster` on your laptop:

1. Connect your laptop and phone to the same Wi-Fi network (or your phone's hotspot).
2. Start the API on the laptop:
   ```bash
   cd api && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
3. Start the Vite dev server with `--host` enabled (default in `pnpm dev`):
   ```bash
   cd web && pnpm dev
   ```
4. Note the `Network: http://<LAN-IP>:5173/` URL printed by Vite (or add `http://<LAN-IP>:5173` to `WEB_ORIGIN` in `api/.env`; private LAN origins are also allowed automatically when `DEMO_MODE=1`).
5. On your phone browser, open `http://<LAN-IP>:5173/merchant`. All `/api/*` and SSE requests are proxied through Vite to the laptop's FastAPI server.

Tests: `cd api && uv run pytest -q` · Eval: `uv run python scripts/eval.py` · E2E: `cd web && pnpm test:e2e`.

## Docs

Start with [AGENTS.md](AGENTS.md). Product, architecture, design, plan, tests, security and the demo script are in [docs/](docs/).

## Data

All merchants and payments are synthetic. No real Paytm data is used. Sources for the figures in the pitch: Mathrubhumi (21 Oct 2026), WRI India (2024), Mint (June 2026), Paytm press release (3 July 2024), Paytm Q2 FY27 results as reported by YourStory.
