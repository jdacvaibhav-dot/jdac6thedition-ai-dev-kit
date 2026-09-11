# Origin Digital Brand Style Guide

Apply this style to every presentation unless explicitly directed otherwise. The goal is visual consistency: any deck built from an outline plus this guide should look like it came from the same template.

Color values follow the official brand sheet — see [`origin-brand-colors-hex.md`](./origin-brand-colors-hex.md) for the source palette.

## Canvas
- 16:9, **720 × 405 pt**
- Safe content area: 29 pt left/right, 18 pt top, 36 pt bottom (leave room for the footer/logo)
- Two background modes: **Light** (`#F4F3EF`, Gray 100) for content-heavy slides, **Dark** (`#222F2E`, Charcoal) for title, section dividers, and closing slides

## Color Palette

| Role | Hex |
|---|---|
| Logo Green (primary accent) | `#ADFF26` |
| Logo Green @ 30% alpha (oversized numerals on dark) | `#ADFF26` with `alpha="30000"` |
| Charcoal background (dark mode) | `#222F2E` |
| Logo Black — component dark fill (cards, code blocks, tables) **and** primary text on light | `#141712` |
| Closing-slide nav-card fill (lifted charcoal) | `#34433F` |
| Off-white background (light mode) — Gray 100 | `#F4F3EF` |
| Light card / row fill — Gray 300 | `#E3E2D9` |
| White (text on dark, card highlight) | `#FFFFFF` |
| Secondary/muted text on light — Gray 500 | `#77766E` |
| Secondary/muted text on dark | `#9B9B9B` |
| Negative / trade-off / error — Fire | `#FF4B00` |
| Informational — Blue | `#0076FF` |
| Warning / caution — amber (derived; no brand equivalent) | `#F5A623` |

**Contrast rule (critical).** Logo Green `#ADFF26` is a bright lime. It reads cleanly **as a fill, accent strip, or text on a dark surface**, but it is **unreadable as text on light/near-white backgrounds**. Therefore:
- For "green" text on a light slide (headings, identifiers, the wordmark), substitute **Logo Black `#141712`**.
- Filled green elements (tag pills, number squares) take **dark `#141712` text**, never white.
- Green text is only allowed on dark fills (`#141712` / `#222F2E`).

**Accent palette.** For categorical differentiation only, you may use the sanctioned brand accents: **Navy `#2F3060`**, **Purple `#A414C2`**, **Fire `#FF4B00`**, **Blue `#0076FF`**, **Brown `#A66E33`**, and neutral **Green `#DBDF82`**. Use them to distinguish categories (e.g., workstreams, status, data series) — never as decoration. For semantic meaning keep it simple: **green = positive, Fire `#FF4B00` = negative/error, Blue `#0076FF` = informational, amber `#F5A623` = caution.** Do not invent colors outside this list.

## Typography

Font family: **Calibri** throughout. Bold for titles, headers, identifiers, and emphasis; regular for body. Use a monospace-feeling treatment (Calibri bold in green, on a dark fill) for code identifiers — do not switch font families.

| Text role | Size | Weight | Color |
|---|---|---|---|
| Section-divider numeral ("01") | 96 pt | bold | `#ADFF26` @ 30% alpha |
| Section-divider title ("Architecture") | 52 pt | bold | `#FFFFFF` |
| Title-slide main title | 34 pt | bold | `#FFFFFF` |
| Title-slide right-pane heading | 22 pt | bold | `#FFFFFF` |
| Content-slide title | 24 pt | bold | `#141712` |
| TOC heading ("Table of Contents") | 28 pt | bold | `#141712` |
| Card / section heading (within slide) | 13–16 pt | bold | `#141712` on light; `#ADFF26` only on a dark fill |
| Body text | 11–12 pt | regular | `#141712` light / `#FFFFFF` dark |
| Code identifier / monospace label | 11–13 pt | bold | `#ADFF26` (on dark fill only) |
| Breadcrumb ("02 / Backend") | 10 pt | regular | `#77766E` |
| Section-divider sub-topic strip | 14 pt | regular | `#ADFF26` |
| Logo wordmark "⬡ ORIGIN" | 14–20 pt | bold | `#ADFF26` on dark; `#141712` on light |
| Closing footnote / metadata | 10 pt | regular | `#9B9B9B` |

