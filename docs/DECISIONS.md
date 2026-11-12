# DECISIONS.md

Short decision records. Add one before adding a dependency or changing a rule.

| # | Decision | Why | Rejected |
|---|---|---|---|
| D1 | A feature inside Paytm for Business, not a new app | Past winners and Paytm's own buildathon favour fitting into existing products | A standalone insurance app |
| D2 | Payments silence + street quorum + rain as the trigger | Only Paytm can see a street stop paying; it beats weather-only cover on fraud and on proof of loss | Weather-only parametric cover (already built elsewhere, e.g. Guidewire DEVTrails 2026) |
| D3 | Deterministic rules move money; the LLM only labels text | Safety, testability, and the judges' trust | An LLM deciding eligibility |
| D4 | The automatic payout is only the ₹35 plan-fee refund; the claim itself goes to a human adjuster | Real and runnable on Paytm staging; no fake insurer API | Simulating an instant claim payout as if it were real |
| D5 | FastAPI + LangGraph | Eka's strongest stack, and `interrupt()` fits "wait for the merchant" | CrewAI/AutoGen (looser control), n8n (hard to test) |
| D6 | Vite + React + Tailwind v4 + shadcn/ui | Fast local dev, and the reference libraries (21st.dev, React Bits, Skiper, Watermelon) ship shadcn-style components | Next.js (no need for SSR) |
| D7 | `motion` as the only animation library | Covers all three signature moments, supports reduced motion, has a small surface | GSAP (overlap), Lenis (scroll hijack in an app), Barba (SPA) |
| D8 | Custom SVG charts | 2 small visuals (sparklines and shutters) do not justify d3 or a chart library | bklit/d3, Recharts |
| D9 | SSE for live updates | One-way, simple, auto-reconnects, needs no extra service | WebSockets, Supabase Realtime |
| D10 | Postgres on Supabase, SQLite when offline | Matches the deck; the venue Wi-Fi may fail | Supabase only |
| D11 | Recorded fixtures plus a visible Replay mode | The demo must survive network failure without lying | Hiding failures |
| D12 | Tamil first, English gloss | Chennai merchants and Chennai judges | English-only UI |
| D13 | Thresholds 28 trading days / 30% / 60% / 15 mm / 2 of 3 days | Starting points; the rain gate is low because the grid understates floods. Tuned on 140 cases, reported on 60 held out | Tuning on the reported set |
| D14 | Anek Tamil (all text) + IBM Plex Mono (figures) | One Indian-made family draws Tamil and Latin as one design; its width axis gives signage-style headings. Avoids the fonts that read as AI-template | Inter, Space Grotesk, Instrument Serif (flagged as AI-template tells). The deck still uses Instrument Serif and Inter until it is re-skinned |
| D15 | Our own ~12 SVG glyphs; no icon library | Icons only where they carry meaning; "lucide everywhere" reads as AI-template | lucide-react (allowed only inside generated shadcn primitives) |
| D16 | The street drawn as two rows of shopfronts with shutters; metrics as a printed receipt | Comes from the merchant's world and makes the demo memorable; avoids bento grids and three-card rows | A tile grid of KPI cards |
| D17 | No accounts or logins | Fixed personas are enough for a demo; removes passwords, sessions, reset links and CSRF concerns | Auth for the adjuster |
| D18 | Kill switches `PAYBACK_ENABLED` and `DEMO_OFFLINE`, spending caps, rate limits | The only real money-and-cost risks in a demo | Crash reporting, backups, email (not applicable; see PREFLIGHT.md) |
| D19 | `numpy` and `pandas` for `gen_data.py`, `eval.py`, and CSV fixtures | Deterministic seeded (`2026`) Poisson/log-normal data generation and tabular evaluation | Hand-rolled CSV loops or heavier ML packages |
