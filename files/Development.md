# SamskritaDhvani — Development.md

**Project full title:** *SamskritaDhvani: A Hybrid Signal Processing
Approach to Sanskrit Phonetic Assessment and Bhagavad Gita Verse
Recognition*

**Purpose:** This document defines the full development lifecycle for
SamskritaDhvani — two linked sub-projects built on a shared MFCC-based
acoustic front-end:

- **SPD** — Sanskrit Pronunciation error Detection (DTW-based scoring)
- **GVR** — Bhagavad Gita Verse Recognition (HMM-based classification)

It exists to keep the project **feasible, correct, and defensible in a
report/viva** as it grows. Every phase below is strictly scoped: work
is not allowed to skip ahead, and no phase closes until its exit
criteria are actually met and verified — not assumed.

Companion documents:
- **Implementation.md** — the project-specific technical plan: system
  architecture, software stack, data plan, and how each phase below
  applies concretely to SPD and GVR. Development.md defines *how* work
  is done in general; Implementation.md defines *what* is being built.
- **Review.md** — the running log of what was checked, what changed,
  and what's still outstanding. Every session of work should end with a
  Review.md update.
- **SRS.md** — the formal requirements this process exists to satisfy.
- **DataIntegrity.md** — the standing policy for what counts as valid
  audio data and how corrupted, silent, or unattributed audio is kept
  out of the pipeline. Any Phase 2, 5, or 6 work touching the audio
  corpus must follow it.

---

## Ground Rules (apply across every phase, no exceptions)

1. **No fabricated numbers.** Any similarity score, recognition
   accuracy, correlation, or timing figure reported must come from an
   actual run, with the command/script used to produce it. If it wasn't
   measured, it's labeled "estimated" or "not yet measured" — never
   presented as fact.
2. **No silent scope creep.** A bug fix stays a bug fix. A feature
   stays its own reviewable unit. Refactors happen in their own pass,
   never bundled into an unrelated change.
3. **No phase skipping.** You cannot move from Design to Coding, or
   Coding to Testing, without that phase's exit criteria checked off in
   Review.md.
4. **No breaking the shared front-end silently.** The MFCC/feature
   extraction module is used by both SPD and GVR. Any change to its
   output shape, normalization, or default parameters is a breaking
   change to both branches and must be flagged explicitly.
5. **No doc drift.** If a change affects a number or claim in the
   project report, `Implementation.md`, or `SRS.md`, the doc update is
   part of the same unit of work — not a "later" task.
6. **No unverified "it works."** A change is not done until the
   specific test(s) covering it have actually been run and the result
   recorded. "Should work" is not a completion state.
7. **Known trade-offs stay documented, not silently "fixed."** E.g.
   closed-set GVR (not open-vocabulary ASR), small-corpus HMM overfitting
   risk, and the choice of recitation tradition for reference audio
   (see `Implementation.md` §10) are intentional, documented scope
   limits. They get revisited only as an explicit task, never patched
   as a side effect of something else.
8. **All work is branch-based (or clearly separated).** Each unit of
   work gets its own Review.md entry and passes the phase's exit
   criteria before being folded into the main pipeline/report.

---

## Phase 1 — Feasibility Study

**Objective:** Confirm that a proposed change (new word, new verse
subset, new feature type, scope expansion) is actually worth building
before any design work starts.

