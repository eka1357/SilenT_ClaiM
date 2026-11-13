# DESIGN_SYSTEM.md

## Direction: "the street, the shutter, the receipt"

Everything on screen comes from Selvi's world, not from a template. The street is drawn as a street: two rows of shopfronts facing each other across a road. A shop that stops taking payments pulls its shutter down. Proof and money are shown as printed receipts. Type comes from Indian shop signage: condensed, bold and plain.

Two surfaces, one system. The **console** (Paytm ops and the judges) is ink-dark and calm. The **merchant screen** is warm paper in a phone frame, Tamil first, with one decision per screen. Marigold, the flower Selvi sells, is the accent in both.

Principles, in order:

1. **Calm until something happens.** Movement and colour are spent only on state changes: a shutter coming down, a decision, consent, money back.
2. **Show the agent's work in plain words.** Every step appears as a line in a case file, with a Live or Replay label. No terminal look.
3. **Honest labels.** "Simulated", "Live" and "Replay" are part of the design.
4. **One decision per merchant screen.** Selvi never sees a form.
5. **Nothing that reads as AI-template.** The anti-pattern table at the end of this file is binding.

## What we took from your references

| Reference | What we use |
|---|---|
| **manus.im** | An agent's live step list where each step expands to show what it did. We render it as a case file, not a chat or terminal |
| **bklit.com** | Compact live visuals: sparklines and heat rows. We draw them in SVG ourselves (no d3, no chart library) |
| **ui.watermelon.sh** | Dashboard layout structure on shadcn/ui, as a reference only |
| **21st.dev** | Browse only if we need a primitive shadcn lacks. Restyle anything we take |
| **reactbits.dev** | Its `CountUp` idea for the refund. Write it in about 20 lines with `motion`'s `animate()` instead of adding a package |
| **skiper-ui.com** | Its "Dynamic island" idea for the phone's status pill (`PhoneStatusPill`), rebuilt with `motion` layout animations |
| **screensdesign.com** | Mobile consent and receipt screens, as a reference for the merchant flow |
| **realtimecolors.com** | A quick preview of the palette below on real UI. Contrast is already computed |
| **motion.dev** | Our only animation library (`motion/react`) |

Not used: GSAP (it overlaps with `motion`), Lenis (smooth scroll hurts keyboard and screen-reader users in an app with scrolling panels), Barba.js (we are a single-page app), Jitter (optional, only for a pitch video opener), Unsection and Toolfolio (there is no landing page).

## Tokens (`web/src/styles/tokens.css`, Tailwind v4 `@theme`)

### Colour (unchanged from the deck)

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `--ink` | `#10161D` | Console background; text on paper | 16.3:1 vs paper |
| `--ink-2` | `#1A222C` | Console panels | |
| `--ink-3` | `#232D39` | Raised rows, hover, skeletons | |
| `--line-dark` | `#2A3540` | Hairlines on dark | decorative |
| `--paper` | `#F6F2EA` | Merchant background, receipts | |
| `--card` | `#FFFDF8` | Raised paper | |
| `--line` | `#D9D0BE` | Hairlines on paper | decorative |
| `--text-dark-1` | `#F6F2EA` | Primary text on dark | 16.3:1 |
| `--text-dark-2` | `#B9C4CC` | Secondary text on dark | 10.3:1 (7.9:1 on ink-3) |
| `--text-dark-3` | `#8A97A3` | Meta text on dark | 6.1:1 (4.7:1 on ink-3) |
| `--text-1` | `#10161D` | Primary text on paper | 16.3:1 |
| `--text-2` | `#3F4853` | Body text on paper | 8.3:1 |
| `--text-3` | `#5E6772` | Meta text on paper | 5.1:1 |
| `--marigold` | `#F0A23B` | The one accent: event marker, primary button, focus ring on dark. Ink text on it | 8.6:1 on ink |
| `--rust` | `#A54A06` | Accent text and focus ring on paper | 5.3:1 on paper |
| `--live` | `#5DB8C6` dark / `#0F6E7C` paper | "Live" label | 7.0 / 5.3:1 |
| `--ok` | `#7BC99A` dark / `#2F6B45` paper | Filed, approved, refunded | 9.2 / 5.7:1 |
| `--danger` | `#F08A73` dark / `#B42318` paper | Errors | 7.4 / 5.9:1 |

