# RUNBOOK.md: finals day (Windows PowerShell)

Repo root: `C:\Projects\Silent_Claim`. Paytm staging keys only, never production.

## 0. Tonight

1. **Empty `DATABASE_URL` in `api/.env`.** The line must read `DATABASE_URL=` with nothing after it. With `DEMO_OFFLINE=0` the API connects to this URL, and the template's placeholder Postgres host makes it exit at startup. Empty means SQLite in both modes.
2. **Install once, tonight only:** `uv sync` in `api` and `pnpm i` in `web`. No installs at the venue.
3. **One live run with Paytm still pending.** Keep `PAYTM_MODE=pending`, start the API in live mode (§1), then Reset and run the flood, tap, approve. Weather, voice and classifier read Live; the refunds read simulated. `demo_check` runs in Replay, so this is the only test of live mode through the server.
4. From the repo root: `powershell -ExecutionPolicy Bypass -File scripts\demo_check.ps1` gives 9/9 PASS.
5. **Windows:** pause updates for a week (Settings > Windows Update), set sleep to Never when plugged in, and check that Win+Alt+R (Xbox Game Bar) records a browser window.
6. Copy `web\test-results\demo-backup.webm` to the phone. Charge the laptop, the phone and a power bank.

## 1. Start the API and the web app

Window 1, API in live mode:

```powershell
cd C:\Projects\Silent_Claim\api
$env:DEMO_OFFLINE="0"
uv run uvicorn app.main:app --port 8000
```

Window 2, web:

```powershell
cd C:\Projects\Silent_Claim\web
pnpm dev
```

- Set `$env:DEMO_OFFLINE` every time you start the API. It overrides `api/.env` and stays set in that window, so a window that once ran Replay stays in Replay until you set it back to `"0"`.
- No `--reload`: on Windows it can leave an orphan process holding port 8000.
- No `--host 0.0.0.0`: the phone reaches the API through Vite's proxy, so the API stays on 127.0.0.1.
- To restart: Ctrl+C in Window 1, then the same three lines.
- To clear the screens without running the flood, run this, then refresh `/console`, `/adjuster` and the phone:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/scenario/reset
```

## 2. Phone on the hotspot

1. The laptop joins the phone's hotspot. VPN off.
2. `pnpm dev` prints a `Network:` URL. On the phone, open `http://<that IP>:5173/merchant`.
3. If the phone can't load it, Windows Firewall is blocking Node on this network. Either set the hotspot to Private (Settings > Network & internet > Wi-Fi > the hotspot > Network profile type > Private), or allow Node.js on Private and Public (Windows Security > Firewall & network protection > Allow an app through firewall).
4. Do this first thing in the morning. The phone tap is the one moment you can't fake.

## 3. Paytm staging keys (finals morning)

When the organisers share them, put them in `api/.env`:

```ini
PAYTM_MID=<STAGING_MID>
PAYTM_MERCHANT_KEY=<STAGING_MERCHANT_KEY>
PAYTM_MODE=staging
```

## 4. Probe, then pay four ₹35 orders

Window 3:

```powershell
cd C:\Projects\Silent_Claim\api
uv run python scripts/paytm_spike.py --probe
```

Then four times: create an order, pay it right away, and write its `orderId` on paper.

```powershell
uv run python scripts/paytm_spike.py --create
Invoke-Item runs\paytm_checkout.html
```

Pay with Paytm's staging test credentials (test UPI `7777777777@paytm`, or the test card Paytm lists). Each `--create` overwrites `paytm_checkout.html`, so pay each order before creating the next.

| Order | Used for |
|---|---|
| A | Spike refund test and the Replay fixture (§5) |
| B | Live rehearsal (§6) |
| C | The judges' run (§8) |
| D | Spare: a second round or a retry |

An order can be refunded only once, so every live run needs its own unused order.

## 5. Spike refund test and fixture (order A)

