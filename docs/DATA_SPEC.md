# DATA_SPEC.md: rules, thresholds and simulated data

All thresholds live in one file, `api/app/detector/config.py`, under `RULES_VERSION = "2026.11-a"`. Every evidence pack prints that version. The values below are starting points. Tune them on the eval set, then freeze them before the demo.

## Definitions

| Term | Definition | Default |
|---|---|---|
| Trading day | A calendar day on which the shop took at least one payment | n/a |
| Baseline | Median daily income over the shop's last 28 **trading** days before the day being tested. Using trading days means a shop back from a month's leave is compared with its last active month, not with zeros. | 28 trading days |
| Minimum history | A shop needs at least 14 trading days of history, or it is never auto-filed | 14 |
| Drop | Day income below this share of the baseline | 30% |
| Street quorum | Share of all the street's shops with enough history that dropped on the same day | 60% or more |
| Rain gate | Open-Meteo daily `precipitation_sum` for the street's coordinates | 15 mm or more |
| Eligibility | The shop traded normally (did not drop) on at least 2 of the 3 calendar days before the event. One weekly holiday still passes; a leave or a QR switch that started earlier does not. | 2 of 3 |
| Plan-fee refund | One month's fee, refunded once per shop per calendar month | ₹35 (3,500 paise) |

The rain gate is deliberately low. On 21 Oct 2026 the city reported more than 10 cm, but the Open-Meteo grid cell showed only 27.7 mm (45.4 mm over 20 and 21 Oct). Grid data understates street flooding, so a high gate would miss real events.

## Decision table (pure function `decide(shop, day, street, rain) -> Decision`)

| Condition (checked in this order) | Decision |
|---|---|
| Shop has under 14 trading days of history | `ask` |
| Shop did not drop | `none` |
| Shop dropped, not eligible (dropped on 2 or more of the 3 days before) | `ask` (reason `inactive_before_event`) |
| Shop dropped, street quorum met, rain gate met | `file` |
| Shop dropped, quorum met, rain gate not met | `ask` (reason `no_rain_signal`, e.g. a strike or a power cut) |
| Shop dropped, quorum not met | `ask` (reason `lone_drop`) |

An `ask` never pays. It sends the Tamil prompt with a voice-note reply option. The classifier output decides only where the case goes next: `flood_closure` goes to File (with the human adjuster), and `leave`, `illness`, `qr_switch` or `other` go to `human_review` or close with no claim. A label never changes an amount.

## The simulated street

- **Name:** "Panagal Park Road (simulated)". Coordinates 13.04 N, 80.25 E (the Open-Meteo cell used on the deck).
- **Period:** 24 Sep 2026 to 22 Oct 2026, hourly, 07:00 to 22:00 IST.
- **Seed:** 2026. Output must be byte-identical across runs.

| # | Shop | Owner | Behaviour |
|---|---|---|---|
| 1 | Flower stall | Selvi | Hero shop. Normal rhythm, drops on 21 and 22 Oct. |
| 2 | Tea stall | Kumar | Normal, drops in the flood |
| 3 | Pharmacy | Ravi | Keeps trading in the flood (thin) |
| 4 | Fruit cart | Lakshmi | Normal, drops in the flood |
| 5 | Tailor | Anwar | Weekly holiday on Mondays (19 Oct is one); still eligible; drops in the flood |
| 6 | Mobile repair | Priya | Normal, drops in the flood |
| 7 | Grocery | Murugan | Keeps trading (thin) |
| 8 | Bakery | Fatima | Weekly holiday on Tuesdays (20 Oct is one); still eligible; drops in the flood |
| 9 | Footwear | Arjun | Normal, drops in the flood |
| 10 | Stationery | Meena | **On leave from 18 Oct** (inactive before the event): must be `ask`, not `file` |
| 11 | Hotel (tiffin) | Babu | Keeps trading (thin) |
| 12 | Saree shop | Kavya | **Moved to another QR on 19 Oct**: must be `ask` and classify `qr_switch` |

The event day is Wednesday 21 Oct 2026; the three days before are Sun 18, Mon 19 and Tue 20 Oct.

Flood day result: 9 shops dropped (1, 2, 4, 5, 6, 8, 9, 10, 12), which meets the quorum. Seven of them are filed (1, 2, 4, 5, 6, 8, 9). Meena and Kavya go to Ask, so the console tells an honest story about the edge cases.

Daily rhythm: two peaks (08:00 to 10:00 and 18:00 to 21:00). Each shop has its own scale: daily median between ₹2,000 and ₹15,000. Payment count follows a Poisson distribution; amounts are log-normal per shop. All names are fictional.

## Files

- `data/street.csv`: `shop_id, ts_hour, n_payments, amount_paise`
- `data/shops.csv`: `shop_id, name, owner, category, lat, lon, plan_active, staging_order_id`
- `data/eval_shopweeks.csv`: 200 rows. `case_id, shop_profile, scenario, true_label, expected_decision`, plus a path to its daily series in `data/eval/`
- Eval scenario mix: 70 normal, 60 flood street, 20 leave (including 5 that start 1 to 3 days before a flood), 15 illness (a lone drop), 15 QR switch, 10 weekly holiday, 10 power cut (quorum met, no rain)
- `data/rain.json`: cached Open-Meteo response (the fixture used offline)

## Metrics

- **False-claim rate** = cases decided `file` whose true label is not `flood_closure`, divided by all cases.
- **Missed-claim rate** = true `flood_closure` cases not decided `file`, divided by true `flood_closure` cases.
- Report both numbers and the confusion matrix. Never tune on the cases you report: split 140 for tuning and 60 held out, and report the held-out numbers.
