# AGENTS.md: Silent Claim

Read this first, every session. It is loaded on every turn, so it stays short. The detail lives in `docs/`.

## What we are building

Silent Claim is a feature for Paytm for Business. When a merchant's Paytm payments stop and most of their street goes quiet at the same time, an agent asks the merchant one question in Tamil, takes one tap of consent, files an evidence-backed income-protection claim for a human adjuster to approve, and refunds that month's plan fee straight away.

Hero line: "When the Soundbox goes silent, that is the claim."

This is a hackathon build: Paytm Build for India AI Hackathon, Chennai, Track 2 (AI-Powered Financial Journeys). Code written before the event is allowed (confirmed 13 Nov), so we build before the finale on 15 Nov and use the day itself for Paytm keys, polish and rehearsal. A demo that never breaks beats a big one that might.

## Read before you code

| Need | File |
|---|---|
| What and why, scope, user stories, acceptance criteria | `docs/PRODUCT.md` |
| System design, data model, APIs, agent graph | `docs/ARCHITECTURE.md` |
| Rules, thresholds, simulated data | `docs/DATA_SPEC.md` |
| Colours, type, components, motion | `docs/DESIGN_SYSTEM.md` |
| Order of work and the finals-day clock | `docs/IMPLEMENTATION_PLAN.md` |
| Tests and the evaluation | `docs/TESTING.md` |
| Secrets, money safety, privacy | `docs/SECURITY.md` |
| The 90-second demo and judge questions | `docs/DEMO_SCRIPT.md` |
| Checks before the demo, and what we skip | `docs/PREFLIGHT.md` |
| Why we chose what we chose | `docs/DECISIONS.md` |

If a doc and the code disagree, stop and ask the human. Do not guess.

## Non-negotiables

1. **No LLM moves money.** Payout amounts, eligibility and caps come only from `api/app/detector/rules.py`, which is pure, deterministic and tested. LLM output is parsed into a closed enum and validated with Pydantic.
2. **Paytm staging only.** `PAYTM_MODE` is `pending` (keys not here yet: requests are signed but never sent, and every Paytm result is labelled "Simulated: keys pending") or `staging`. The app refuses to start with any other value or a non-staging host. Never use production keys.
3. **Never invent an API.** For Paytm, Sarvam, Open-Meteo or the LLM, read the official docs linked in `docs/ARCHITECTURE.md`. If something is unclear, stop and report it.
4. **Label everything simulated.** Any simulated surface (shop history, insurer intake, claim payout, app shell) shows a visible "Simulated" label. Real calls show a "Live" label. Judges must never be misled.
5. **Demo mode must work offline.** With `DEMO_OFFLINE=1`, every external call is served from recorded fixtures in `api/tests/fixtures/`, and the UI says "Replay".
6. **Secrets stay server-side.** Nothing from `.env` reaches `web/`. The frontend only talks to our API.
7. **Do not copy Paytm's branding.** No Paytm logo, colours or screen designs. The merchant screen is our own design, captioned "Concept: inside Paytm for Business".
8. **Accessibility is part of done.** WCAG 2.2 AA contrast, keyboard access, visible focus, `prefers-reduced-motion`, and `lang="ta"` on Tamil text.
9. **No AI-template look.** The anti-pattern table in `docs/DESIGN_SYSTEM.md` is binding: no gradients, glass, drop shadows, big radii, emoji, sparkle icons, bento or three-card rows, terminal-style panels, hover animations, or Inter/Space Grotesk/Instrument Serif. `pnpm lint:design` must pass.
10. **Don't build what doesn't apply.** No accounts, logins, passwords, sessions, email or crash reporting. `docs/PREFLIGHT.md` lists what we skip and why.

## Stack (do not add to it without a line in `docs/DECISIONS.md`)

- **API:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, LangGraph, httpx, reportlab, pytest. Packages managed with `uv`.
- **Database:** Postgres on Supabase through `DATABASE_URL`. With `DEMO_OFFLINE=1` it falls back to local SQLite.
- **Web:** Vite, React, TypeScript (strict), Tailwind CSS v4, shadcn/ui (restyled), `motion` (motion.dev). Fonts: Anek Tamil and IBM Plex Mono. Icons: our own SVG glyphs, no icon library. Packages managed with `pnpm`.
- **Live updates:** Server-Sent Events from `GET /api/stream`.

## Commands

```bash
# API
cd api && uv sync && uv run uvicorn app.main:app --reload --port 8000
uv run pytest -q                      # all tests
uv run python scripts/gen_data.py     # simulated street + eval set
uv run python scripts/eval.py         # false-claim / missed-claim rates
# Web
cd web && pnpm i && pnpm dev          # http://localhost:5173
pnpm lint && pnpm lint:design && pnpm typecheck && pnpm build
# Full offline rehearsal
DEMO_OFFLINE=1 (run both) and open /console
```

## Conventions

- **Python:** type hints everywhere, `ruff` for format and lint, no bare `except`, money as integer paise (`amount_paise: int`), times as timezone-aware datetimes in `Asia/Kolkata`.
- **TypeScript:** strict, no `any`, components in PascalCase, one component per file, data fetching in `web/src/lib/api.ts`, design tokens only (no raw hex in components).
- **Naming:** use the domain words from `docs/PRODUCT.md`: shop, street, baseline, drop, street event, ask, file, pay back, evidence pack, batch.
- **Commits:** small, imperative ("Add street quorum rule"). Commit after every working step. Never commit `.env`.

## Definition of done (per task)

The code runs. Tests for it pass (`uv run pytest -q`, plus `pnpm typecheck` for web). It works with `DEMO_OFFLINE=1`. Simulated parts are labelled. No new warnings in the console. You explain in two lines what changed and what to check by hand.

## When unsure

Choose the simpler, more reliable option. Say what you assumed. Do not widen the scope: the "Not building" list in `docs/PRODUCT.md` is binding.
