---
trigger: glob
globs: web/**
---

# Frontend rules

- Read `docs/DESIGN_SYSTEM.md` before touching UI, including its anti-pattern table. Use tokens from `web/src/styles/tokens.css` only; no raw hex in components.
- Stack: Vite, React, TypeScript strict, Tailwind v4, shadcn/ui (restyled with our tokens), `motion/react`. Ask before adding any package, and record it in `docs/DECISIONS.md`.
- Fonts: Anek Tamil (all text, Tamil and Latin) and IBM Plex Mono (figures, IDs, receipts). No Inter, Geist, Space Grotesk, serif or italic.
- Icons: our own glyphs in `src/components/glyphs/`. Never import `lucide-react` outside `components/ui/`. No emoji, no sparkle icons.
- Shape: radius 2, 4 or 6 px (the phone frame is the only exception); 1 px hairlines; no shadows, gradients, blur or glass.
- Motion: wrap the app in `<MotionConfig reducedMotion="user">`. Hover is an instant tone change only. Motion only on state changes; the three signature moments are the only long animations.
- All server access goes through `src/lib/api.ts` and `src/lib/stream.ts` (SSE with auto-reconnect). No keys in the frontend.
- Every simulated surface shows `<StateLabel kind="simulated" />`; every integration result shows `live` or `replay`. Loading states use static skeletons.
- Tamil text gets `lang="ta"`. Glyph-only buttons need `aria-label`. Focus rings must be visible.
- Never copy Paytm's logo, colours or screens. The merchant view is captioned "Concept: inside Paytm for Business".
- Before saying done: `pnpm typecheck && pnpm lint && pnpm lint:design && pnpm build` pass, and the screen works at 1440 × 900 and 360 × 740.