Rules: no pure white or black, no gradients anywhere, no transparency effects. Status colours appear only on status, always next to a word. Marigold is never small text on paper (1.9:1); use rust there.

### Type

One family for both scripts: **Anek Tamil** by Ek Type, an Indian foundry. It draws Tamil and Latin as one design, so Selvi's Tamil prompt and the English console share one voice. Its width axis gives us condensed signage-style headings and normal-width body text from the same family. **IBM Plex Mono** is used for figures that change live, IDs and receipts.

Google Fonts link (one link, loaded in `index.html`):
`https://fonts.googleapis.com/css2?family=Anek+Tamil:wdth,wght@75..125,100..800&family=IBM+Plex+Mono:wght@400;500&display=swap`

The rupee sign (₹) is in Anek's latin-ext subset, which Google Fonts loads automatically. Do not restrict subsets with `&text=` or `&subset=`.

| Role | Face and settings | Size / line-height | Use |
|---|---|---|---|
| Sign | Anek Tamil, `font-stretch: 75%`, 700, uppercase, +0.5 px tracking | 56/56 | Product name in the top bar; the street name on the road |
| Heading | Anek Tamil, `font-stretch: 87.5%`, 600 | 28/32, 20/24 | Panel titles, sentence case |
| Body | Anek Tamil, 100% width, 400 | 16/24 | Default |
| Small | Anek Tamil, 100% width, 400 or 500 | 14/20 | Meta and table cells; minimum size in the app |
| Tamil | Anek Tamil, 400 or 600 | 22/36 on the merchant screen, 16/26 in the console | Always `lang="ta"` |
| Figures | IBM Plex Mono, 400 or 500 | 14/24 in the receipt, 13/20 for IDs | Receipts, timestamps, IDs, live counters |

Numbers in tables use `font-variant-numeric: tabular-nums` (Anek supports `tnum`). Never use a serif or an italic anywhere in the app.

### Space, shape, depth

- **Spacing:** a 4 px scale only: 4, 8, 12, 16, 24, 32, 48. Panel padding is 24. No other values.
- **Radius:** 2 px for labels, 4 px for buttons and inputs, 6 px for shop tiles and panels. The phone frame is the one exception (44 px), because phones are round.
- **Depth:** 1 px hairlines only. **No drop shadows**, including on the phone frame (use a 10 px `--ink-3` bezel instead).

### Glyphs (no icon library)

About 12 custom SVG glyphs in `web/src/components/glyphs/`, drawn on a 20 px grid with a 1.75 px stroke and square caps: play, pause, mic, check, alert, copy, open-external, chevron, close, rain drop, shutter, receipt. A glyph appears only where it carries meaning, and always beside a word or with an `aria-label`. Do not import `lucide-react` in our own components; shadcn primitives may keep their internal chevron and close icons. Never use a sparkle to mean "AI".

## Layouts

**`/console` at 1440 × 900 (the demo target).** A 72 px top bar: "SILENT CLAIM" in the Sign style, the scenario clock in mono, integration labels (Open-Meteo, Sarvam, LLM, Paytm staging, each "Live", "Replay" or "Down"), and one primary button: "Reset and run the flood". Below it is a two-column grid, `1fr 360px`:

- **Street (left, top, about 380 px tall):** shops 1 to 6 in the top row, a road band, shops 7 to 12 in the bottom row, each shopfront 160 × 120. The road band carries the street name in the Sign style, the date, the rain reading with its source and label, and the quorum ("9 of 12 shutters down"). Each shopfront shows the shop name, the owner, today's sparkline and a status word: "Trading", "Shutter down", "Asked", "Filed" or "Closed: on leave".
- **Case file (left, below the street, fills the rest):** the agent's steps, newest on top, grouped by shop. Each line shows the time in mono, a plain title ("Checked rain for Panagal Park Road"), a one-line result and a Live or Replay label. "Details" opens a paper drawer with the request and response JSON in mono. Do not style it as a terminal: no black box, no green text and no window dots.
- **Receipt (right, full height):** a paper slip on the ink background. Lines are written in mono with dotted leaders: "Forms filled ........ 0", "Taps ........ 1", "Time to file ........ 00:14", "Claims right (eval) ........ [M] of [N]", "Closures missed (eval) ........ [K] of [F]". Below a torn-edge rule come the batch line ("Batch of 7 ready: open adjuster view") and the refund lines as they print.