```powershell
uv run python scripts/paytm_spike.py --order-id <ORDER_A>
Copy-Item runs\paytm_spike.json tests\fixtures\paytm_refund_staging.json -Force
```

Skip `record_fixtures.py` on the day. The other fixtures already pass `demo_check`, and re-recording on a weak network can overwrite good ones.

## 6. Live rehearsal (order B)

1. In `api/.env`: `PAYTM_DEMO_ORDER_ID=<ORDER_B>`, `PAYTM_MODE=staging`, `PAYBACK_ENABLED=1`.
2. Restart the API in live mode (§1). It reads the order ID only at startup.
3. Start recording (Win+Alt+R). `/console`: **Reset and run the flood**. Phone: tap **ஆம், பதிவு செய்யுங்கள்**. `/adjuster`: **Approve batch (7)**. Stop recording (Win+Alt+R).
4. Check Selvi's line: ₹35, Live, refund ID `SC-clm_...`. The other six read "Simulated refund (no staging payment)".
5. This recording is now the main backup video, because it shows a Live refund. `demo-backup.webm` is the second backup.

## 7. Replay rehearsal

```powershell
$env:DEMO_OFFLINE="1"
uv run uvicorn app.main:app --port 8000
```

The badges read Replay. Reset and run, tap, approve: all 7 refund lines print. This is the run you fall back to if the venue network dies.

## 8. Arm for the judges (order C)

1. In `api/.env`: `PAYTM_DEMO_ORDER_ID=<ORDER_C>`.
2. Restart in live mode: `$env:DEMO_OFFLINE="0"`, then uvicorn (§1).
3. Clear the screens with the reset command in §1. From `demo-freeze-2`, reset moves the rehearsal's staging refund into `api/runs/live_refunds.jsonl`, so Selvi's monthly cap is clear. Without that fix, use the "Monthly cap reached" row in §10 now.
4. If there's a second round, repeat this section with order D.

## 9. Fifteen minutes before the slot

- [ ] `/console` idle on the trading street; badges read Live
- [ ] Laptop: only two tabs, `/console` and `/adjuster`; zoom 100%; Do not disturb on; plugged in; other apps closed
- [ ] Projector connected, console readable from the back of the room
- [ ] Phone: `/merchant` loaded as Selvi; Do Not Disturb on; auto-lock off; brightness and media volume up
- [ ] Backup video open and paused, on the laptop and on the phone
- [ ] Paper with orders C and D
- [ ] Kill switches known by heart: `DEMO_OFFLINE=1` replays everything; `PAYBACK_ENABLED=0` pauses refunds
- [ ] Roles: one person talks and drives; the other holds the phone and handles failures

## 10. If this fails

| Problem | Do this |
|---|---|
| API exits at startup in live mode | `DATABASE_URL` in `api/.env` must be empty (§0) |
| Port 8000 already in use | `Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess -Force`, then start again |
| Phone can't open `/merchant` | Same hotspot? VPN off? Firewall step in §2. Last resort: `/merchant` in a narrow laptop window |
| Selvi reads "Monthly cap reached" | A rehearsal refund is still in the database. Stop the API, run `Remove-Item C:\Projects\Silent_Claim\api\silent_claim.db*`, set a fresh order in `api/.env`, and start the API again: it rebuilds the database from the seed. On stage, use the line in DEMO_SCRIPT.md |
| Selvi reads "Pending at Paytm" | Fine: Paytm accepted the refund. Use the line in DEMO_SCRIPT.md |
| Refund fails or staging is down | Use the fallback line in DEMO_SCRIPT.md. For the next run, set `PAYTM_MODE=pending` |
| Network drops | Keep going. Calls fall back to Replay after 4 s |
| API crashes | Play the backup video. Meanwhile restart with `$env:DEMO_OFFLINE="1"`, then **Reset and run the flood** |
| Browser crashes | Reopen `http://localhost:5173/console` and press **Reset and run the flood** |
