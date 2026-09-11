# Origin Logo Assets

Five PNG lockups of the ORIGIN wordmark + icon mark live in this folder. Each is `1500 × 300` px, transparent background (rendered from the source SVGs in the Origin brand folder; upload these PNGs to the PowerPoint plugin). The **wordmark** (the letters) and the **icon mark** (the dot cluster on the left) are colored independently across variants.

Pick by background, not by taste: a logo must contrast with the surface it sits on.

## Dark-on-light (use on LIGHT backgrounds — `#F4F3EF`, white, light cards)
| File | Wordmark | Icon | Appears as | Notes |
|---|---|---|---|---|
| `origin-logo-02.png` | Black `#141712` | Green `#ADFF26` | Lime-green icon + solid black wordmark | **Primary light-mode logo.** Full color. Default for light slides. |
| `origin-logo-01.png` | Black `#141712` | Black `#141712` | Entirely solid black | All-black monochrome. Use when full color is unwanted (one-color print, watermark). |

## Light-on-dark (use on DARK backgrounds — Charcoal `#222F2E`, Logo Black `#141712`)
**Note on `#F9FFEE`:** it is a near-white tint. On a dark slide it reads as crisp off-white; on a white background (e.g. a browser file:// preview) it looks washed-out — like a faint, **half-opacity lime**. That is expected — `04` and `05` are meant for dark surfaces only.

| File | Wordmark | Icon | Appears as | Notes |
|---|---|---|---|---|
| `origin-logo-04.png` | Off-white `#F9FFEE` | Green `#ADFF26` | Solid lime icon + pale/off-white wordmark (looks like half-opacity lime on white) | **Primary dark-mode logo.** Full color. Default for title / section / closing slides. |
| `origin-logo-05.png` | Off-white `#F9FFEE` | Off-white `#F9FFEE` | Entirely pale/off-white (looks like half-opacity lime on white) | All off-white monochrome. Use when full color is unwanted. |
| `origin-logo-03.png` | Green `#ADFF26` | Green `#ADFF26` | Entirely solid lime green (icon + wordmark) | All-green monochrome. High-impact accent on dark; use sparingly — lower-contrast wordmark, avoid at small sizes. |

## Quick rule
- **Light slide → `origin-logo-02.png`** (full color) or `origin-logo-01.png` (mono).
- **Dark slide → `origin-logo-04.png`** (full color) or `origin-logo-05.png` (mono).
- Never put a light-on-dark variant on a light background, or vice versa — the wordmark disappears.
- The icon mark is bright green `#ADFF26` in the full-color variants; this works on both light and dark, but the **wordmark** is what determines readability, so choose by the wordmark color.

## Paths (co-located in this folder)
```
./origin-logo-01.png   (mono black,        light bg)
./origin-logo-02.png   (black + green,     light bg — PRIMARY)
./origin-logo-03.png   (mono green,        dark bg)
./origin-logo-04.png   (white + green,     dark bg — PRIMARY)
./origin-logo-05.png   (mono near-white,   dark bg)
```

## Sizing & placement (ties to `pp-style-guide.md`)
- Maintain the native 5:1 aspect ratio — never stretch. Scale by width.
- Content slide (light): bottom-right, width ≈ 144 pt → `origin-logo-02.png`.
- Title / section / closing slide (dark): top-left of the dark area, width ≈ 200 pt → `origin-logo-04.png`.
- Clear space: keep at least the icon-mark's width of empty space on every side.
- These PNG lockups replace the typed "⬡ ORIGIN" placeholder described in the style guide — prefer the asset whenever the tool can place an image; fall back to typed text only when it cannot.
