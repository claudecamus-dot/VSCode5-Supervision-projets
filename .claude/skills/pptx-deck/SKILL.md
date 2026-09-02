---
name: pptx-deck
description: Build quality PowerPoint slides with python-pptx — a reusable helper library (typographic scale, colored progress bars, circular gauge, cards, chips) plus a mandatory geometric self-check that catches shapes running off the slide. Use when generating or improving .pptx decks programmatically (restitution/synthesis/report decks), especially when content looks cramped, overflows, or lacks visual hierarchy. Pairs with a real-render verification step (LibreOffice or PowerPoint COM on Windows).
---

> **Provenance** : rapatriée de `~/.claude/skills/pptx-deck` au hub le 2026-09-02
> (arbitrage `VScode5:skills-pptx-globales-non-versionnees`).
> La copie du hub est désormais la source : corriger ICI, jamais dans
> `~/.claude/skills/`, sinon les deux divergent en silence.

# pptx-deck

Reusable toolkit to generate **well-designed** slides with `python-pptx` instead
of dumping monotone bullet lists. The recurring failure mode of hand-built decks
is shapes positioned for the wrong slide size (content runs off the bottom/right)
and a flat wall of text. This skill fixes both: principled layout helpers + an
automatic geometry check, verified against a real render.

## When to use

- Generating a `.pptx` from data (dashboards, restitution, synthesis, reports).
- A generated deck "n'est pas bien designé": cramped, overflowing, no hierarchy.
- You need bars / gauges / cards / KPI emphasis rather than bullet lists.

## The helper library

`scripts/pptx_deck.py` (dependency: `python-pptx`; charts use its built-in
support). Coordinates are in **inches** (floats) for readability. Import it:

```python
import sys, os; sys.path.insert(0, "<dir containing pptx_deck.py>")
import pptx_deck as D
```

Key API:
- `D.TYPE` — the **one** type scale (`title/h2/h3/body/small/tiny/kpi/kpi_unit` in pt). Never hardcode random sizes; pull from here so the deck stays consistent.
- `D.PALETTE`, `D.couleur_pilier(i)`, `D.INK/MUTED/LINE/TRACK/OK/WARN/GOLD` — colors.
- `D.add_text(slide, l, t, w, h, lignes, anchor=, align=, wrap=)` — text box from a list of `(texte, opts)` paragraphs; opts: `size,bold,italic,color,align,space_before,space_after,line_spacing`. Margins zeroed, autosize off (so geometry is predictable).
- `D.add_rect(slide, l, t, w, h, fill=, line=, line_w=, rounded=, radius=)` — rectangle / rounded rectangle, shadow disabled.
- `D.add_hbar(slide, l, t, w, h, frac, fill, track=)` — horizontal progress bar (track + fill), `frac` in 0..1.
- `D.add_gauge(slide, l, t, size, frac, fill, track=, hole=)` — circular ring gauge via a 2-segment doughnut chart; place the centre label separately with `add_text(..., anchor=MIDDLE)`.
- `D.add_card(slide, l, t, w, h, accent)` — white rounded card + colored left accent bar (for lists of items).
- `D.estimer_lignes(texte, largeur_in, taille_pt, cpi_ref=11.0, taille_ref=10.5)` — estimates how many lines `texte` will wrap to at `taille_pt` in a box `largeur_in` inches wide (chars/inch derived from `cpi_ref` calibrated at `taille_ref`).
- `D.ajuster_police(textes, largeur_in, taille_max, taille_min, budget_ok, pas=0.5)` — **adapts font size to sentence length** instead of a fixed line cap. Searches from `taille_max` down to `taille_min` for the largest size where your `budget_ok(taille, lignes_max)` callback (your own layout constraint, e.g. "N stacked cards must fit in this band") returns true. Returns `(taille, lignes_max)`. Falls back to `taille_min` if nothing fits — never silently truncates on its own.
- `D.tronquer_a_lignes(texte, largeur_in, taille_pt, max_lignes)` — last-resort ellipsis truncation for the rare case where even `taille_min` doesn't fit. Pair with `ajuster_police`: shrink first, truncate only as the final fallback, so geometry never breaks.
- `D.verifier_geometrie(prs, marge_in=0.02)` — **returns the list of out-of-frame shapes** (empty = OK). Call before saving.
- `D.theme_colors(prs)` — reads the template's theme palette (`dk1/lt1/dk2/lt2/accent1..6`) as `{name: '#RRGGBB'}` (empty dict if unreadable). Use to derive a **brand accent** from a provided model template instead of hardcoding — but keep categorical/series colors (e.g. per-pilier) as a deliberate palette, since a theme's accents are rarely a good N-category set.

## Design principles (keep the deck "de qualité")

1. **Size the layout to the real slide.** Read `prs.slide_width/height` first. The
   classic bug is positioning for 10×7.5" (4:3) on a 10×5.625" (16:9 short) deck —
   everything overflows. Define a content band (e.g. top ≈ title height, bottom ≈
   slide height − footer) and lay out inside it.
