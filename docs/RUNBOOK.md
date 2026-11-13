# RUNBOOK.md: Finale-Day Execution (Windows PowerShell)

All commands assume the repo root `C:\Projects\Silent_Claim` in Windows PowerShell.

## 1. Start the API and Web App

Open **PowerShell Window 1 (API)**:

```powershell
cd C:\Projects\Silent_Claim\api
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **PowerShell Window 2 (Web)**:

```powershell
cd C:\Projects\Silent_Claim\web
pnpm i
pnpm dev
```

Vite starts with `--host` on port `5173` and prints both `Local` and `Network` URLs.

## 2. Open `/merchant` on Your Phone over the Hotspot

1. Connect the laptop and phone to the same phone hotspot.
2. Find the laptop's hotspot IPv4 address (or read the `Network:` line printed by `pnpm dev`):
   ```powershell
   ipconfig | Select-String "IPv4"
   ```
3. On the phone browser, open:
   ```text
   http://<LAPTOP_HOTSPOT_IPV4>:5173/merchant
   ```
   Example: `http://192.168.43.102:5173/merchant` (or `http://172.20.10.2:5173/merchant`).
   Vite proxies `/api/*` to `http://localhost:8000` on the laptop, so the phone only needs port `5173`.

## 3. Put the Paytm Staging MID and Key in `api/.env`

When the organisers share the Paytm staging credentials on finale morning, edit `C:\Projects\Silent_Claim\api\.env`:

```ini
PAYTM_MID=<STAGING_MID>
PAYTM_MERCHANT_KEY=<STAGING_MERCHANT_KEY>
PAYTM_MODE=staging
```

## 4. Probe Paytm Staging Hosts and Create a ₹35 Staging Order

In **PowerShell Window 3**:

```powershell
cd C:\Projects\Silent_Claim\api

# 1) Probe both Paytm staging hosts across all 4 endpoints
uv run python scripts/paytm_spike.py --probe

# 2) Create a Rs 35 staging order for Selvi (shop_01)
uv run python scripts/paytm_spike.py --create
```

`--create` prints `orderId=<ORDER_ID>` and `txnToken=<TXN_TOKEN>` and writes `api/runs/paytm_checkout.html`.

## 5. Pay ₹35 in `api/runs/paytm_checkout.html` with Test Credentials

1. Open the generated checkout page in the browser:
   ```powershell
   Invoke-Item C:\Projects\Silent_Claim\api\runs\paytm_checkout.html
   ```
2. Click **Pay Rs 35.00** and complete payment using Paytm's staging test credentials (for example, test UPI `7777777777@paytm` or the staging test card/netbanking details provided by Paytm).

## 6. Verify the Order & Refund Spike (`--order-id <ORDER_ID>`)

Test the status check, idempotent refund (`SC-spike_01`), and refund status poll against that paid order:

```powershell
cd C:\Projects\Silent_Claim\api
uv run python scripts/paytm_spike.py --order-id <ORDER_ID>
```

Note: once an order is refunded by the spike, create and pay a **second** fresh ₹35 order (`uv run python scripts/paytm_spike.py --create` and pay in `api/runs/paytm_checkout.html`) so Selvi's order is unrefunded for the live demo run.

## 7. Set `PAYTM_DEMO_ORDER_ID` and `PAYTM_MODE=staging`

Paste the paid, unrefunded `<ORDER_ID>` into `C:\Projects\Silent_Claim\api\.env`:

```ini
PAYTM_MODE=staging
PAYTM_DEMO_ORDER_ID=<ORDER_ID>
PAYBACK_ENABLED=1
DEMO_OFFLINE=0
```

## 8. Record the Paytm and Integration Fixtures

```powershell
cd C:\Projects\Silent_Claim\api
Copy-Item runs\paytm_spike.json tests\fixtures\paytm_refund_staging.json -Force
uv run python scripts/record_fixtures.py
```

## 9. Run One Full Live Rehearsal and One `DEMO_OFFLINE=1` Rehearsal

### A. Full Live Run (`DEMO_OFFLINE=0`)
1. Restart the API in Window 1 (`$env:DEMO_OFFLINE="0"; uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`).
2. Open `http://localhost:5173/console` on the laptop and `http://<LAPTOP_HOTSPOT_IPV4>:5173/merchant` on the phone.
3. Click **Reset and run the flood**, tap **ஆம், பதிவு செய்யுங்கள்** on the phone, and click **Approve batch (7)** on `/adjuster`.
4. Confirm Selvi's refund line prints on `/console` and `/merchant` (`Live` if using an unrefunded staging order; note that once refunded on staging, create one more ₹35 order for the judges' run).

### B. Full Offline Run (`DEMO_OFFLINE=1`)
1. In Window 1, start the API in offline replay mode:
   ```powershell
   $env:DEMO_OFFLINE="1"
   uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
2. On `/console`, confirm integration badges read `Replay`, click **Reset and run the flood**, tap consent on `/merchant`, approve the batch on `/adjuster`, and verify all 7 refund lines print.

## 10. If This Fails, Do This

| Failure during demo | Immediate action |
|---|---|
| **Network drops mid-demo** | Keep going; calls fall back to `Replay` on their own (`weather.py`, `sarvam.py`, and `llm.py` each have a 4 s timeout and automatic fixture fallback). |
| **Paytm refund fails** | Keep `PAYTM_MODE=pending` and use the fallback line in `docs/DEMO_SCRIPT.md`: *"The refund call is built and signed against Paytm's staging API; today it runs simulated, and it's labelled that way."* |
| **API crashes** | Restart it with `$env:DEMO_OFFLINE="1"; uv run uvicorn app.main:app --host 0.0.0.0 --port 8000` and rerun the flood (**Reset and run the flood**). |
| **Browser crashes** | Reopen `http://localhost:5173/console` and press **Reset and run the flood**. |

