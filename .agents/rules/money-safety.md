---
trigger: glob
globs: api/app/detector/**, api/app/integrations/paytm.py, api/app/agents/**
---

# Money safety rules (read docs/SECURITY.md)

- `detector/rules.py` is pure: no I/O, no LLM, no randomness. 100% branch coverage.
- The refund amount is only `PLAN_FEE_PAISE` from `detector/config.py`. Nothing else may set it.
- Refund ID is `SC-{claim_id}`; never generate a new ID on retry.
- Pay back runs only after an adjuster approves the batch. No agent node may call it directly.
- Refuse to start unless `PAYTM_MODE` is `pending` or `staging` and the host is one of Paytm's two staging hosts (`securestage.paytmpayments.com` or `securegw-stage.paytmpayments.in`), never a production host. In `pending`, never send a request and label every result "Simulated: keys pending".
- LLM output must parse into the cause enum; anything else becomes `other` and goes to a human.
- Any change here needs a line in `docs/DECISIONS.md` and a test that would have failed before it.
