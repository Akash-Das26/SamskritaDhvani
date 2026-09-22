# Gita Supersite — Permission Request Draft

**Purpose:** Open Item 5 in `Review.md`. The GVR registry (SRS FR-22)
is blocked on all public sources (verified 2026-09-22/23 — see
`PROVENANCE.md` GVR-01/GVR-02 and `DataSources.md` §1); a maintainer
permission grant is the remaining path to verse-wise reference audio.
This file holds the ready-to-send draft. Fill every `[...]` slot
before sending — nothing here may be sent with invented details
(the same Ground Rule 1 discipline applies to correspondence as to
numbers).

---

## Addressing (verified 2026-09-23 — do not send to an unverified guess)

| Channel | Address / URL | Basis |
|---|---|---|
| **Primary** | `head@cse.iitk.ac.in` | Published on the CSE IIT Kanpur "Contact Us" page (`cse.iitk.ac.in/pages/ContactUs.html`): "E-mail: {head}@{cse.iitk.ac.in}". Request forwarding to the Gita Supersite team. |
| **Secondary (parallel)** | Contact form / any address published on `gitasupersite.in` itself | The current site is a JS SPA behind Cloudflare; check its footer/contact links from a normal browser session (automated fetches get the challenge shell). The legacy `old.gitasupersite.in` pages carry no mailto (checked 2026-09-23). |
| **Tertiary** | IIT Kanpur CSE administrative staff list (`cse.iitk.ac.in/pages/AdminStaff.html`) | Staff emails are published as `username@cse.iitk.ac.in`; the department office can route a student request. |

**Do not** use the personal addresses of individual faculty members
found in search results unless the department office or the site itself
names them as the Supersite contact — a permission request should come
through the team that owns the resource.

**From:** use your institute email (`[your-name]@[your-institute].ac.in`)
— academic affiliation is the credibility this request rests on.

---

## Subject line

```
Permission request: academic use of Bhagavad Gita verse audio from the
Gita Supersite (Sanskrit speech research, IIT Kanpur CSE project)
```

---

## Body

```
Dear Gita Supersite Team / Prof. [Head's name], Head, Dept. of CSE,

I am [your name], a [programme, e.g. B.Tech/M.Tech/PhD] student in
[department] at [institute], working on my [degree] project
"SamskritaDhvani: A Hybrid Signal Processing Approach to Sanskrit
Phonetic Assessment and Bhagavad Gita Verse Recognition" under the
supervision of [supervisor name, designation]. I am writing to request
your permission for a specific, limited academic use of material from
the Gita Supersite (https://www.gitasupersite.in / gitasupersite.iitk.ac.in).

What I am asking for
--------------------
Permission to download the verse-recitation audio for the Bhagavad Gita
available on the Supersite — verse-wise MP3s, chapters [N] only in the
first instance (~[20–70] verses) — and to use them in my project for:

  1. Building a verse-ID ↔ audio registry for a closed-set verse
     recognition experiment (one HMM model per verse, classical
     MFCC features — a standard speech-processing coursework
     architecture, cf. Rabiner 1989).
  2. Academic evaluation of that experiment inside my project report:
     accuracy and confusion-matrix results on held-out recordings.

What I am NOT asking for
------------------------
  - No redistribution of the audio in any form: not in the project
    repository, not in supplementary archives, not in derived datasets.
  - No commercial use of any kind.
  - No scraping of text/translation content; the Supersite's text
    material would only be consulted manually as reference.

Method and load
---------------
Retrieval would be a one-time, rate-limited download of the verse
audio files ([N] files, ~[size] MB total), done manually or via a
script throttled to a request every few seconds to avoid loading the
server. I note the site currently sits behind Cloudflare protection;
if direct download is not practical, I would be glad to receive the
files any way the team prefers (a zip archive, a Drive/Dropbox link),
or to have a team member supervise the retrieval.

Provenance and attribution
--------------------------
The project maintains a provenance ledger (source, license/permission
basis, access date for every audio file — this request exists precisely
because the Supersite states no reuse license and I will not use the
material without one). With your permission, every file will be logged
as "Gita Supersite, used with permission of the Gita Supersite team,
IIT Kanpur CSE (granted [date])", the Supersite will be credited in
the project report's acknowledgements and methodology section, and a
copy of this correspondence will be retained as the permission record.

Scope of the project
--------------------
Purely academic coursework: the report is submitted to [institute] and
is not published commercially. If any future publication were to use
results built on Supersite audio, I would seek your approval again
before including them.

If this request should be directed to someone else on the team, I
would be grateful if you could forward it or point me to the right
contact. I am happy to provide supervisor endorsement, institute ID,
or any other assurance you require, and of course to answer questions.

Thank you for building and maintaining the Supersite — it is an
extraordinary resource for Sanskrit studies.

Yours sincerely,
[your name]
[programme, department, institute]
[institute email] · [phone, optional]
[supervisor name, designation, email — with supervisor cc'd]
```

---

## Before sending — checklist

- [ ] Every `[...]` filled; supervisor cc'd (their endorsement is the
      single biggest credibility factor for a student permission ask).
- [ ] First-instance chapter chosen consistently with the Phase 3
      design decision ([N] = the verse subset already agreed for the
      self-recording program — using the *same* subset for both makes
      a permissioned set and a self-recorded set directly comparable).
- [ ] Sent from the institute email address.
- [ ] A copy of the sent mail + any reply saved to
      `data/provenance/gita_supersite_permission/` and logged in
      `PROVENANCE.md` GVR-02 ("Acquisition status" row) with the date.

## If the answer is YES

1. Log the grant (date, scope, any conditions) in PROVENANCE.md GVR-02
   and Review.md — only then may retrieval begin.
2. Retrieve respecting whatever method/load the team specified, sweep
   immediately per DataIntegrity §4 (this corpus becomes the canonical
   GVR reference registry, FR-22), and update PROVENANCE.md with
   per-file provenance.
3. Revisit the D4 self-recording decision scope: permissioned audio
   may serve as *reference* while self-recordings remain the
   *test/eval* side (per-reciter split policy per FR-23) — record the
   revised split policy in Review.md before any accuracy claim.

## If there is no response

- One polite follow-up after 2–3 weeks (template below); after a
  second silence, record "permission request unanswered" in
  PROVENANCE.md GVR-02 and keep the GVR registry on the D4
  self-recording path (the already-approved plan). Phase 4/5 work
  proceeds regardless — nothing is blocked on this except the
  registry itself.

### Follow-up template (2–3 weeks later)

```
Subject: Re: Permission request: academic use of Bhagavad Gita verse
audio from the Gita Supersite

Dear [name/team],

I am following up on my request of [date] (copied below) regarding
academic use of the Supersite's Bhagavad Gita verse audio for a
coursework speech-recognition project. I understand the team is busy;
a short yes/no, or a pointer to the right person, would be greatly
appreciated. Thank you again for the resource.

Yours sincerely,
[your name]
```
