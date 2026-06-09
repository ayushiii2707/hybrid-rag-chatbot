# Particle Website Reconstruction

A pixel-faithful reconstruction of a scroll-driven particle animation website from a screen recording. The site features full-screen Three.js particle systems that morph through 7 distinct shapes as the user scrolls, with content sections fading in at exact scroll positions.

## Run & Operate

- `pnpm --filter @workspace/particle-site run dev` — run the frontend (port auto-assigned)
- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- Frontend: React + Vite + Three.js + React Three Fiber
- No database needed (frontend-only experience)
- Animation: Custom scroll-driven particle morphing

## Where things live

- `artifacts/particle-site/src/components/ThreeScene.tsx` — Three.js canvas with all 7 particle systems
- `artifacts/particle-site/src/lib/particles.ts` — particle shape generators (torus, funnel, DNA, fountain, wave, blackhole, galaxy) + color arrays + lerp utilities
- `artifacts/particle-site/src/components/ContentSections.tsx` — all fixed UI overlays (hero, stat cards, sections 2 & 5)
- `artifacts/particle-site/src/components/Navbar.tsx` — fixed navbar with dynamic section label
- `artifacts/particle-site/src/App.tsx` — scroll progress tracking + section orchestration

## Architecture decisions

- Scroll container is `1000vh` tall; canvas + all content sections are `position: fixed`
- `scrollRef` is a mutable ref (not state) passed to Three.js to avoid React re-renders on every scroll frame
- Particle positions are pre-computed at mount into 7 `Float32Array` shape arrays; `lerpPositions` interpolates between them each frame based on scroll progress
- WebGL availability is checked before mounting the Canvas to avoid errors in headless/GPU-less environments
- Colors are per-particle in a `BufferAttribute` and also interpolated between shapes

## Product

Scroll-driven immersive landing page with 7 animated particle scenes:
1. **Hero ring** — glowing torus (red/white/blue) with hero copy
2. **Funnel** — downward vortex + "21x faster deployment" stat card
3. **DNA/hourglass** — double helix + "68% efficiency gain" stat card
4. **Fountain** — exploding particle burst + "2,400M flow" stat card
5. **Wave landscape** — terrain grid — "Everything revolves around your growth" section
6. **Black hole** — purple particle accretion disk transition
7. **Galaxy spiral** — rotating galaxy — "A universe of possibilities" ecosystem section

Navbar label cycles: STRUCTURE → FLOW → VOYAGE → COSMOS as user scrolls.

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- Three.js's `WebGLRenderer` throws if no GPU is present. Guard with `isWebGLAvailable()` before rendering `<Canvas>`.
- `PARTICLE_COUNT = 28000` — reducing below ~15000 makes the shapes look sparse; increasing above ~40000 may hurt performance on integrated GPUs.
- Scroll progress is `scrollTop / (scrollHeight - clientHeight)` — never use `window.scrollY / document.body.scrollHeight` (off-by-viewport-height).
- React Three Fiber's `useFrame` runs outside React's render cycle; pass data via refs, not props/state.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
