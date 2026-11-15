# DEMO_SCRIPT.md

## Full pitch (about 2:30): story, demo, close

**Story (0:00 to 0:30, cover slide).** "21 October. Over 10 cm of rain overnight in Chennai. Selvi sells flowers at Panagal Park in T. Nagar. That day, her Paytm QR took nothing. Paytm launched cover for days like this, from ₹35 a month. But to claim, she has to prove a lost day she has no paperwork for, and claims are where insurance breaks: nearly 70% of health and general insurance complaints are about claims."

**Insight (0:30 to 0:40).** "Here's what only Paytm can see. When a flood shuts a street, every Soundbox on it goes silent at the same time. That silence is the proof."

**Demo (0:40 to 2:00).** Run the table below from the 0:10 row ("Paytm already sees this. Watch the street.") to the 1:23 row ("...and it missed one closure."). Skip the 0:00 row, because you just told the story, and save the 1:30 line for the close.

**Close (2:00 to 2:30, business model slide).** "It's a feature inside Paytm for Business, not a new app. Paytm gets a reason for merchants to buy cover and renew it, and 1.64 crore merchants already pay Paytm a subscription. Insurers get evidence on every claim, and one shop can't fake a silent street. AI talks to her in Tamil; fixed rules and a human move the money. When the Soundbox goes silent, that is the claim."

**20 seconds, for a quick mentor visit.** "When a flood shuts a street, every Paytm Soundbox on it goes silent at once. Silent Claim turns that silence into a filed insurance claim: it checks the street and the rain, asks the merchant one question in Tamil, and with one tap sends the insurer the proof. No forms."

## The demo (90 seconds)

Laptop on the projector with one tab on `/console`; the links on screen take you to `/adjuster`. Phone on `/merchant` as Selvi. You're solo: keep the phone face up beside the laptop, pick it up at 0:49 and hold it up at 1:14. Target: 90 seconds. Follow the cues in the Do column, not the clock.

| Time | Say | Do |
|---|---|---|
| 0:00 | "21 October. Over 10 cm of rain overnight. Panagal Park in T. Nagar went under water. Selvi sells flowers there. That day, her Paytm QR took nothing." | Console idle, the street trading |
| 0:10 | "Paytm already sees this. Watch the street." | Click **Reset and run the flood**. The clock runs to 22:00 in about 16 s |
| 0:13 | "Silent Claim is a feature inside Paytm for Business, not a new app. It compares every shop with its own last 28 trading days. As payments stop, shutters come down. At day's end, any shop under 30% of its normal day counts as a drop." | Let the shutters fall. If you finish early, stay quiet until the clock passes 22:00 |
| 0:29 | "Nine of twelve shutters down, and Open-Meteo confirms the rain, live. But rain can't say which shops lost money. The payments can." | Decisions land. Point at the road band: 9 of 12 shutters, 27.7 mm, Live |
| 0:39 | "Two shops are different. Meena was on leave, and her voice reply, simulated and labelled, says so: no claim. Kavya switched to another QR, so a person reviews her case. Nothing is paid on a guess." | Point at Meena (**Closed: on leave**), then Kavya (**Asked**; the case file marks her for review) |
| 0:49 | "Selvi gets one question, in Tamil." | Phone: play the prompt |
| 0:57 | "She sees exactly what we share, and with whom. One tap to file, one tap to say no. No forms." | Point at the "What we share" line, then tap **ஆம், பதிவு செய்யுங்கள்** (Yes, file it), or hold the phone out and let a judge tap it. Never hand the phone over. "Claim filed" can take a few seconds; keep talking |
| 1:05 | "The insurer gets an evidence pack: her baseline, the street, the rain and her consent. A human adjuster approves the batch." | In the console's receipt, click **Batch for 21 Oct: ready (7)**. On `/adjuster`, click Selvi's row (PDF preview, 3 s), then **Approve batch (7)** |
| 1:14 | "And Paytm refunds her ₹35 plan fee right away. The refund call is built and signed for Paytm's staging gateway; today it runs simulated, and it's labelled that way. The real money is the insurer's claim for her lost ₹3,201, now filed with proof." | Stay on `/adjuster`. Point at Selvi's line under **Plan-fee refunds**: ₹35, "Simulated: keys pending", refund ID. Hold up the phone: her tracker shows it too |
| 1:23 | "On 60 held-out simulated shop-weeks with leaves, illness and QR switches, it filed 18 claims. 17 were right, and it missed one closure." | Look at the judges, not the screen |
| 1:30 | "When the Soundbox goes silent, that is the claim." | Stop. Wait for questions |

