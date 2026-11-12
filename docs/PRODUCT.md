# PRODUCT.md

## One line

When a merchant's Paytm payments stop because their street is flooded, Silent Claim files their income-protection claim for them: one Tamil question, one tap, no forms.

## The problem

On 21 October 2026, Chennai had more than 10 cm of rain overnight and Panagal Park in T. Nagar was under water (Corporation Commissioner, reported by Mathrubhumi). A street shop like Selvi's flower stall takes no payments that day. She has no paperwork to prove a day without sales.

Cover already exists. In July 2024, Paytm launched Health Saathi for merchants from ₹35 a month, with income protection for business interruptions from floods, fires and strikes. But a claim still starts with the merchant: she has to know she can claim, find the form and prove the loss. Nearly 70% of health and general insurance complaints are about claims (Mint, June 2026). Chennai's MSMEs lost more than ₹7,000 crore in Cyclone Michaung (WRI India, 2024).

## The insight

Paytm can see income stop. A weather feed only sees a grid cell, and an insurer only sees a form. Paytm sees each shop's payments stop, street by street. The loss is the trigger, Paytm's own records are the proof, and one shop cannot fake a silent street.

Note: we could not confirm that Health Saathi is still sold today. The product works for any merchant income cover sold through Paytm.

## Users

| User | Need | What they see |
|---|---|---|
| **Merchant** (Selvi: flower stall, Tamil speaker, uses her phone and Soundbox) | Get paid for a flooded day without paperwork | One Tamil voice note and one button |
| **Insurer adjuster** | Approve real claims fast and catch false ones | A batch of claims with evidence attached, approved in one action |
| **Paytm** (product and ops) | Plan renewals, merchant retention, fewer support calls | Console: street status, agent trace, metrics |

## The loop

| Step | What happens | Real or simulated on finals day |
|---|---|---|
| 1 Sense | Each shop is compared with its own last 28 trading days | Real detector on simulated payment history |
| 2 Confirm | At least 60% of the street dropped and rainfall is at least 15 mm: a street event. Only one shop quiet: ask first. | Real Open-Meteo rainfall, real rules |
| 3 Ask | A Tamil voice prompt and a one-tap "Yes, file it". Odd cases reply by voice note, and AI sorts them by cause. | Real Sarvam speech and LLM classifier |
| 4 File | An evidence pack (PDF) goes to the insurer queue. A human adjuster approves the batch. | Real PDF; simulated insurer intake |
| 5 Pay back | Paytm refunds that month's ₹35 plan fee at once. The insurer pays the claim. | Real Paytm staging refund; simulated claim payout |

## User stories and acceptance criteria

**US1: Detect a street event.** As Paytm, I want shops that went quiet together, on a day with heavy rain, flagged automatically.
- Given the simulated street on 21 Oct, the detector marks 9 of 12 shops as dropped, and the street as a street event.
- Rainfall shown is the real Open-Meteo value, with a "Live" label (or "Replay" offline).
- From pressing "Run the flood" to the first shop flagged takes 5 seconds or less in demo mode.

**US2: Ask in Tamil, file on one tap.** As Selvi, I want to hear what happened and say yes once.
- The merchant screen plays a real Sarvam Tamil voice prompt and shows the Tamil text with an English gloss.
- Before the button, a "What we share" line says exactly what goes to the insurer (her shop's daily totals for 28 days, the street count and the rainfall), to whom and why, with a "Details" sheet. Consent means nothing if she can't see what she agrees to.
- The "Yes, file it" button is at least 56 px tall, works by keyboard, and confirms within 300 ms.
- After the tap, the claim status shows "Filed" and the forms counter reads 0.

**US3: Sort the odd cases.** As Paytm, I want shops that went quiet for other reasons asked, not paid.
- A voice note saying "I'm on leave this month" is classified `leave`, and no claim is filed.
- A shop that was already inactive for the 3 days before the event goes to Ask, not File.
- A QR switch (payments moved to another provider) is classified `qr_switch` and sent to a human.

**US4: Evidence pack and batch approval.** As an adjuster, I want evidence I can trust and one action to approve.
- Each claim gets a PDF with the shop's baseline vs event-day income, the street quorum, rainfall and its source, the merchant's consent timestamp, and the rule version.
- The adjuster sees all claims in a batch and approves with one button. Every decision is logged.

**US5: Pay back now.** As Selvi, I want something back the same day.
- After approval, a real Paytm staging refund of ₹35 runs against that shop's staging plan-fee payment.
- The UI shows Paytm's refund status (Live) and an idempotent refund ID. Running it twice never refunds twice.

**US6: Prove it works.** As a judge, I want a number, not a promise.
- `scripts/eval.py` reports the false-claim rate and missed-claim rate on 200 labelled simulated shop-weeks.
- The console shows these two numbers with "Simulated eval" beside them.
- Targets: false-claim rate of 5% or less, missed-claim rate of 10% or less. Report the real numbers either way.

## On-screen metrics

Forms filled: 0. Taps: 1. Time from event to filed claim. False-claim rate (eval). Refund status (Paytm staging).

## Not building (binding)

No new insurance product or pricing. No real merchant data. No production Paytm calls. No Soundbox firmware. No login or user accounts (the demo uses fixed personas), so no passwords, sessions, email or account deletion. No terms of service; a short `/privacy` page explains the synthetic data and the consent. No languages beyond Tamil and English. No mobile app: the merchant view is a responsive web screen in a phone frame. No landing page.

## Success on finals day

The judges watch a 90-second demo with no failures, see at least three real calls (rainfall, Tamil voice, Paytm staging refund), and hear one honest number from the eval.