Minimum body size is 11 pt. Do not go below 10 pt for any text, including footnotes.

## Persistent Brand Elements (on every slide)
1. **Left accent strip** — vertical rectangle, `#ADFF26`, 9 pt wide (13 pt on dark slides), full slide height, at `left=0, top=0`. Never omit, never recolor.
2. **ORIGIN wordmark** — "⬡ ORIGIN" in 14 pt bold. Green `#ADFF26` on dark slides, Logo Black `#141712` on light slides. On content slides, place bottom-right (`left≈562, top≈374, width≈144`). On title / section / closing slides, place top-left of the dark area, 20 pt.
3. **Title divider line** — on content slides, a thin horizontal line under the title/breadcrumb at `top≈76`, spanning content width. Color: `#E3E2D9` (light) or `#34433F` (dark).

## Slide Templates

These are composable building blocks. Pick whichever fits each outline item — no required ordering beyond "open with a Title slide and close with a Closing slide." Insert section dividers when the outline groups topics; skip them for short decks.

### Template A — Title Slide (dark, split-pane)
- Full dark `#222F2E` background
- **Left pane** (~302 pt wide): ORIGIN logo top-left (20 pt, green), deck title 34 pt bold white, subtitle 16 pt muted, thin green divider, then 2–3 lines of body context (audience, presenter, scope), and a 12 pt date/metadata line near the bottom.
- **Right pane** (~374 pt wide, starting at `left=324`): section/feature heading 22 pt bold white, optional one-line subtitle, then a 3×2 or 3×3 **tag pill grid** (architectural components, tech stack, agenda preview), followed by 2–4 lines of supporting text separated by thin horizontal lines.

### Template B — Table of Contents (light)
- Light background, "Table of Contents" title 28 pt bold, green underline below
- **2-column grid of section cards.** Each card: light fill `#E3E2D9`, with a dark `#222F2E` square on the left containing the section number ("01") in 24–28 pt bold green. To the right: section name 14 pt bold dark, then a muted gray sub-topic list 10 pt separated by middle dots.
- 4–6 sections fit comfortably. If more than 6, switch to a 3-column grid or split across two TOC slides.

### Template C — Section Divider (dark)
- Full dark `#222F2E` background
- Oversized numeral ("01") at `left=36, top=36`, 96 pt bold, green at 30% alpha (so it reads as a watermark)
- Section title at `left=36, top≈130`, 52 pt bold white
- Sub-topic breadcrumb at `top≈220`, 14 pt green, items joined by ` · ` (middle dot with spaces)
- ORIGIN wordmark bottom-right

### Template D — Content Slide (light, the workhorse)
Light `#F4F3EF` background. Top zone is always: title 24 pt bold at `top=18`, breadcrumb "0N / Section" 10 pt at `top=55`, divider line at `top=76`. Content begins at `top≈85`.

Within the content zone, compose using the **components below**. Common patterns:
- **Two-column grid** (~324 pt each, 14 pt gutter at `left=29` and `left=367`) — use for parallel content: naming convention vs description rules, benefits vs trade-offs, key components vs auth flow.
- **Three-column grid** (~210 pt each, ~14 pt gutter) — use for numbered step cards.
- **Four-column grid** — use for tag/tech-stack chips at the top of a slide.
- **Full-width table** — use for hierarchical lists (service→description, identifier→purpose).
- **Diagram + sidebar** — left two-thirds for boxes-and-lines diagram, right third for a list of related items.

