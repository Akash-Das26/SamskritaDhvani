---
name: SamskritaDhvani Scholarly Lab
colors:
  surface: '#fef8f4'
  surface-dim: '#dfd9d5'
  surface-bright: '#fef8f4'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f9f2ef'
  surface-container: '#f3ede9'
  surface-container-high: '#ede7e3'
  surface-container-highest: '#e7e1de'
  on-surface: '#1d1b19'
  on-surface-variant: '#57423c'
  inverse-surface: '#32302e'
  inverse-on-surface: '#f6f0ec'
  outline: '#8b716b'
  outline-variant: '#dfc0b8'
  surface-tint: '#a63b1d'
  primary: '#7d1e02'
  on-primary: '#ffffff'
  primary-container: '#9e3518'
  on-primary-container: '#ffc1b1'
  inverse-primary: '#ffb5a1'
  secondary: '#625e59'
  on-secondary: '#ffffff'
  secondary-container: '#e9e1db'
  on-secondary-container: '#68645f'
  tertiary: '#4a4035'
  on-tertiary: '#ffffff'
  tertiary-container: '#62574c'
  on-tertiary-container: '#ddcdbf'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdbd1'
  primary-fixed-dim: '#ffb5a1'
  on-primary-fixed: '#3c0800'
  on-primary-fixed-variant: '#852307'
  secondary-fixed: '#e9e1db'
  secondary-fixed-dim: '#ccc5c0'
  on-secondary-fixed: '#1e1b18'
  on-secondary-fixed-variant: '#4a4642'
  tertiary-fixed: '#f0e0d1'
  tertiary-fixed-dim: '#d3c4b6'
  on-tertiary-fixed: '#221a11'
  on-tertiary-fixed-variant: '#4f453a'
  background: '#fef8f4'
  on-background: '#1d1b19'
  surface-variant: '#e7e1de'
typography:
  headline-lg:
    fontFamily: Noto Serif
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Noto Serif
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: 0em
  headline-md:
    fontFamily: Noto Serif
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: 0em
  headline-sm:
    fontFamily: Noto Serif
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: 0.01em
  body-lg:
    fontFamily: Noto Serif
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 32px
    letterSpacing: 0.01em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: -0.005em
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 19px
    letterSpacing: 0em
  label-lg:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 15px
    letterSpacing: 0.04em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '400'
    lineHeight: 14px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1.25rem
  gutter-lg: 2rem
  margin: 1.5rem
  margin-lg: 3rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system establishes a high-rigor, contemplative computational linguistics interface. Built specifically for Sanskrit acoustic analysis, phoneme alignment, and Bhagavad Gita metrical recognition, the system draws aesthetic structure from traditional palm-leaf manuscripts (*tāḷapatra*), classical epigraphy, and archival typography, filtered strictly through the lens of a contemporary computer science research lab.

The atmosphere is scholarly, quiet, and deeply analytical. It rejects ornamental tropes, mythic flourishes, and gamified mechanics. Devanagari script is prioritized as an analytical subject of inquiry: given ample optical line-height, immaculate ligature rendering, and balanced side-bearings. UI chrome stays austere and unobtrusive to ensure continuous focus during audio-spectrogram evaluation and meter (*chandas*) transcription.

## Colors

The palette is rooted in classical materials: handmade rag paper, weathered stone, and mineral cinnabar (*hiṅgula*). 

- **Primary (`#9E3518`):** Deep scholarly vermilion. Used with strict parsimony for primary actions, active acoustic markers, selected morphemes, and critical phonological warnings.
- **Secondary (`#4A4642`):** Dried charcoal ink. Supplies high-legibility secondary text, metadata labels, active tabs, and coordinate axes on spectrogram plots.
- **Tertiary (`#766A5E`):** Warm raw umber. Reserved for structural accents, minor data readouts, and subdued meter delineations.
- **Neutral (`#22201E`):** Lampblack neutral. The anchor for high-density body text, Devanagari ligatures, and high-contrast waveforms.

### Background & Surface Hierarchy
- **Canvas Base:** `#FAF8F5` (Warm off-white archival parchment).
- **Surface Layer 1:** `#F3EFEA` (Light warm stone for card interiors, spectrogram backdrops, and input wells).
- **Surface Layer 2:** `#EAE4DC` (Tonal elevation for hovered rows and segmented controls).
- **Borders & Rules:** `#E5DFD7` (Hairline delineation, replacing heavy shadows).
- **Subtle Accent Wash:** `rgba(158, 53, 24, 0.06)` (Phoneme selection and playback intervals).

## Typography

