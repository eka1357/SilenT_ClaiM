# DEMO_SCRIPT.md

Laptop on `/console`, a phone (or a second window) on `/merchant`. Rehearse with a timer. Target: 90 seconds.

| Time | Say | Do |
|---|---|---|
| 0:00 | "21 October. Over 10 cm of rain overnight. Panagal Park in T. Nagar is under water. Selvi sells flowers there. That day, her Paytm QR took nothing." | Console idle. The street is trading |
| 0:12 | "Paytm already sees this. Watch the street." | Click **Reset and run the flood**. Shutters come down as each shop's payments stop |
| 0:22 | "Nine of twelve shutters down at once, and the rainfall check is live from Open-Meteo. The whole street lost the day." | Point at the road band (quorum and rain, labelled Live) and the case file |
| 0:32 | "Two shops are different. Meena went on leave three days ago. Kavya moved to another QR. Each gets a question first, and nothing is paid until they answer." | Point at the two "Asked" shopfronts |
| 0:42 | "Selvi gets one question, in Tamil." | Play the prompt on the phone |
| 0:50 | "She sees exactly what we share, and with whom. One tap. No forms." | Point at the "What we share" line, then tap **ஆம், பதிவு செய்யுங்கள்** (Yes, file it). The pill shows "Claim filed" |
| 0:56 | "The insurer gets evidence: her baseline, the street, the rain, her consent, and the rules version. A human approves the batch." | Open the evidence PDF for 3 s, then **Approve batch** |
| 1:08 | "And Paytm gives her this month's fee back right now. This is a real refund on Paytm's staging gateway." | The receipt prints the refund line: ₹35, Live, with the refund ID |
| 1:16 | "On 200 simulated shop-weeks seeded with leaves, illness and QR switches, the false-claim rate is [X]%." | Point at the receipt line |
| 1:24 | "When the Soundbox goes silent, that is the claim." | Stop |

If the staging keys never arrive or the refund fails, say instead: "The refund call is built and signed against Paytm's staging API; today it runs simulated, and it's labelled that way." Never call a simulated refund real.

If anything fails live: say "We recorded this an hour ago", switch to the second running instance with `DEMO_OFFLINE=1` (its labels read Replay), and carry on. Never improvise numbers.

## Hard questions (answer in two sentences)

**"What if a merchant takes a month's leave?"** One silent shop never files. A shop that was already quiet for two of the three days before the event is asked, not paid, and a returning shop is compared with its last 28 trading days, not with zeros.

**"Couldn't a shop fake a drop to get paid?"** Going quiet costs them a day's sales, and it still pays nothing unless most of the street goes quiet with real rain. A human adjuster approves every batch, and the only automatic money is a ₹35 fee refund, capped once a month.

**"Why not use weather alone, like parametric cover?"** Weather says it rained; payments say the shop actually lost money. On 21 Oct the weather grid showed about 28 mm while the city reported over 10 cm, so weather alone would have missed it.

**"Would Paytm share this data with insurers?"** It doesn't need to share raw transactions. Paytm already distributes the insurance, and it sends the insurer only the evidence pack, with the merchant's consent.

**"What is real and what is simulated?"** Real: the rainfall data, the Tamil voice, the classifier, the rules, the evidence PDF and the Paytm staging refund. Simulated and labelled: the shops' payment history, the insurer's intake and the claim payout.

**"How does Paytm make money?"** Distribution income on cover that merchants renew because it pays, plus merchants keeping their payments and Soundbox on Paytm. Financial services distribution revenue was ₹912 crore last quarter, up 49%.

**"Who decides the payout, the AI?"** No. The LLM only sorts free-text replies into five labels. Fixed, tested rules set eligibility and the amount, and a human approves.