Reserve `top≈374` and below for the footer/logo — do **not** extend content into that band. If content runs past `top≈355`, split the slide.

### Template E — Closing / Thank You (dark)
- Full dark background
- "Thank You!" 36 pt bold white at top-left, with a thin green divider below it
- 1–2 lines of deck metadata ("Weil MCP Platform · Technical Documentation · April 2026") 14 pt, then a sub-line 10 pt muted
- Row of 4–6 **section nav cards** along the bottom (`top≈310`, `height≈36`): dark `#34433F` fill, section number + name in 11 pt, gap of ~10 pt between cards

### Template F — Resource / Links Slide (light, optional)
- Standard content header (title + breadcrumb + divider)
- 2-column bulleted hyperlink list with bold column headers
- Use this for "Helpful Links", "References", "Further Reading"
- Keep the bottom half empty or add a short metadata line; do not stretch links to fill

## Component Library

Reuse these on any content slide. Sizes are starting points — scale to fit content width.

**Card-with-green-tab** (`#141712` fill, 5 pt green top bar OR 4 pt green left bar):
- Use the **top-bar variant** for prominent grid cards (numbered step cards, feature cards): card 216×150 pt, top bar full-width × 5 pt, large green numeral inside.
- Use the **left-bar variant** for compact row items in a list (tools, env vars, code identifiers): row 324×35 pt, left bar 4 pt wide.

**Code / identifier row** (dark `#141712` fill, 4 pt green left bar):
- Green monospace-style identifier 11 pt bold left, white description 11 pt right or below
- Used for tool catalogs, environment variables, configuration keys

**Numbered step card** (three-card row at top of a content slide):
- Card 216×150 pt, dark `#141712` fill, 5 pt green top bar
- Large green numeral (1, 2, 3) 24 pt bold inside, then green bold title 13 pt, muted sub-label 10 pt, body text 11 pt white

**Step row** (numbered list, vertical):
- Row 374×45 pt, dark fill, 26 pt green square on the left holding the number 14 pt bold **dark `#141712`** (the green square is bright — number text must be dark, not white)
- Bold title 12 pt + body 11 pt on the right

**Benefit row / Trade-off row** (two-column list):
- Light row fill: `#F0FBD9` (benefits, pale lime) or `#FFE4D6` (trade-offs, pale fire)
- 4 pt left bar: `#ADFF26` (benefits) or `#FF4B00` (trade-offs)
- Single line of 11 pt body text

**Tag pill** (used on title slide and at the top of tool-detail slides):
- 115×30 pt rounded rectangle
- Two variants: **filled** (green `#ADFF26` fill, **dark `#141712`** bold text) for emphasized tags; **outlined** (dark `#141712` fill, green outline + green bold text) for secondary tags
- 11 pt bold text, centered

**Architecture / diagram boxes**:
- 187×52 pt (compact) or 216×52 pt (wide) rounded rectangle, dark `#141712` fill
- Green bold component name 13 pt on the first line, white description 11 pt on the second
- Connect with 1 pt green lines (`#ADFF26`) using right-angle paths only — no curves, no diagonals

**Footer rule strip** (full-width banner near the bottom):
- 662×45 pt, dark `#222F2E` fill
- Green bold label on the left (e.g., "Standard Verbs:"), middle-dot-separated items in white on the right
- Use for cross-cutting reminders that apply to the whole slide

**Callouts**:
- Amber `#F5A623` left-bar + dark fill for warnings ("⚠ Do NOT use for…")
- Green-tinted bar for tips / key insights
- Always single-line; if longer, promote to a full row

**Tables** (hierarchical lists):
- Alternating row fills: white `#FFFFFF` and `#E3E2D9`
- First row highlighted dark `#222F2E` with green identifier + white description (marks the primary/recommended option)
- Row height 35–45 pt, 11 pt text, left-aligned
- No visible cell borders — separation comes from row fill