## When something goes off-script

- **Selvi's line reads "Pending at Paytm":** say "Paytm has accepted the refund and is still processing it. The refund ID is real." Keep going.
- **It reads "Monthly cap reached":** say "That's the once-a-month cap at work: Selvi was already refunded in this morning's rehearsal." Keep going, and clear it before the next run (RUNBOOK §10).
- **Staging keys never arrive, or the refund fails:** run with `PAYTM_MODE=pending` and say "The refund call is built and signed against Paytm's staging API. Today it runs simulated, and it's labelled that way." Never call a simulated refund real.
- **Network drops:** keep going. Weather, voice and the classifier fall back to Replay within seconds and their labels change. Selvi's refund doesn't fall back: if it fails, use the line above.
- **Screens pause after Approve batch:** the server waits while Paytm answers. Say "That's Paytm's staging server answering, live," and keep going.
- **Someone taps வேண்டாம் (No) or the voice button on Selvi's phone:** say "She said no, so nothing is filed. That's the point." Then go back to the console and press **Reset and run the flood**.
- **Anything frozen for more than 10 s:** say "Here's a run we recorded earlier," play the backup video and keep narrating. Restart the API in Replay once the judges move on (RUNBOOK §10).
- Never improvise numbers.

## Hard questions (two sentences each)

Learn the first four by heart.

**"How much does Selvi get from the claim?"** The policy sets the amount, not us: we file under the income cover Paytm already sells, and the evidence pack shows the insurer her usual ₹3,201 against ₹0 that day. We chose not to invent a payout formula; the insurer prices and pays.

**"Nine of twelve includes Meena and Kavya. Did the quorum really pass?"** The quorum asks whether the street's payments went quiet, whatever the reason. Leave Meena and Kavya out completely and it's 7 of 10, 70%, still over our 60% line.

**"Health Saathi claims already take a few clicks. What's new?"** She still has to know she's covered, start the claim and prove the loss. We start it for her, and the proof is payment data Paytm already holds.

**"This is an AI track. Why is the AI so small?"** On purpose: AI talks to her in Tamil and understands her reply, but never decides money. An agent still runs every claim end to end, from the street going quiet to the refund.

**"Your data is generated. What does 17 of 18 prove?"** That the rules do what we designed on held-out hard cases we didn't tune on. Real-world accuracy needs Paytm's own payments for 21 Oct, a query Paytm can run and we can't.

**"Floods last days. What happens on day two?"** Day one files the claim. On day two the day before was already a drop, so she gets a voice question instead of one tap; in production a multi-day flood should be one event and one consent.

**"Isn't refunding the plan fee a premium rebate?"** We haven't had legal review, and it's a fair flag. If compliance says it is, the same ₹35 goes out as a Paytm goodwill credit or we drop it; filing the claim is the product.

**"Who underwrites this, and is the cover still sold?"** Paytm launched Health Saathi in July 2024 at ₹35 a month with income cover for floods, fires and strikes, and we couldn't confirm it's still sold. Silent Claim works with any merchant income cover Paytm distributes; the insurer underwrites.

**"How accurate is the Tamil sorting on real voices?"** We tested on a handful of Tamil samples, and a misread can't pay anyone: anything unclear goes to a person. A native-speaker test set is the first thing we'd build.

