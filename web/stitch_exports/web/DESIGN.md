---
name: SamskritaDhvani
colors:
  surface: '#fdf8f5'
  surface-dim: '#ddd9d6'
  surface-bright: '#fdf8f5'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f7f3ef'
  surface-container: '#f1ede9'
  surface-container-high: '#ece7e4'
  surface-container-highest: '#e6e2de'
  on-surface: '#1c1b1a'
  on-surface-variant: '#56423d'
  inverse-surface: '#31302e'
  inverse-on-surface: '#f4f0ec'
  outline: '#8a726c'
  outline-variant: '#ddc0b9'
  surface-tint: '#a13f26'
  primary: '#7e260f'
  on-primary: '#ffffff'
  primary-container: '#9e3d24'
  on-primary-container: '#ffc9bc'
  inverse-primary: '#ffb4a2'
  secondary: '#a13f2a'
  on-secondary: '#ffffff'
  secondary-container: '#ff866b'
  on-secondary-container: '#741f0d'
  tertiary: '#5d3f00'
  on-tertiary: '#ffffff'
  tertiary-container: '#7b5503'
  on-tertiary-container: '#ffcd7d'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdbd2'
  primary-fixed-dim: '#ffb4a2'
  on-primary-fixed: '#3c0800'
  on-primary-fixed-variant: '#812811'
  secondary-fixed: '#ffdad3'
  secondary-fixed-dim: '#ffb4a4'
  on-secondary-fixed: '#3e0500'
  on-secondary-fixed-variant: '#812815'
  tertiary-fixed: '#ffdead'
  tertiary-fixed-dim: '#f2be68'
  on-tertiary-fixed: '#281900'
  on-tertiary-fixed-variant: '#604100'
  background: '#fdf8f5'
  on-background: '#1c1b1a'
  surface-variant: '#e6e2de'
typography:
  display:
    fontFamily: Noto Serif
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Noto Serif
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
  headline-lg-mobile:
    fontFamily: Noto Serif
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Noto Serif
    fontSize: 22px
    fontWeight: '500'
    lineHeight: 30px
  headline-sm:
    fontFamily: Noto Serif
    fontSize: 18px
    fontWeight: '500'
    lineHeight: 26px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-lg:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.01em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
    letterSpacing: 0.03em
  code:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-sm: 1rem
  margin: 2rem
  margin-sm: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style
The design system establishes an environment of quiet intellectual rigor and archival reverence. Conceived for linguists, philologists, and acoustic researchers working in Sanskrit phonetics and computational prosody, the UI prioritizes sustained concentration over transient stimulation. The aesthetic marries classical epigraphic tradition with contemporary computational precision—an architectural synthesis of ancient palm-leaf manuscript discipline and high-resolution acoustic laboratory interfaces.

Visual hierarchy relies on structural restraint, expansive negative space, and disciplined typographic rhythm rather than decorative embellishments. Motion is minimal, instantaneous, and purely functional. The emotional register is serene, authoritative, and uncompromisingly scholarly—devoid of consumerized gamification, cheerful microcopy, or artificial visual noise.

## Colors
The palette evokes aged parchment, unglazed terracotta, and mineral pigments. 

- **Surface & Canvas:** The background hierarchy moves across tiered parchment tones. The base canvas anchors at `#F9F8F5`, elevated panels and cards rest on `#F4F1EA`, and nested technical sub-containers or inset panels use `#EFECE6`. Active selection fills and subtle structural stripes drop to `#E8E3DA`.
- **Primary & Secondary Accents:** Primary actions, focal phonetic annotations, and waveform selections utilize deep madder saffron `#9E3D24` and its darker lithic counterpart `#842A17`. These colors signify critical semantic states (e.g., active phoneme segmentation, primary audio playback). A muted temple-ochre `#C29342` provides tertiary emphasis for metrical analysis (chandas) and prosodic stress markers.
- **Typography & Structural Inks:** Primary text is `#242321` (charcoal ink), avoiding harsh digital blacks. Secondary commentary, phonetic metadata, and IPA transcriptions reside in `#57534E`. Muted UI chrome, timestamps, and inactive glyphs utilize `#78716C`.
- **Borders & Dividers:** Outlines and tabular rules strictly employ warm stone `#E5E0D8`, maintaining structural integrity without visual weight.

## Typography
Typographic orchestration is tripartite:
1. **Classical / Scriptorial (`Noto Serif`):** Applied to Devanagari text, transliterated IAST verses, corpus titles, and analytical module headers. Its classical proportion maintains legibility for complex conjunct consonants (saṃyuktākṣara) and Vedic svara diacritics.
2. **Instrumental Chrome (`Inter`):** Applied to interface controls, configuration panels, dense metadata trees, and systemic feedback. Neutral, uninflected, and optimized for data density.
3. **Acoustic Readout (`JetBrains Mono`):** Applied to spectrogram frequency coordinates (Hz), formant values (F1/F2/F3), pitch contours, audio timecodes, and International Phonetic Alphabet (IPA) strings.

Devanagari rendering requires explicit typographic configuration with ligatures fully enabled (`font-variant-ligatures: normal`) and generous line-height to prevent diacritical collision between vertical matras and viramas.