2. **No vertical void.** Don't rely on body placeholders that vertical-center their
   text (they leave a big gap under the title when content is short). Draw absolute
   shapes from the top of the content band.
3. **Hierarchy over bullets.** One headline metric (gauge/KPI), then bars/cards. Use
   color to encode meaning (per-category palette; green/red for up/down, weak).
4. **Respect template chrome.** Prefer a "title-only" layout so the master's logo,
   footer and page number survive; draw your infographic in the content area rather
   than covering the brand with a full-bleed band.
5. **One type scale** (`D.TYPE`) and generous whitespace.
6. **Adapt font size to text length, don't hard-cap lines.** A fixed "max 2 lines"
   assumption breaks the moment real data has a longer sentence than your test data —
   text silently overflows its box. Use `D.ajuster_police` to shrink font size (and
   thus line count) to fit real content, with `D.tronquer_a_lignes` as the final
   fallback (ellipsis) only when even the size floor doesn't fit. **Size each item to
   its own content**, not a uniform height applied to a whole group from its worst-case
   member — a short item next to a very long one shouldn't inherit the long one's
   height (or, worse, get clamped below its own content's height). Sum individual
   sizes and check the sum against your budget, not `n × max`.
7. **Floor on readable text: ~10.5pt, never below.** `D.ajuster_police`'s
   `taille_min` should not go under this — smaller reads as illegible at
   slide scale/projection, whatever the fitting pressure (repris de
   VSCode1/export/design-system-octo.md §2, 2026-09-02).

## Mandatory verification

1. **Geometry check (always).** `problemes = D.verifier_geometrie(prs); assert not problemes`.
   Wire it into a test that builds the deck from a synthetic payload (incl. edge
   cases: missing values, no comparison, very wide images).
2. **Real render (see it).** A geometry-clean deck can still look wrong. Render to
   images and inspect:
   - **Windows + PowerPoint:** drive PowerPoint via COM to export PNGs —
     ```powershell
     $p = New-Object -ComObject PowerPoint.Application
     $pres = $p.Presentations.Open($pptx, $true, $false, $false)
     foreach ($s in $pres.Slides) { $s.Export($png, "PNG", 1280, 720) }
     $pres.Close(); $p.Quit()
     ```
   - **LibreOffice (any OS):** `soffice --headless --convert-to pdf deck.pptx`.
   - **No renderer:** fall back to the geometry check + dumping each shape's text and
     bounds; state honestly that the visual was not eye-checked.

### Defects the geometry check will NOT catch (eyeball these every render)

`verifier_geometrie` only flags shapes off the slide. A deck can pass it and still
look broken. When you render, hunt specifically for:

1. **Over-stretched panels / empty voids.** A callout/panel sized to the full band
   but holding 2–3 lines reads as a big empty box. **Size panels to their content**
   (+ a small margin) and center them in the free space — don't stretch to fill.
2. **Values not aligned to the element they annotate.** A number placed beside a bar
   must be **vertically centered on the bar's centerline** (a box centered on the bar,
   `anchor=MIDDLE`), not top-anchored — a big `h3` number otherwise floats above the
   bar. Use a single helper for the "value beside bar" so every bar matches.
3. **Collisions with template chrome.** Geometry only checks the slide frame, never
   overlap with the master's **page-number badge / logo / footer**. On a title-only
   layout the page number sits bottom-right; keep full-width bottom content clear of
   that corner (measure the badge once on a render, then cap your right edge short of
   it). Same for the footer band at the bottom.
4. **Gaps from over-budgeted line heights.** Estimate ~**0.17"/line for 10.5pt**
   (~0.20" for 12pt), not 0.23–0.25". A too-tall text box leaves slack that opens a
   visible gap between stacked elements (e.g. question ↔ caption). Keep one constant
   and tune it against a real render.
5. **Content flush to borders.** Give cards/panels internal padding so text doesn't
   touch the rounded edge; center the content block within the card.
6. **Cryptic labels.** Spell out indicators for the reader (`écart-type`, not `é-t`).
   Don't duplicate as text what a shape already shows (e.g. a min–max range already
   drawn by the bar) — name the metric instead.
7. **Text overflowing its own card/box (geometry check won't catch this).** If a card's
   height was computed from a fixed line-count assumption (or from a *different* item's
   longer text in the same group), a text box can render taller than the shape drawn
   behind it — the shape itself stays in-frame (geometry passes) but the text visibly
   spills above/below its card on a real render. Test with synthetic text noticeably
   longer than anything in your real sample data, not just your typical case — this is
   exactly the gap between "tests pass" and "actually looked right" that only a real
   render (see below) exposes.

## Reusing in a project

Copy `scripts/pptx_deck.py` next to your generator (so runtime has no dependency on
this skill's install path) and `import pptx_deck as D`. Keep the project copy and
this one in sync if you extend the helpers.