From 768 to 1279 px, the receipt moves below the case file. Below 768 px everything is one column (street, receipt, case file), and the street wraps to rows of 3.

**`/merchant`:** a 390 × 844 phone frame centred on ink, with paper inside. Screens:
1. **Listening:** "Your shop is covered" and the plan name.
2. **Ask:** play the voice prompt; the Tamil text large and the English gloss small; a "What we share" line (the shop's daily totals for 28 days, the street count and the rainfall, sent only to the insurer for this claim) with a "Details" sheet; the "ஆம், பதிவு செய்யுங்கள்" (Yes, file it) button; and a smaller "Reply by voice" button.
3. **Filed:** a check, "Claim filed" and "Forms filled: 0".
4. **Money back:** a receipt with "₹35 returned" and the Paytm staging refund ID.

Under the frame, a caption reads "Concept: inside Paytm for Business". On a real phone the frame drops away and the screen fills the viewport.

**`/adjuster`:** paper background. A table of the batch (shop, owner, drop %, quorum, rain, consent time, evidence and rules version), an evidence PDF preview pane, and one primary button: "Approve batch (7)".

**`/privacy`:** one short page in plain words: synthetic data only; what is shared, with whom and why; how consent works; and that this is a demo, not a live service.

## Components

Generate these shadcn primitives, then restyle them with our tokens (radius, colours, fonts and focus rings; remove the default `shadow-sm`, `rounded-md` and zinc greys): `button`, `table`, `tooltip`, `dialog`, `sheet`, `separator`, `skeleton`, `sonner`.

Ours (one file each, typed props, all shown on a `/dev/kit` page):

| Component | Notes |
|---|---|
| `StateLabel` | `live`, `replay`, `simulated`, `filed` or `error`: a 6 px square marker plus the word, in 12/16 caps. Not a pill |
| `Shopfront` | Name, owner, `Sparkline` and status word; the shutter overlay; `aria-live="polite"` on the status word only |
| `Shutter` | SVG slats that cover the top 60% of the tile; the name stays readable |
| `Sparkline` | 24 hourly points as an SVG path, 1.5 px stroke, no axes, the last point a dot |
| `RoadBand` | Street name, date, rain reading and quorum |
| `CaseFile` / `CaseLine` | Expandable lines; a status glyph (running, done or error) beside a plain-language title |
| `Receipt` / `ReceiptLine` | Mono lines with dotted leaders; new lines "print" in |
| `PhoneFrame` / `PhoneStatusPill` | The pill morphs between "Listening", "Asking" and "Claim filed" |
| `ConsentButton` | 56 px tall, full width, marigold with ink text |
| `VoicePrompt` | Play or pause, a waveform drawn from the audio's peaks, the duration; Space toggles playback |
| `ShareDisclosure` | The "What we share" line and sheet |

Every loading state uses a static skeleton (an `--ink-3` or `--line` block, no shimmer).

## Motion (`motion/react` only)

Wrap the app in `<MotionConfig reducedMotion="user">`. CSS keyframes are allowed only for the running glyph.

- **Hover:** an instant tone change (120 ms colour transition). No movement, scale, glow or fade on hover.
- **Press:** the background darkens. Only `ConsentButton` also scales to 0.98, because it is pressed on a phone.
- **Lists:** a new case line or receipt line appears with an 8 px reveal over 200 ms.
- **No** scroll-triggered effects, cursor-following effects, looping decoration or animated arrows.

The three signature moments (state changes only, 500 to 700 ms, each plays once):
1. **Shutters come down.** Each shop's shutter drops at the simulated hour its payments actually stop, not on a fake stagger. When the quorum is met, the road band's count updates and the rain reading appears with its source.
2. **One tap.** The consent button fills, shows a check, and the phone pill changes to "Claim filed".
3. **The receipt prints.** When Paytm's staging status returns, the refund line extends down the receipt and the amount counts from ₹0 to ₹35 in mono.

With reduced motion, all three become instant state changes carrying the same information.

## Writing on screen

Plain words: "Checked rain", not "Invoked weather tool". The merchant screen is Tamil first, with an English gloss, and never says "parametric", "trigger" or "claim ID".

Banned in all UI copy: em dashes, "It's not X, it's Y" constructions, and the words seamless, revolutionise, empower, leverage, unlock, supercharge, next-gen, cutting-edge, AI-powered (the track name on the title slide is the only exception), magic and effortless.

Use Indian number grouping via `Intl.NumberFormat('en-IN')`.

## Accessibility (all required)

Contrast as in the table. Keyboard order follows the visual order; Enter and Space activate; Escape closes sheets. Focus is always visible: a 2 px ring with a 2 px offset (marigold on dark, rust on paper). Every glyph-only button has a name. `lang="ta"` on Tamil. Audio always has its text on screen. Touch targets are at least 44 px (56 px for consent). Nothing flashes more than three times a second. The demo path works at 200% zoom.

## Anti-patterns (binding)

Each tell from the "vibecoded" lists, and our rule for it:

| Tell | Our rule |
|---|---|
| Purple-to-blue or harsh gradients, gradient text, grain over a gradient, radial orbs, rainbow colouring, neon, basic pastels, purple and black | A flat ink, paper and marigold palette. No gradients. Status colours only on status |
| Glassmorphism, liquid glass | Solid surfaces only |
| Drop shadows | None. 1 px hairlines |
| Soft corner radius | 2, 4 and 6 px. Only the phone frame is round |
| Inter, Geist or Space Grotesk everywhere; Space Grotesk with Instrument Serif; serif italic accents | Anek Tamil plus IBM Plex Mono. No serif or italic in the app |
| Lucide icons everywhere, sparkle icons, animated arrows, checkmark bullets, emoji | About 12 custom glyphs, only where they carry meaning. No bullet glyphs. No emoji |
| 3 feature cards or 3 icon boxes in a row, bento grids, coloured border or left-stripe cards | The street is drawn as a street, metrics are a receipt, and the batch is a table |
| A badge above the headline | Plain headings. Labels only for state |
| Untouched shadcn UI | Every primitive restyled with our tokens |
| A terminal window | The agent's work is a case file in plain words |
| Fade-in on scroll, a cursor-following beam, buttons that fade on hover, hover animations | No scroll or cursor effects. Hover is an instant tone change. Motion only on state change |
| Dot grids | No decorative dots. A dot means only "no payments that hour" |
| A pure white background, low-contrast dark mode | Toned paper and ink, and every text colour at 4.5:1 or more |
| Inconsistent spacing | The 4 px scale tokens only |
| Em dashes, "it's not X, it's Y", generic buzzword copy | Banned (see "Writing on screen") |
| No skeleton loaders | Static skeletons on every loading state |
| Fake testimonials, 3 pricing tiers, no real product demo | None of the first two. The demo itself is the product |
| No terms of service, no privacy policy | No terms needed for a demo. A `/privacy` page and the consent disclosure, because consent is the product |

## Acceptance criteria

1. `pnpm lint:design` passes. It is a script in `web/scripts/design-lint.mjs` that fails the build if `web/src` (outside `components/ui/` and `styles/tokens.css`) contains: a raw 6-digit hex value, `gradient`, `backdrop-blur`, `shadow-`, `rounded-xl`/`rounded-2xl`/`rounded-3xl`, an import from `lucide-react`, the em dash character (U+2014), or any banned word.
2. Lighthouse accessibility is at least 95 on `/console`, `/merchant`, `/adjuster` and `/privacy`.
3. axe-core in the Playwright run finds zero serious or critical issues.
4. With `prefers-reduced-motion: reduce`, the demo path completes and nothing moves.
5. The console at 1440 × 900 shows the street, the case file and the receipt without scrolling the page.
6. The merchant screen at 360 × 740 shows the Tamil prompt, the share line and the consent button without scrolling.
