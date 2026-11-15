# RUNBOOK.md: finals day (Windows PowerShell)

Repo root: `C:\Projects\Silent_Claim`. Paytm staging keys only, never production.

## Finals day at a glance (solo)

| Time | Do |
|---|---|
| 08:00 to 09:00 | Check in. Plug in, start the hotspot, then §1 and §2 (the laptop's address may change). From here you can demo in simulated mode, keys or not |
| Paytm (decided) | Simulated today: the test account returned error 239 and Paytm's team said to leave it. Keep `PAYTM_MODE=pending`, skip §3 to §6 and §8, and record the demo video now with the §6 step 3 setup |
| 09:30 to 12:00 | Rehearse at your table. No code changes unless a rehearsal finds a demo-breaker, and then only before 11:00 |
| 12:00 to 16:00 | Mentor rounds and shortlisting decide the Top 10. Every visit is the demo: after each one, reset (§1) |
| 16:30 to 18:30 | Top 10 jury round: reset (§1), then the demo |

## 0. Before the event (done Saturday)

1. **Empty `DATABASE_URL` in `api/.env`.** The line must read `DATABASE_URL=` with nothing after it. With `DEMO_OFFLINE=0` the API connects to this URL, and the template's placeholder Postgres host makes it exit at startup. Empty means SQLite in both modes.
2. **Install once, tonight only:** `uv sync` in `api` and `pnpm i` in `web`. No installs at the venue.
3. **One live run with Paytm still pending.** Keep `PAYTM_MODE=pending`, start the API in live mode (§1), then Reset and run the flood, tap, approve. Weather, voice and classifier read Live; the refunds read simulated. `demo_check` runs in Replay, so this is the only test of live mode through the server.
4. From the repo root: `powershell -ExecutionPolicy Bypass -File scripts\demo_check.ps1` gives 9/9 PASS.
5. **Windows:** pause updates for a week (Settings > Windows Update), set sleep to Never when plugged in, and check that Win+Alt+R (Xbox Game Bar) records a browser window.
6. Copy `web\test-results\demo-backup.webm` to the phone. Charge the laptop, the phone and a power bank.
7. Record a narrated backup video in simulated mode, the same way as §6 step 3. Tomorrow's live recording replaces it if there's time.

## 1. Start the API and the web app

Window 1, API in live mode:

```powershell
cd C:\Projects\Silent_Claim\api
$env:DEMO_OFFLINE="0"
Remove-Item Env:PAYTM_MODE -ErrorAction SilentlyContinue
uv run uvicorn app.main:app --port 8000
```

Window 2, web:

```powershell
cd C:\Projects\Silent_Claim\web
pnpm dev
```

- Use these exact lines every time you start the API. `$env:` settings override `api/.env` and stay set in that window, so the live lines also clear the Replay settings from §7.
- No `--reload`: on Windows it can leave an orphan process holding port 8000.
- No `--host 0.0.0.0`: the phone reaches the API through Vite's proxy, so the API stays on 127.0.0.1.
- To restart: Ctrl+C in Window 1, then the same four lines.
- To clear the screens without running the flood, run this, then refresh `/console`, `/adjuster` and the phone:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/scenario/reset
```

## 2. Phone on the hotspot

1. The laptop joins the phone's hotspot. VPN off.
2. `pnpm dev` prints a `Network:` URL. On the phone, open `http://<that IP>:5173/merchant`.
3. If the phone can't load it, Windows Firewall is blocking Node on this network. Either set the hotspot to Private (Settings > Network & internet > Wi-Fi > the hotspot > Network profile type > Private), or allow Node.js on Private and Public (Windows Security > Firewall & network protection > Allow an app through firewall).
4. Do this first thing in the morning. The phone tap is the one moment you can't fake.

## 3. Paytm staging keys (at the event)

When the organisers share them, put them in `api/.env`. Use the same keys all day: an order can only be refunded with the keys of the account that took the payment.

```ini
PAYTM_MID=<STAGING_MID>
PAYTM_MERCHANT_KEY=<STAGING_MERCHANT_KEY>
PAYTM_MODE=staging
```

## 4. Probe, then pay ₹35 orders

Window 3:

```powershell
cd C:\Projects\Silent_Claim\api
uv run python scripts/paytm_spike.py --probe
```

Pay five right away and more at lunch. For each one, create the order, pay it right away, and write its `orderId` on a numbered list.

```powershell
uv run python scripts/paytm_spike.py --create
Invoke-Item runs\paytm_checkout.html
```

Pay with Paytm's staging test credentials (test UPI `7777777777@paytm`, or the test card Paytm lists). Each `--create` overwrites `paytm_checkout.html`, so pay each order before creating the next.

| Order | Used for |
|---|---|
| 1 | Spike refund test (§5) |
| 2 | Live rehearsal and demo video (§6) |
| 3 onwards | One per live demo: mentor visits, shortlisting, the jury, and spares |

An order can be refunded only once, so every live run needs its own unused order. Cross each one off as you use it.

## 5. Spike refund test (order 1)

```powershell
uv run python scripts/paytm_spike.py --order-id <ORDER_1>
```

This proves the refund path on staging before the rehearsal and shows how fast Paytm answers. Don't copy its output into `tests/fixtures`, and skip `record_fixtures.py` on the day: Replay runs with Paytm in pending mode (§7), so it needs no Paytm fixture.

## 6. Live rehearsal and demo video (order 2)

1. In `api/.env`: `PAYTM_DEMO_ORDER_ID=<ORDER_2>`, `PAYTM_MODE=staging`, `PAYBACK_ENABLED=1`.
2. Restart the API in live mode (§1). It reads the order ID only at startup.
3. Put `/console` and a narrow `/merchant` window side by side on the laptop. Start a screen recording with your mic on (Snipping Tool > Record > select the whole screen; Xbox Game Bar records only one window). Say the script as you go: **Reset and run the flood**, tap **ஆம், பதிவு செய்யுங்கள்** in the merchant window, then the batch card and **Approve batch (7)**. Stop recording.
4. Check Selvi's line: ₹35, Live, refund ID `SC-clm_...`. The other six read "Simulated refund (no staging payment)". Note how many seconds the refund lines took to appear after **Approve batch**: the screens pause while Paytm answers.
5. This recording is your demo video for submission and your main backup, because it shows a Live refund. `demo-backup.webm` is the second backup. Copy both to the phone.

## 7. Replay rehearsal

```powershell
cd C:\Projects\Silent_Claim\api
$env:DEMO_OFFLINE="1"
$env:PAYTM_MODE="pending"
uv run uvicorn app.main:app --port 8000
```

The badges read Replay. Reset and run, tap, approve: all 7 refund lines print as simulated. Paytm must be `pending` here: no Paytm fixture is recorded, so Replay with `staging` would show Selvi's refund as "Paytm staging unavailable". This is the run you fall back to if the venue network dies.

## 8. Arm for each live demo (next unused order)

1. In `api/.env`: `PAYTM_DEMO_ORDER_ID=<next unused order>`.
2. Restart with the live lines in §1. They also clear the Replay settings from §7.
3. Clear the screens with the reset command in §1. From `demo-freeze-2`, reset moves the rehearsal's staging refund into `api/runs/live_refunds.jsonl`, so Selvi's monthly cap is clear. Without that fix, use the "Monthly cap reached" row in §10 now.
4. Repeat this section before every live demo.

## 9. Fifteen minutes before the slot

- [ ] `/console` idle on the trading street; badges read Live
- [ ] Laptop: one tab on `/console` (its links open `/adjuster`); zoom 100%; Do not disturb on; plugged in; other apps closed
- [ ] Projector connected, console readable from the back of the room
- [ ] Phone: `/merchant` loaded as Selvi; Do Not Disturb on; auto-lock off; brightness and media volume up
- [ ] Backup video open and paused, on the laptop and on the phone
- [ ] `PAYTM_MODE=pending` in `api/.env`, and the Paytm badge reads Simulated
- [ ] Kill switches known by heart: `DEMO_OFFLINE=1` replays everything; `PAYBACK_ENABLED=0` pauses refunds
- [ ] Solo: phone face up beside the laptop, backup video one click away

## 10. If this fails

| Problem | Do this |
|---|---|
| API exits at startup in live mode | `DATABASE_URL` in `api/.env` must be empty (§0) |
| Port 8000 already in use | `Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess -Force`, then start again |
| Phone can't open `/merchant` | Same hotspot? VPN off? Firewall step in §2. Last resort: `/merchant` in a narrow laptop window |
| Selvi reads "Monthly cap reached" | A rehearsal refund is still in the database. Stop the API, run `Remove-Item C:\Projects\Silent_Claim\api\silent_claim.db*`, set a fresh order in `api/.env`, and start the API again: it rebuilds the database from the seed. On stage, use the line in DEMO_SCRIPT.md |
| Selvi reads "Pending at Paytm" | Fine: Paytm accepted the refund. Use the line in DEMO_SCRIPT.md |
| Screens pause after **Approve batch** | Paytm is answering and the server waits for it. Use the filler line in DEMO_SCRIPT.md |
| Someone taps No or the voice button on Selvi's phone | Use the line in DEMO_SCRIPT.md, then **Reset and run the flood** |
| Refund fails or staging is down | Use the fallback line in DEMO_SCRIPT.md. For the next run, set `PAYTM_MODE=pending` |
| Network drops | Keep going. Calls fall back to Replay after 4 s |
| API crashes | Play the backup video. Meanwhile restart with the Replay lines in §7, then **Reset and run the flood** |
| Browser crashes | Reopen `http://localhost:5173/console` and press **Reset and run the flood** |