**"What about new or cash-heavy shops?"** A shop with under 14 trading days is always asked, never auto-filed, because it has no baseline yet. We only see what the QR sees, which is also why the cover gives merchants a reason to keep payments on Paytm.

**"Can she withdraw consent or appeal?"** She can say no on the same screen. Withdrawals and appeals belong in the insurer's claim system, which is the source of truth in production.

**"What's next?"** The same silent-day signal can pause the daily repayment on a Paytm merchant loan, the lending half of this track. And the Soundbox itself can ask her the question out loud.

**"What if a merchant takes a month's leave?"** One silent shop never files: a claim needs most of the street to go quiet in real rain. A shop that was already closed before the rain is asked, not paid, and when it reopens it's compared with its last 28 trading days, not with the zeros.

**"Couldn't a shop fake a drop to get paid?"** Going quiet costs them a day's sales, and it still pays nothing unless most of the street goes quiet in real rain. A human adjuster approves every batch, and the only automatic money is a ₹35 fee refund, at most once a month.

**"₹35 is tiny. Why does it matter?"** The ₹35 is Paytm's same-day goodwill, not the claim. The real money is the insurer's claim for her lost day, ₹3,201 here: her policy sets the payout, and we file the claim for her with proof and one tap.

**"Why not use weather alone, like parametric cover?"** Weather says it rained; payments say which shops actually lost money. Our 15 mm rain gate only confirms the rain, and the grid's 28 mm on 21 Oct was far below the 10 cm the city measured, so grid rainfall also understates a street-level flood.

**"What if the flood falls on her weekly day off?"** Then she wasn't going to trade anyway, so nothing is filed and she isn't asked. The rules spot each shop's weekly day off from its own payment history.

**"What happens to Meena and Kavya?"** They answer by voice, and the reply is transcribed and sorted into one of five labels. A flood closure files a claim and leave closes it; anything else, like Kavya's QR switch, goes to a person, and nothing is paid on a guess.

**"Can we try to fool it?"** Please do: open `/lab`, move the sliders or pick a preset, and it runs the same rules live without touching the demo data. (Click **Console** at the top, then **Try to fool it**, and hand over the laptop.)

**"Would Paytm share this data with insurers?"** It doesn't need to share raw transactions. Paytm already distributes the insurance, and it sends the insurer only the evidence pack, with the merchant's consent.

**"What is real and what is simulated?"** Real: the rainfall data, the Tamil voice and transcription, the classifier, the rules, the evidence PDF and Selvi's tap. Simulated and labelled: the shops' payment history, the other six taps, Meena's and Kavya's voice replies, all seven ₹35 refunds, the insurer's intake and the claim payout.

**"Why isn't the refund live?"** Our Paytm staging test account returned a system error this morning, and Paytm's team at the venue advised us to move on. The refund client is built and checksum-signed for the staging API, and all four endpoints answered our probe, so going live is a credentials switch, not a rebuild.

**"Where do the rules fail?"** Two places, both in our own eval. A shop that switches to another QR on the flood day itself looks like a closed shop, which is why every claim needs the merchant's consent and a human adjuster. A shop that keeps more than 30% of its sales during a flood isn't filed; in production it would get the same Tamil question.

**"How does Paytm make money?"** Distribution income on cover that merchants renew because it pays, plus merchants staying on Paytm payments and Soundbox. Financial services revenue was ₹912 crore in July to September 2026, up 49%, and 1.64 crore merchants already pay Paytm a subscription that this cover can be added to.

**"Who decides the payout, the AI?"** No. The LLM only sorts free-text replies into five labels. Fixed, tested rules set eligibility and the amount, and a human approves.

**"What would production need?"** Authentication, encryption at rest, IRDAI-compliant consent records, the insurer's own claim system as the source of truth, and data-sharing agreements. We left those out of the demo on purpose.

**"Why only Tamil?"** Chennai first. The prompt is one short template per language and Sarvam's voice models cover the major Indian languages, so a new language is a translation, not a rebuild.