The type scale serves three distinct functional layers:
1. **Sacred & Textual Corpus (Noto Serif):** Used for Devanagari verse display, International Alphabet of Sanskrit Transliteration (IAST), and primary verse titles. Provides open counterforms, clear *mātrā* (vowel sign) clearance, and generous vertical clearance to eliminate clipping on conjunctive ligatures (*saṃyuktākṣara*).
2. **Operational Interface (Inter):** Clean, neutral sans-serif used for navigation, tabular data labels, filter options, and form fields. It ensures effortless scan-paths without competing with the complexity of Sanskrit typography.
3. **Acoustic & Metrics Engine (JetBrains Mono):** Precision monospaced type applied to pitch trackers (Hz), format frequencies (F1-F3), timestamp offsets, confidence scores, and syllable-weight notation (laghu/guru: `˘` / `¯`).

## Layout & Spacing

The interface employs a responsive 12-column structured grid designed for research density and simultaneous side-by-side inspection (e.g., audio waveform viewer paired with metrical scansion breakdown).

- **Desktop (≥1280px):** 12-column grid, 3rem margins, 2rem gutters. Layout allows persistent dual-pane workflows (Corpus Explorer + Waveform Analyzer).
- **Tablet (768px - 1279px):** 8-column grid, 1.5rem margins, 1.25rem gutters. Panels collapse into vertically stacked inspection drawers.
- **Mobile (<768px):** 4-column grid, 1rem margins, 0.75rem gutters. Sequential view toggling between text transcription, phonetic alignment, and audio playback.

Vertical rhythms prioritize comfortable Sanskrit reading: Devanagari blocks require a minimum vertical buffer of `space-lg` to prevent visual collision with adjacent technical graphs or metadata headers.

## Elevation & Depth

Visual hierarchy is maintained without heavy dropshadows or glossy textures. Depth is conveyed strictly through **tonal layering and micro-borders**:

- **Ground (Level 0):** Canvas `#FAF8F5`.
- **Containers (Level 1):** `#F3EFEA` bordered by a crisp `1px solid #E5DFD7`.
- **Inspectors & Flyouts (Level 2):** `#FAF8F5` bordered by `#D4CDC3` with a minimal ambient occlusion shadow: `0 4px 16px -2px rgba(34, 32, 30, 0.04)`.
- **Waveform Overlays / Scrubber Playheads:** Hairline `1px` or `2px` rules in `#9E3518` with zero diffusion blur.
- **Dividers:** Universal `1px solid #E5DFD7`. Vertical line height on separators matches optical cap-height of adjacent labels.

## Shapes

The interface embraces a refined, architectural curvature level. All base containers, input fields, spectrogram bounding boxes, and action elements utilize subtle `0.25rem` corners.

Pill shapes and bubbly radii are prohibited. The gentle `0.25rem` rounding softens high-density analytical grids without breaking the crisp, manuscript-ruled structural alignment characteristic of rigorous scientific instruments.

## Components

### Buttons
- **Primary:** Filled `#9E3518` background, `#FAF8F5` text, `0.25rem` border-radius. High-priority actions only (e.g., `Run Metrical Alignment`, `Record Syllable`). Padding: `0.5rem 1rem`. Focus state: `2px` ring `#9E3518` offset by `2px` `#FAF8F5`.
- **Secondary / Ghost:** Transparent background, `1px solid #E5DFD7`, `#22201E` text. Hover: `#F3EFEA` background and `#4A4642` border.
- **Icon / Transport Control:** Minimal squares (`36px x 36px`), `1px solid transparent`, `#4A4642` icon. Hover: `#F3EFEA` background with crisp hairline border.

### Input Fields & Search
- Surface: `#FAF8F5` with `1px solid #E5DFD7`. Text in `14px Inter` or `14px Noto Serif` (for Devanagari input).
- Focus: `1px solid #9E3518` without artificial drop-shadow glow. 
- Integrated virtual keyboard transliteration badges (e.g., `HK`, `IAST`, `SLP1`) sit inline in `JetBrains Mono` at `10px`.

### Chips & Badges
- **Metrical Tags (e.g., Triṣṭubh, Anuṣṭubh):** `#F3EFEA` fill, `#4A4642` text, hairline border `#E5DFD7`, padding `0.2rem 0.5rem`, `11px JetBrains Mono`.
- **Confidence Scores:** Monospaced pill badge using tonal thresholds:
  - High (≥95%): `#FAF8F5` background, `1px solid #B84A28`, vermilion text `#9E3518`.
  - Review Needed (<80%): `#FAF8F5` background, `1px solid #766A5E`, neutral text `#4A4642`.

### Cards & Analytical Panels
- Flat surfaces (`#FAF8F5` or `#F3EFEA`), defined by `1px solid #E5DFD7`.
- Card headers feature uppercase `11px JetBrains Mono` section tags paired with inline action buttons.
- No decorative gradients or card shadows.

### Specialized Research Components
- **Verse Scansion Display:** Devanagari text presented with top-aligned metrical markings (`¯` for guru, `˘` for laghu) in `JetBrains Mono` rendered in `#9E3518`.
- **Audio Waveform / Phoneme Bounding Boxes:** Waveform rendered in `#4A4642`. Phoneme partitions separated by dotted vertical rules (`#B84A28` at 40% opacity) with active playback segment highlighted via `rgba(158, 53, 24, 0.08)` background fill.