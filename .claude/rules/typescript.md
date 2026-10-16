---
paths:
  - "web/**"
---

# Frontend (React, TypeScript, Vite)

- Strict TypeScript. `npm --prefix web run typecheck` must pass. No `any`
  without a comment saying why.
- The UI never computes dates, windows, KPIs or business days. It renders
  what the API returns, including the window and comparison dates.
- Filters live in the URL search params. Reset restores the defaults
  (Summit Sky Deck, Last Week, Compare On, Prior Period).
- A null value renders "No data", never 0 or an empty bar.
- Brand: Nicky Sans via @font-face from the brand fonts, no fallback web
  font. Logo `<img>` with its intrinsic aspect ratio, the black file on
  light, the white file on dark, no CSS filters or transforms on it. Chrome
  is black, white and grays. #FFC000 only inside charts and data marks.
- Thin 1px borders, no box shadows, dense spacing. Status always pairs color
  with a glyph or text.
- Light mode is the default. Theme colors are CSS variables.