**Section nav card** (closing slide only):
- 126×36 pt rounded rectangle, `#34433F` fill
- Green section number 14 pt bold + white name 11 pt, both centered

## Image Specifications

The reference deck is illustration-free, but the template supports images cleanly when used sparingly.

**When to include images:**
- Architecture diagrams (preferred: build with shapes per Template D, not raster) — use a raster image only when the diagram exists externally and re-creating it isn't practical
- Screenshots of UIs, dashboards, or tool output
- Product photography on a title slide
- Author/team headshots on a closing slide

**When NOT to include images:**
- Decorative stock photography behind text — never
- Logos other than ORIGIN inside the content area — partner logos go in a dedicated logo strip
- Background washes or hero photos under text

**Placement zones (Template D content slides):**
- **Right pane** (`left=367, top=85, width=324, height=270`) — default for a single supporting image alongside left-pane text
- **Full-width band** (`left=29, top=85, width=662, height=200`) — wide diagram or screenshot, with explanatory text below at `top=295`
- **Inline thumbnail** (`width≤120, height≤90`) — small icon or logo within a card or row

**Sizing rules:**
- Maintain source aspect ratio — never distort. Pass either width OR height, not both.
- Minimum size for screenshots: 240 pt wide (smaller is unreadable on projection)
- Maximum image area: 60% of the content zone. If an image is larger, give it its own slide.
- Image edges align to the 29 pt left margin or 367 pt column gutter — never floating mid-column

**Treatment:**
- **Frame:** wrap every photographic image in a 1 pt `#141712` border. Diagrams and screenshots with white backgrounds get the same border so they don't bleed into `#F4F3EF`.
- **Background:** if an image has transparency, place it directly on the slide background. For photos, no drop shadow or rounded corners — keep the geometry square.
- **On dark slides:** add a 2 pt `#ADFF26` accent on the left or top edge of the image (matches the card treatment); never frame in white.
- **Captions:** 10 pt italic `#77766E`, placed directly under the image, left-aligned to the image's left edge.

**Logo strip (Template D, four-column):**
- Four `#FFFFFF` cards each 144×62 pt, 4 pt green left bar, partner logo centered, 1 pt `#141712` border
- Logos rendered at 80% of card height with a 20 pt internal margin

**Architecture diagrams:** strongly prefer building with native shapes (see Architecture / diagram boxes component) over inserting a raster image — it stays crisp, accessible, and editable. Only fall back to an inserted image when the diagram comes from an upstream tool (drawio, Lucidchart, Visio export).

## Layout Assembly Guidance

Given an outline, pick templates per item, not by sequence:

1. **First slide** → Template A (Title)
2. **Outline item that's a section header / chapter** → Template C (Section Divider)
3. **Outline item that's a topic with details** → Template D (Content). Choose the inner grid based on the outline's substructure:
   - 2 parallel concepts → two-column grid
   - 3–4 sequential or peer items → three/four-column step or tag grid
   - Hierarchical list of items with descriptions → full-width table
   - One concept with a diagram → diagram + sidebar
4. **Outline item that's a list of links** → Template F (Resource)
5. **Optional second slide before the close** → Template B (Table of Contents) used as a recap
6. **Last slide** → Template E (Closing)

Rules that always apply, regardless of order:
- Every slide carries the left green strip and the ORIGIN wordmark
- Section dividers are optional but, if used, must precede every section's first content slide and must be numbered sequentially (`01`, `02`, …)
- Breadcrumbs on content slides must match the section divider number and name exactly (e.g., "02 / Backend")
- Density limit: a single content slide holds at most ~7 cards / ~7 table rows / ~5 step rows. If the outline item exceeds this, split it across two slides with the same title and append "(cont.)" or a sub-scope
- Never mix light and dark backgrounds within the same section's content slides
- Never use Logo Green as text on a light background (see the Contrast rule) — use Logo Black instead
