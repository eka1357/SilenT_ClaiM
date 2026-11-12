# TESTING.md

## Layers

| Layer | Tool | Scope | Must pass before |
|---|---|---|---|
| Unit | pytest | `detector/` (100% branch coverage), `format`, idempotency key builder, Pydantic schemas | every commit that touches them |
| Eval | `scripts/eval.py` | 200 labelled shop-weeks; reports held-out rates | rules changes, and the demo |
| Contract | pytest + recorded fixtures | `paytm.py`, `sarvam.py`, `weather.py`, `llm.py` parse real recorded responses; offline | every integration change |
| Live smoke | `pytest -m live` (opt-in) | one real call per integration | morning of the event |
| Graph | pytest | LangGraph paths: file, ask→leave→close, ask→qr_switch→human, refund failure | agent changes |
| E2E | Playwright (`web/e2e/demo.spec.ts`) + `@axe-core/playwright` | Reset → run flood → merchant taps → adjuster approves → refund shown; once live, once with `DEMO_OFFLINE=1` | the code freeze |
| Types and lint | `ruff`, `pnpm typecheck`, `pnpm lint` | everything | every commit |
| Design lint | `pnpm lint:design` (`web/scripts/design-lint.mjs`) | the anti-pattern rules in DESIGN_SYSTEM.md | every UI commit |

## Required unit cases for `decide()`

1. Flood street, Selvi: `file`.
2. Same street, Ravi (still trading): `none`.
3. Meena, on leave from 18 Oct: `ask`, reason `inactive_before_event`.
4. Leave that starts on 20 Oct (one day before): `ask`.
5. Anwar, Monday holiday on 19 Oct: still eligible, `file`.
6. Kavya, QR switch on 19 Oct: `ask`.
7. A lone drop with no quorum (illness): `ask`, reason `lone_drop`.
8. Quorum met but 3 mm of rain (power cut or strike): `ask`, reason `no_rain_signal`.
9. Under 14 trading days of history: `ask`.
10. Returning after a month's leave: the baseline equals the median of the 28 trading days before the leave (not zero).
11. Payout cap: a second refund for the same shop in the same month is refused.
12. Refund idempotency: calling payback twice for one claim sends one refund request.
13. With `PAYBACK_ENABLED=0`, approval files the batch but sends no refund, and the claim shows "Refunds paused".
14. The redaction function removes keys, checksums and signatures from a recorded Paytm response.
15. The 31st request in a minute to `/api/asks/*` returns 429.

## Rules for tests

Tests never call the network unless marked `live`. Fixtures are real recorded responses with secrets removed, never hand-written. Every bug found in rehearsal gets a test before the fix. Name tests by behaviour: `test_leave_before_flood_is_asked_not_filed`.

## Acceptance gate for the demo build

`uv run pytest -q` is green. `pnpm typecheck && pnpm build` are green. The E2E run is green live and offline, with zero serious axe issues. `eval.py` prints its numbers, and those exact numbers are on the console and in the pitch.
