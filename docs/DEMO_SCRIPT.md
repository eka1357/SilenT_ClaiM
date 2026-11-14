# DEMO_SCRIPT.md

Laptop on the projector with two tabs: tab 1 `/console`, tab 2 `/adjuster` (Ctrl+Tab switches). Phone on `/merchant` as Selvi. One person talks and drives the laptop; the other holds the phone and handles anything that breaks. Target: 90 seconds. Follow the cues in the Do column, not the clock.

| Time | Say | Do |
|---|---|---|
| 0:00 | "21 October. Over 10 cm of rain overnight. Panagal Park in T. Nagar went under water. Selvi sells flowers there. That day, her Paytm QR took nothing." | Console idle, the street trading |
| 0:10 | "Paytm already sees this. Watch the street." | Click **Reset and run the flood**. The clock runs to 22:00 in about 16 s |
| 0:13 | "Silent Claim is a feature inside Paytm for Business, not a new app. It compares every shop with its own last 28 trading days. When a shop takes less than 30% of a normal day, its shutter comes down." | Let the shutters fall. If you finish early, stay quiet until the clock passes 22:00 |
| 0:29 | "Nine of twelve shutters down, and Open-Meteo confirms the rain, live. One quiet shop proves nothing. A quiet street in real rain is a claim." | Decisions land. Point at the road band (quorum and rain, labelled Live) |
| 0:39 | "Two shops are different. Meena was on leave before the rain. Kavya moved to another QR. They get a question first, and nothing is filed until they answer." | Point at the two **Asked** shopfronts |
| 0:49 | "Selvi gets one question, in Tamil." | Phone: play the prompt |
| 0:57 | "She sees exactly what we share, and with whom. One tap to file, one tap to say no. No forms." | Point at the "What we share" line, then tap **ஆம், பதிவு செய்யுங்கள்** (Yes, file it). Or hand the phone to a judge: "You're Selvi. Tap yes." The pill shows "Claim filed" |
| 1:05 | "The insurer gets an evidence pack: her baseline, the street, the rain and her consent. A human adjuster approves the batch." | Ctrl+Tab to `/adjuster`. Click Selvi's row (PDF preview, 3 s), then **Approve batch (7)** |
| 1:14 | "And Paytm refunds this month's ₹35 plan fee right away. Selvi's is a real refund on Paytm's staging gateway. The other six are simulated, and labelled that way." | Ctrl+Tab back to `/console`. The receipt prints Selvi's line: ₹35, Live, refund ID. Hold up the phone: her tracker shows it too |
| 1:23 | "On 60 held-out simulated shop-weeks with leaves, illness and QR switches, it filed 18 claims, and 17 were right." | Look at the judges, not the screen |
| 1:30 | "When the Soundbox goes silent, that is the claim." | Stop. Wait for questions |

## When something goes off-script

- **Selvi's line reads "Pending at Paytm":** say "Paytm has accepted the refund and is still processing it. The refund ID is real." Keep going.
- **It reads "Monthly cap reached":** say "That's the once-a-month cap at work: Selvi was already refunded in this morning's rehearsal." Keep going, and clear it before the next run (RUNBOOK §10).
- **Staging keys never arrive, or the refund fails:** run with `PAYTM_MODE=pending` and say "The refund call is built and signed against Paytm's staging API. Today it runs simulated, and it's labelled that way." Never call a simulated refund real.
- **Network drops:** keep going. Calls fall back to Replay after 4 s and the labels change to Replay.
- **Anything frozen for more than 10 s:** say "Here's the run we recorded this morning," play the backup video and keep narrating. The teammate restarts the API in Replay (RUNBOOK §10).
- Never improvise numbers.

## Hard questions (two sentences each)

**"What if a merchant takes a month's leave?"** One silent shop never files: a claim needs most of the street to go quiet in real rain. A shop that was already closed before the rain is asked, not paid, and when it reopens it's compared with its last 28 trading days, not with the zeros.

**"Couldn't a shop fake a drop to get paid?"** Going quiet costs them a day's sales, and it still pays nothing unless most of the street goes quiet in real rain. A human adjuster approves every batch, and the only automatic money is a ₹35 fee refund, at most once a month.

**"₹35 is tiny. Why does it matter?"** The ₹35 is Paytm's same-day goodwill. The real money is the insurer's claim payout, which she would otherwise have to prove with forms; we file it for her with one tap.

**"Why not use weather alone, like parametric cover?"** Weather says it rained; payments say the shop actually lost money. On 21 Oct the weather grid showed about 28 mm while the city reported over 10 cm, so weather alone would have missed it.

**"What if the flood falls on her weekly day off?"** Then she wasn't going to trade anyway, so nothing is filed and she isn't asked. The rules spot each shop's weekly day off from its own payment history.

**"What happens to Meena and Kavya?"** They answer by voice, and the reply is transcribed and sorted into one of five labels. Only a flood closure files a claim; anything else is closed or goes to a human, never paid on a guess.

**"Can we try to fool it?"** Please do: open `/lab`, move the sliders or pick a preset, and it runs the same rules live without touching the demo data. (Open `localhost:5173/lab` in a new tab and hand over the laptop.)

**"Would Paytm share this data with insurers?"** It doesn't need to share raw transactions. Paytm already distributes the insurance, and it sends the insurer only the evidence pack, with the merchant's consent.

**"What is real and what is simulated?"** Real: the rainfall data, the Tamil voice and transcription, the classifier, the rules, the evidence PDF, Selvi's tap and her Paytm staging refund. Simulated and labelled: the shops' payment history, the other six taps and refunds, Meena's and Kavya's voice replies, the insurer's intake and the claim payout.

**"Where do the rules fail?"** Two places, both in our own eval. A shop that switches to another QR on the flood day itself looks like a closed shop, which is why every claim needs the merchant's consent and a human adjuster. A shop that keeps more than 30% of its sales during a flood isn't filed; in production it would get the same Tamil question.

**"How does Paytm make money?"** Distribution income on cover that merchants renew because it pays, plus merchants staying on Paytm payments and Soundbox. Financial services revenue was ₹912 crore in July to September 2026, up 49%, and 1.64 crore merchants already pay Paytm a subscription that this cover can be added to.

**"Who decides the payout, the AI?"** No. The LLM only sorts free-text replies into five labels. Fixed, tested rules set eligibility and the amount, and a human approves.

**"What would production need?"** Authentication, encryption at rest, IRDAI-compliant consent records, the insurer's own claim system as the source of truth, and data-sharing agreements. We left those out of the demo on purpose.

**"Why only Tamil?"** Chennai first. The prompt is one short template per language and Sarvam's voice models cover the major Indian languages, so a new language is a translation, not a rebuild.