**Entry criteria:** A clearly stated idea or problem (e.g. "add
duration-based scoring to SPD," "extend GVR to Chapter 12," "add an
LPCC ablation").

**Activities:**
- State what the change does and who it benefits: a learner using SPD,
  an evaluator reviewing GVR's output, or the report/viva itself.
- Check what already exists first. SamskritaDhvani already has a shared
  MFCC(+Δ/ΔΔ)+CMVN front-end, a DTW-based SPD scorer, and a per-verse
  HMM GVR classifier (see `Implementation.md` §3). Don't propose
  rebuilding something that already exists — read the relevant module
  first.
- Effort/impact estimate: S/M/L effort, low/med/high impact.
- State the real trade-off: added complexity, added dependency weight,
  accuracy risk, or corpus-collection burden (recording more audio is
  often the actual bottleneck, not the algorithm).
- Explicitly flag if the idea touches the shared front-end (affects
  both SPD and GVR) or a number already reported in the project report.

**Rule specific to this phase:** An idea does not proceed to Phase 2
without a stated "why now" — impact alone isn't sufficient if it
doesn't close a real gap (e.g. a specific weakness found during
testing) or unlock something concrete.

**Exit criteria:** A short feasibility verdict recorded in Review.md:
go / no-go / needs more information, with the effort/impact estimate
and named trade-offs.

---

## Phase 2 — Resource Gathering & Analysis

**Objective:** Establish the actual technical ground truth before
designing anything — what the code and corpus currently contain, not
what the report claims.

**Activities:**
- Read the exact module(s)/function(s) the change will touch. Do not
  design against assumed structure.
- For front-end work: confirm current MFCC configuration (sample rate,
  frame size/shift, number of mel filters, cepstral coefficients kept,
  window type) exactly as currently implemented, per `Implementation.md`
  §4 and FR-01/FR-02 in `SRS.md`.
- For SPD work: review the existing DTW scoring formula and per-axis
  breakdown implementation before changing it.
- For GVR work: review the existing HMM topology (states, emission
  model) and the verse registry before adding verses or changing
  training.
- Confirm current corpus state: how many words/verses actually have
  verified, provenance-tracked audio right now (per
  `DataIntegrity.md`) — do not assume the corpus is larger or cleaner
  than it's been checked to be.
- Confirm current test coverage for the area being touched — know what
  already covers this before assuming a gap.

**Rule specific to this phase:** Every claim about "how the pipeline
currently works" must be backed by an actual file read, listen-through,
or command run in this session — not recalled from a prior session or
assumed from the report alone, since docs can drift from code.

**Exit criteria:** A short written summary in Review.md of the current
state relevant to the task (modules involved, existing conventions,
current corpus/test coverage) — this becomes the input to Design.

---

## Phase 3 — Design

**Objective:** Decide the shape of the change before writing code, so
implementation doesn't wander or contradict the existing pipeline.

**Activities:**
- Specify: new/changed interfaces (feature extractor signature, SPD
  scoring formula, GVR HMM interface), data flow, and where any new
  state (e.g. a new provenance entry, a new HMM model file) lives.
- Specify test plan up front: which existing tests must still pass,
  which new tests will be written, and what "done" looks like in
  measurable terms (a passing test, a specific evaluation run) — not a
  vague "it should score better."
- Specify report/doc impact: which sections of the project report need
  updating, and what specifically changes in them.
- If the change is breaking (alters the shared front-end's output
  shape, changes the verse registry format), state the migration
  impact on the other branch plainly rather than deferring it.
- If the design is ambiguous on a material point (which verses to add
  next, how many mispronunciation variants per word, whether GVR needs
  phoneme-level or whole-verse HMMs), resolve it with one direct
  question rather than guessing.

**Rule specific to this phase:** Design must name the smallest unit of
change that accomplishes the goal. If a design requires touching more
than one of (shared front-end, SPD module, GVR module) at once, split
it into sequential, independently testable steps.

**Exit criteria:** A design note in Review.md: interfaces changed, test
plan, report impact, and (if applicable) migration/compatibility notes
— reviewed before Phase 4 starts.

---

## Phase 4 — Coding

**Objective:** Implement exactly what Phase 3 specified, matching
existing conventions, with no unrelated changes mixed in.

**Activities:**
- Follow existing conventions exactly (see Phase 2). New SPD scoring
  axes plug into the existing breakdown structure; new GVR verses plug
  into the existing registry format.
