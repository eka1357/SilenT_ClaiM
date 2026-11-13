# IMPLEMENTATION_PLAN.md

**Confirmed on 13 Nov: code written before the event is allowed.** We build everything before the finale on Sunday 15 Nov (IVB, Royapettah, Chennai). The finale day is for the Paytm staging keys, a last polish, rehearsal and the demo. The reporting time and schedule come through the finalist WhatsApp group.

The rule at every checkpoint: the demo runs end to end, even if parts are still plain. Build the spine first, then polish.

## Done

| Task | What | Commit |
|---|---|---|
| A | Simulated data, pure detector rules, unit tests, held-out eval (18 claims filed, 17 right; 1 of 18 closures missed) | `441ac57`, `5b6935a` |
| B | Open-Meteo, Sarvam TTS (`bulbul:v3`) and STT (`saaras:v4`), classifier (`sarvam-105b-conversations`), replay fixtures, offline contract tests | `ddbc407` |
| C | Paytm staging client in pending mode, checksum signing, redaction, startup guard, `paytm_spike.py` with `--probe`, `--create`, `--order-id` | `c5e71e5` |

## Build order (before the finale)

| Day | Task | Done when |
|---|---|---|
| Fri 13 | **D1 Backend spine:** DB and seed, scenario runner and clock, SSE stream, LangGraph `sense, confirm, ask, classify, file`, consent and voice endpoints, evidence PDF, demo personas (Selvi's consent is the only real tap; the other six consents and Meena's and Kavya's replies are automatic and labelled simulated) | With `DEMO_OFFLINE=1`, a 21 Oct run gives 9 drops and 7 consent asks; Selvi's tap files her claim; her PDF downloads; pytest green |
| Fri 13 | **D2 Adjuster and pay back:** batches, `POST /api/batches/{id}/approve`, `payback` node (pending mode until keys), `PAYBACK_ENABLED`, metrics endpoint, refund idempotency and cap enforced in the database | Approving the batch produces 7 refund lines labelled "Simulated: keys pending"; a second approve sends nothing; pytest green |
| Sat 14 | **E1 Web scaffold and console:** Vite, Tailwind v4, shadcn (restyled), tokens, fonts, glyphs, `design-lint.mjs`; `/console` with the street (`Shopfront`, `Shutter`, `RoadBand`), `CaseFile` and `Receipt`, wired to SSE | Pressing "Reset and run the flood" plays the whole run on screen |
| Sat 14 | **E2 Merchant, adjuster and privacy screens:** `/merchant` (phone frame, voice prompt, share disclosure, consent button, money-back receipt), `/adjuster` (batch table, PDF preview, approve), `/privacy` | The full demo path works by clicking through, offline |
| Sat 14 | **F Polish and tests:** the three signature moments, skeletons, error states, reduced motion, Playwright demo spec with axe, `pnpm lint:design` | DESIGN_SYSTEM acceptance criteria pass; E2E green offline |
| Sat 14 night | **G Freeze and preflight:** code freeze, the "night before" list in PREFLIGHT.md, five timed pitch rehearsals, a backup video in pending mode | Every box ticked |

## Finale day (Sun 15)

1. **Paytm keys first:** put the staging MID and key in `api/.env`, set `PAYTM_MODE=staging`, run `paytm_spike.py --probe`, then `--create`, pay ₹35 with the test credentials, then `--order-id <ORDER_ID>`. Record the Paytm fixtures. If the refund fails, keep `PAYTM_MODE=pending` and use the fallback line in DEMO_SCRIPT.md.
2. Run the full demo live once, then once with `DEMO_OFFLINE=1`.
3. Ask a Tamil speaker at the venue to listen to the prompt and, if they're willing, record the four replies; swap them in only if there is time to re-run the tests.
4. Re-record the backup video with the live refund.
5. Rehearse twice. After this, no code changes, only configuration if something is down.

**Cut list (if Saturday runs late, cut in this order):** the LLM evidence summary in the PDF, then the voice-note path (keep the tap path), then the sparklines (keep the status words), then the shutter and receipt animations (keep the states), then the adjuster PDF preview (keep the link). **Never cut:** the real rainfall call, the Tamil voice prompt, the staging refund, the Simulated and Live labels, or the eval number.

## Prompts for Antigravity (one per block)

Start each block with: "Read AGENTS.md and the docs it points to for this block. Plan first, show me the plan, then build. Stop at the checkpoint and tell me how to verify it."
