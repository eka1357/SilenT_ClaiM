# IMPLEMENTATION_PLAN.md

Two phases. **Phase 0** is before the event: accounts, keys, spikes, data, rules and recorded fixtures. **Phase 1** is the finals day build.

**Rules check first.** We have not seen Chennai's rule on code written before the event. Ask the organisers. If it is not allowed, Phase 0 is practice: keep the docs, data, prompts, fixtures and accounts, and rewrite the code on the day from these docs. Keep a dated git history either way.

## Phase 0: before the event (start now)

| # | Task | Done when |
|---|---|---|
| 0.1 | Accounts and keys: Paytm staging (dashboard.paytmpayments.com), Sarvam, an LLM API, Supabase project. Fill `.env` from `.env.example`. | `GET /api/health` (or the spike scripts) reach all four |
| 0.2 | **Paytm client, written from the docs (no keys yet):** `app/integrations/paytm.py` with request builders, checksum signing, refund ID `SC-{claim_id}`, redaction and the startup guard, plus `scripts/spikes/paytm_spike.py` (₹35 payment → status → refund → refund status) ready to run. With `PAYTM_MODE=pending` it signs requests but never sends them, and returns responses marked simulated. Staging keys arrive on finals day. | Unit tests pass with no network; the spike prints "pending: keys not set" |
| 0.3 | **Sarvam spike:** Tamil TTS of the prompt; STT on three recorded replies (yes / "I'm on leave this month" / "I moved to another QR") | Transcripts readable; a native speaker has checked the prompt line |
| 0.4 | **Data:** `scripts/gen_data.py` as in DATA_SPEC.md | Seeded and repeatable; the flood day shows 9 of 12 dropped |
| 0.5 | **Rules:** `detector/` + unit tests | All DATA_SPEC cases pass, including Meena (leave) and Kavya (QR switch) |
| 0.6 | **Eval:** `scripts/eval.py` | Prints, for the held-out set: claims filed and right, the false-positive and missed-claim rates, the confusion matrix and every misclassified case |
| 0.7 | **Fixtures:** `scripts/record_fixtures.py` saves real responses (rain, TTS wav, STT, classifier, Paytm) | `DEMO_OFFLINE=1 uv run pytest tests/contract` passes with no network |
| 0.8 | **Scaffold:** web (Vite, Tailwind v4, shadcn init, tokens, fonts) and api (FastAPI skeleton, health, SSE echo) | `pnpm dev` and `uvicorn` both run; the console shows a heartbeat from SSE |
| 0.9 | **Rehearse the pitch:** the 90 seconds in DEMO_SCRIPT.md, five times out loud with a timer | Under 90 s with no notes |
| 0.10 | **Preflight:** the "night before" list in PREFLIGHT.md (credits and spending caps, Supabase pause check, cold run by someone new) | Every box ticked |

## Phase 1: finals day (about five build hours; times assume 11:00 to 16:30)

The rule: at every checkpoint, the demo must run end to end, even if parts are still plain. Build the spine first, then polish.

| Time | Build | Checkpoint |
|---|---|---|
| First 20 minutes | **Paytm keys:** put the staging MID and key in `api/.env`, set `PAYTM_MODE=staging`, run `paytm_spike.py`, and record the Paytm fixtures | All four steps PASS. **If the refund fails, keep `PAYTM_MODE=pending` and change the demo line to "simulated refund" (DEMO_SCRIPT.md)** |
| 11:00 to 11:30 | Load data into the DB, scenario runner and clock, `shop.status` over SSE, plain street (two rows of `Shopfront` and a `RoadBand`) | Pressing "Run" changes shop status words live |
| 11:30 to 12:30 | Detector wired in, the LangGraph `sense → confirm → file` path, rain (Live + Replay), plain `CaseFile` | 7 shops reach "Filed" with no merchant step yet |
| 12:30 to 13:15 | `ask` node with interrupt, `/merchant` screen, TTS audio, consent endpoint | Tapping "Yes" on the phone files Selvi's claim |
| 13:15 to 13:45 | Voice note → STT → classifier for Meena and Kavya; evidence PDF | Meena closes as leave; Kavya goes to human review; PDF opens |
| 13:45 to 14:30 | `/adjuster` batch approval → `payback` → real staging refund → refund line on the `Receipt` | Approve shows the Live refund ID and status |
| 14:30 to 15:15 | Polish: the three signature moments (shutters, one tap, the receipt printing), state labels, skeletons, error states, the `/privacy` page | `pnpm lint:design` passes; DESIGN_SYSTEM acceptance criteria 4, 5 and 6 pass |
| 15:15 to 15:45 | Playwright demo spec, offline rehearsal (`DEMO_OFFLINE=1`), fix bugs | E2E is green both live and offline |
| 15:45 to 16:15 | **Freeze code.** Record a backup screen video of the full demo. Rehearse twice. | Video saved on the laptop and on a phone |
| 16:15 to 16:30 | Buffer | n/a |

**Cut list (cut in this order if late):** the LLM evidence summary in the PDF → the voice-note path (keep the tap path) → the sparklines (keep the status words) → the shutter and receipt animations (keep the states) → the adjuster PDF preview (keep the link). **Never cut:** the real rainfall call, the Tamil voice prompt, the staging refund, the Simulated/Live labels, or the eval number.

## Prompts for Antigravity (one per block)

Start each block with: "Read AGENTS.md and the docs it points to for this block. Plan first, show me the plan, then build. Stop at the checkpoint and tell me how to verify it."