## Layout & Spacing
The layout follows a disciplined workbench model: a fixed-width left navigation rail for corpus and session management, a fluid multi-tier workspace for spectrograms and waveform editors, and an optional collapsible right inspector for phonological and metrical properties.

- **Grid Systems:** Workspaces use an asymmetrical 12-column layout on desktop viewports (1280px+), collapsing to a stacked single-column layout below 1024px. The main analytical stage prioritizes horizontal continuity for linear audio timelines.
- **Rhythm & Padding:** Spacing operates strictly on an 8px base rhythm (with 4px increments for dense parameter tables). Generous margins (`margin: 2rem`) around the primary audio workspace prevent cognitive fatigue, while inspector drawers use tighter padding (`space-sm` to `space-md`) to ensure high density of acoustic parameters.
- **Breakpoints:**
  - **Desktop (≥ 1280px):** 3-panel split view (Corpus Tree: 260px fixed, Main Spectrogram: fluid, Inspector: 320px fixed).
  - **Tablet (768px – 1279px):** Inspector transitions into an overlaid sheet; spectrogram maintains horizontal scrollability.
  - **Mobile (< 768px):** Linear sequence: segmented audio clip reader, stacked text preview, and tabular metric cards.

## Elevation & Depth
Depth in the design system is communicated through flat, tonal stratification rather than artificial optical drop shadows. The design system eschews floating cards and blurred glass surfaces.

- **Tonal Layers:** Hierarchical depth is achieved strictly by stepping surface values: `#F9F8F5` (base canvas) → `#F4F1EA` (workstation surface) → `#EFECE6` (nested audio timeline or technical container).
- **Crisp Outlines:** Boundaries between distinct workspace domains rely on 1px continuous borders tinted in `#E5E0D8`. Active or selected regions substitute this boundary with `#9E3D24`.
- **Zero Heavy Shadows:** Shadows are omitted entirely across standard surfaces, except for modal dialogs and dropdown menus, which employ a subtle, diffused warm shadow: `0 4px 16px -2px rgba(36, 35, 33, 0.08)`.

## Shapes
Geometry is utilitarian, structured, and formal. Corners feature modest softening (`roundedness: 1`, mapping to `0.25rem` / `4px`), which prevents the harshness of raw right angles without sacrificing the architectural quality suited to scientific instrumentation.

Badges, phoneme segmentation pills, and waveform cursors maintain strict rectangular structures with minimal chamfers. Interactive controls (buttons, inputs) utilize the default `0.25rem` radius. Fully rounded pills are strictly forbidden to avoid colloquial or consumer-application tropes.

## Components

### Buttons
- **Primary:** Solid `#9E3D24` background, `#F9F8F5` text, 1px border of `#842A17`. Zero shadow. Hover transitions to `#842A17`.
- **Secondary / Ghost:** Transparent background, `#242321` text, 1px border of `#E5E0D8`. Hover state fills with `#EFECE6`.
- **Icon / Utility Buttons:** Standardized to 32×32px squares with 4px border radius. Uses minimalist stroke icons (1.5px stroke weight) in `#57534E`.

### Chips & Badges
- **Acoustic / Metrical Tags:** Non-interactive tags (e.g., *Laghu*, *Guru*, *Pluta*) render in `#EFECE6` with `#57534E` text and a subtle 1px `#E5E0D8` border.
- **Phoneme Classes:** Svara (vowels), Sparśa (stops), and Antastha (semivowels) use discrete, low-saturation earth-toned fills with monospaced labels.

### Lists & Corpus Navigation
- Flat, dense tabular presentation. List items have a 36px fixed height, separated by 1px `#E5E0D8` horizontal borders.
- Hover states initiate a subtle background shift to `#F4F1EA`. Active/selected items display a 2px left border accent in `#9E3D24`.

### Checkboxes & Radio Buttons
- Custom 16×16px square checks (4px radius) and circles. Unchecked: `#F9F8F5` surface with 1px `#E5E0D8` border. Checked: `#9E3D24` fill with `#F9F8F5` indicator marks. Focus rings apply a 2px offset outline in `#9E3D24`.

### Input Fields & Parameter Steppers
- Background of `#F4F1EA`, 1px border of `#E5E0D8`, text in `#242321`. Focus state transitions the border to `#9E3D24` with zero ambient glow. Placeholder text in `#78716C`. Monospace font (`JetBrains Mono`) for all numerical tolerance, pitch, and duration fields.

### Cards & Panels
- Flat structural panels with `#F4F1EA` surface fill and 1px `#E5E0D8` border. Header bars within panels are visually anchored by an internal horizontal divider and labeled in `label-lg` uppercase tracking.

### Specialized Domain Components
- **Phonetic Timeline Tier:** Stacked horizontal lanes displaying audio waveform, pitch contour (F0), spectrogram, and aligned Devanagari/IPA text tracks. Boundary markers are draggable vertical rules (`#9E3D24`, 1px width) with micro-numeric time indicators at the bottom.
- **Prosodic Grid (Chandas Visualizer):** A metrical matrix with fixed cells denoting moraic weights. Classical signs—horizontal bars for *guru* (long, 2 mātrās) and vertical crescents for *laghu* (short, 1 mātrā)—render in `#842A17` over an `#EFECE6` grid.