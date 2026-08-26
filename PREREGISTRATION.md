# PRE-REGISTRATION — Paper 5 (C1), frozen before analysis
**Freeze date:** 2026-08-21 · Any deviation logged in DEVIATIONS.md with rationale.
**Rule:** analysis code may only compute what is defined here. Exploratory work goes in
EXPLORATORY.md and is labeled as such in the paper.

## Event of study
MCP specification release `2026-07-28` ("statelessness migration"), RC tagged 2026-05-29.
Epochs: PRE = 2026-05-29..2026-07-27 (RC window), RELEASE = 2026-07-28,
POST = 2026-07-28..data-freeze (target freeze: 2026-11-15, giving a ~16-week post window).

## Research questions, estimands, and success/failure narratives

### RQ1 — Adoption curves
**Estimand:** per population (9 official SDKs; registry servers; dependent repos), the empirical
CDF of time-to-first-stateless-support measured from 2026-07-28.
**Adoption event definitions (frozen):**
- SDK: first release whose artifacts advertise the `2026-07-28` protocol version (source: release
  assets/tags + protocol-version constant in the tagged tree).
- Registry server: first version record with `publishedAt` >= 2026-07-28 whose declared protocol
  version (or schema reference) is the 2026-07-28 line; absence of any such record by freeze =
  right-censored.
- Dependent repo: first commit on the default branch that bumps an official SDK dependency to a
  stateless-supporting release (per-SDK mapping table built at Gate 2, frozen before RQ1 runs).
**Narrative:** fast absorption is a finding (young ecosystems can hard-cut); slow/bimodal
absorption is a finding (protocol pinning risk). No outcome is null.

### RQ2 — Migration strategy taxonomy
**Estimand:** frequency distribution over a closed strategy taxonomy, seeded (frozen seed set):
{hard cut, dual-stack via parallel package line (e.g., `server-legacy`), dual-stack via runtime
negotiation, version-gated code paths, wrapper/adapter, no action}. Taxonomy may EXTEND during
coding (new categories logged) but seeded categories may not merge/rename.
**Unit:** SDK (all 9, census) + stratified sample of dependent repos (Gate-1 sets n and strata).
**Coding:** two raters, Cohen's kappa reported; kappa >= 0.6 required or codebook is revised and
re-coded (revision counts as a logged deviation).

### RQ3 — Failure modes
**Estimand:** taxonomy + frequency of migration-attributed failures in issues/PRs across
modelcontextprotocol/* and the dependent-repo sample, POST epoch; plus time-to-resolution.
**Attribution rule (frozen):** an issue/PR is migration-attributed iff it (a) references the
2026-07-28 spec/protocol version, stateless(ness), or a named migration artifact
(e.g., server-legacy), AND (b) reports breakage/incompatibility (not feature requests).
Two-rater coding on a sample; single-rater with audit sample if kappa >= 0.75 on the sample.
**Known bias (declared):** issue text is public-report data; silent failures invisible. Stated as
a threat, not fixed.

### RQ4 — Ecosystem displacement
**Estimand:** npm daily download share of legacy vs stateless package lines
(`@modelcontextprotocol/server-legacy` vs `@modelcontextprotocol/server`, plus sdk pre/post
version split if npm per-version stats allow — else declared unavailable), and registry
version-publication rate per week around RELEASE (interrupted time-series, level+slope,
2-week bins, +/- 8 weeks).
**Narrative:** legacy-line persistence quantifies the long tail; a publication-rate spike (or
absence) characterizes registry-side response. Either direction publishable.

## Sample frames (frozen)
- SDKs: census of the 9 official SDK repos (typescript, python, go, rust, java, kotlin, csharp,
  ruby, php).
- Registry: all server version records in our daily dumps (started 2026-08-21) UNION records
  reconstructable from live `_meta` timestamps at freeze. Deletions measurable only from
  2026-08-21 onward — SCOPE LIMITATION, stated.
- Dependent repos: reuse arXiv:2607.10123's verified dataset as the base frame if its release
  artifact is usable (decide at Gate 1; if unusable, replicate their GH-API pipeline with our
  verification). Exclusions: forks, archived-before-RC, educational/tutorial per their labels.
- Downloads: the 7 npm packages in collect_snapshot.py + pypi `mcp`.

## Denominator discipline (response to arXiv:2608.00997 reconciliation duty)
Every rate reports its denominator class explicitly: distinct servers vs version records vs
active servers (>=1 version update in trailing 90 days). Our counts must reconcile with
2608.00997's published counts within stated definitional differences, or the discrepancy is
investigated and documented before any RQ1 number is trusted.

## Analyses (primary; anything else = exploratory)
- RQ1: Kaplan-Meier with right-censoring at freeze; per-population medians with bootstrap CIs.
- RQ2/RQ3: descriptive distributions + kappa; no significance tests.
- RQ4: interrupted time-series (OLS with level+slope terms, HAC errors); plus plain difference
  of 4-week means pre/post as the robustness twin.
- Robustness (pre-committed): RQ1 repeated under "active servers" denominator; RQ4 repeated
  excluding the release week (announcement spike).

## Data freeze & artifact
Freeze target 2026-11-15 (movable EARLIER only, never later, without a logged deviation).
**[2026-08-21, D-003: operational freeze set to 2026-10-10 for the Oct 23 MSR/SEIP deadline —
an earlier-only move, no deviation.]**
Release artifact: registry snapshot series (redacted per registry ToS if needed), adoption-event
tables, coding sheets, analysis code — assembled anonymously for double-blind venues.

## Venue (from PLAN.md, subject to CFP verification)
ICSE-SEIP 2027 primary; TMLR fallback (submit <= Nov 2026 for pre-freeze decision);
MSR 2027 mining-track stretch.

## Threats declared up front
Left-censoring (repos born post-RC excluded from RQ1 dependent-repo curve); GitHub-visible
ecosystem only; download counts include CI/bots (mitigation: share-of-line, not absolute);
registry deletions unobservable before 2026-08-21; LLM-assisted coding (if used for scale in
RQ2/RQ3) always behind human-rater agreement gates.


---
## A4 SUPERSESSION NOTE (added 2026-08-25; frozen text above unedited)
The two-rater coding provisions above are superseded by DEVIATIONS.md AMENDMENT A4
(frozen 2026-08-22): RQ2 = frozen mechanical artifact detectors with author-validated
precision/recall; RQ3 = descriptive characterization; solo authorship final.
