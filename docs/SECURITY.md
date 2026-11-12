# SECURITY.md

## Secrets

All keys are in `api/.env`, loaded with pydantic-settings and never logged. `.env` is in `.gitignore`; `.env.example` lists names only. The web app holds no keys and calls only `/api/*`. Before any push, run a secret scan (`gitleaks detect` or a grep for `KEY=`). If a key leaks, rotate it at once.

## Money safety (the most important section)

1. **Staging only.** On startup the API checks that `PAYTM_MODE` is `pending` or `staging`, and in `staging` that the host is `securestage.paytmpayments.com`. It refuses to start otherwise. In `pending` nothing is sent to Paytm and every Paytm result is labelled "Simulated: keys pending".
2. **Fixed amount.** The refund amount is the constant `PLAN_FEE_PAISE = 3500` in `detector/config.py`. No request body, LLM output or URL parameter can change it.
3. **Caps.** One refund per shop per calendar month, checked in the database inside a transaction, with a unique constraint on `(shop_id, month)`.
4. **Idempotency.** Refund ID = `SC-{claim_id}`, unique in `refunds`. A retry reuses it, so Paytm treats it as the same refund.
5. **Human in the loop.** Pay back runs only after `POST /api/batches/{id}/approve`. Agents cannot call it.
6. **Checksums.** Every request to Paytm is signed, and any callback is verified with the official checksum library before it is trusted.

## LLM and voice input

Voice notes and transcripts are untrusted input. The classifier prompt treats the transcript as data inside delimiters, and its output must parse into the enum `{flood_closure, leave, illness, qr_switch, other}` with a confidence between 0 and 1. Anything else becomes `other`, which goes to a human. LLM text is never rendered as HTML.

## Privacy

Only synthetic merchants and synthetic payment data. Recorded voice samples come from the team, with consent, and are not uploaded anywhere except the STT call. Logs keep shop IDs, not phone numbers. The evidence PDF says "Synthetic data for demonstration".

## API surface

CORS allows only `http://localhost:5173` (and the demo laptop's LAN address if needed). Uploads accept audio only, 2 MB at most and 60 s at most. `/api/scenario/*` is enabled only when `DEMO_MODE=1`. Errors return plain messages without stack traces. Every request body is validated with Pydantic.

**Rate limits** (in memory, per client IP): 30 requests a minute on `/api/asks/*` and `/api/scenario/*`, the endpoints that cost money. Over the limit returns 429 with a plain message.

**CSRF:** not applicable. The API uses JSON bodies with no cookies or sessions, and CORS allows only our own origin.

**HTTPS:** the demo runs on localhost. If we deploy a link for judges, use a host that serves HTTPS by default. Every outbound call (Paytm, Sarvam, the LLM, Open-Meteo) is already HTTPS.

## Database access

The API connects with a dedicated Postgres role that can read and write only our tables (no `CREATE`, no `DROP`, no access to other schemas). Never use the Supabase `service_role` key, and never give the browser a database key: the browser talks only to our API.

## Logging

Log IDs, decisions, latencies and integration modes. Never log API keys, Paytm checksums, request signatures, raw audio, full transcripts or phone numbers. The `raw_response` stored for refunds goes through a redaction function, with a unit test, before it is saved.

## Cost control and kill switches

- Set a spending cap or budget alert on the LLM and Sarvam accounts before the event.
- TTS audio for each prompt is generated once and cached on disk; repeat runs reuse it.
- `PAYBACK_ENABLED=0` blocks every refund instantly; the UI shows "Refunds paused".
- `DEMO_OFFLINE=1` serves every external call from fixtures.

## Not applicable to this demo

There are no accounts, so there are no passwords to hash, sessions to expire or reset links to secure, and no signup forms that need CAPTCHA or honeypots. `docs/PREFLIGHT.md` lists every skipped item and why.

## Note for judges

Production would add authentication, encryption at rest, IRDAI-compliant consent records, the insurer's own claim system as the source of truth, and data-sharing agreements. Those are out of scope for the demo, and we say so.