- Keep changes minimal and localized to what Phase 3 designed — no
  drive-by refactors of unrelated code.
- Any new dependency is added to `requirements.txt` with a pinned
  version, and its weight/necessity is justified (see
  `Implementation.md` §4's "explicitly deferred" list before adding
  anything heavy).
- Any change to a reported number or documented interface is paired
  with the corresponding doc edit in the same unit of work.

**Rule specific to this phase:** No commit is "just a quick fix while I
was in there" — if something adjacent looks wrong while coding, it's
logged in Review.md as a new item for its own future Phase 1–2 pass,
not folded into the current change.

**Exit criteria:** Code compiles and imports cleanly for every touched
module. Ready for Phase 5.

---

## Phase 5 — Testing

**Objective:** Prove the change works and didn't break anything else —
with actual runs, not assumptions.

**Activities:**
- Run the full test suite and record the exact pass/fail count in
  Review.md.
- Write or update tests in the existing style, covering: the
  new/changed happy path, at least one edge case (e.g. a corrupted or
  near-silent input file), and integration with whatever the change
  plugs into.
- For SPD changes: verify the similarity score behaves as designed on
  a controlled experiment (e.g. known-correct vs. known-mispronounced
  recitations), per `Implementation.md` §8.
- For GVR changes: report recognition accuracy on a real held-out test
  split — never training-set accuracy — with a confusion matrix.
- For any performance/accuracy claim: run it and report the actual
  number and the exact command to reproduce it. Never present an
  estimate as measured.

**Rule specific to this phase:** A change is not "tested" until the
specific test run and its actual result are written into Review.md. If
a test can't be run in the current environment (e.g. missing audio
hardware, insufficient corpus size), that limitation is stated
explicitly — it is never silently treated as a pass.

**Exit criteria:** All relevant tests pass (or failures are triaged and
either fixed or explicitly deferred with a reason in Review.md).

---

## Phase 6 — Maintenance

**Objective:** Keep the project correct and defensible on an ongoing
basis — separate from any single feature's lifecycle.

**Recurring activities (run periodically, not just on-demand):**
- **Bug sweep:** scan the shared front-end, SPD module, and GVR module
  in that order (front-end bugs affect both branches). Every finding
  must be reproduced (a failing test, a specific triggering input)
  before being logged as a confirmed bug rather than a "suspected
  issue."
- **Report audit:** spot-check that the project report's numbers still
  match what the code currently produces; flag drift immediately rather
  than letting it accumulate.
- **Dependency review:** check for stale pins in `requirements.txt`.
- **Data Integrity Sweep:** run the full procedure defined in
  `DataIntegrity.md` — corruption, silence, provenance, and
  cross-split-leakage checks across the SPD word list and GVR verse
  registry. This is a required, standing maintenance task, not optional
  cleanup; results are logged in Review.md using the table format
  defined in `DataIntegrity.md`.

**Rule specific to this phase:** Maintenance findings are triaged by
real risk — data-validity issues that would invalidate a reported
number > pipeline breakage > cosmetic — and every finding gets a
Review.md entry, whether or not it's fixed immediately.

**Exit criteria:** N/A (this phase is continuous) — but each
maintenance pass closes with an updated Review.md entry stating what
was checked, what was found, and what remains open.

---

## How task-specific work maps onto these phases

| Mode | Phase(s) it belongs to | What it does |
|---|---|---|
| **General dev (front-end, SPD, or GVR work)** | 2, 3, 4 | Grounded context + conventions for day-to-day module work |
| **Bug-hunt & fix** | 6 | Systematic scan in front-end → SPD → GVR order, reproduce-before-fix discipline |
| **Pre-report / pre-viva audit** | 6 (gate before presenting results) | Confirms every reported number traces to an actual run and a validated corpus state |
| **Corpus/feature growth** | 1, 3, 4 | Impact/effort-ranked proposals for new words, verses, or feature types, convention-matched implementation |
