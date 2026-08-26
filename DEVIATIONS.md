> NOTE (package copy): personal names/handles/strategy context mechanically redacted; working-tree original is the private record.

# DEVIATIONS from PREREGISTRATION.md — Paper 5 (C1)
Every deviation from the frozen pre-registration is logged here with rationale, per the
prereg's own rule. The paper reports all entries transparently.

## DEV-1 · 2026-08-21 · Registry adoption event redefined (flagged by panel PA-8/PC-5)
- **Frozen text (prereg RQ1):** "Registry server: first version record with publishedAt >=
  2026-07-28 whose declared protocol version (or schema reference) is the 2026-07-28 line."
- **Problem:** live data shows registry records declare NO protocol version; `$schema` is the
  record-format version (five lines observed, none 2026-07-28-era). The frozen definition is
  unmeasurable as written.
- **Deviation:** registry adoption event redefined via package→SDK-dependency resolution
  (GATE1-MEASUREMENT-DESIGN.md MD-1), with remotes-only servers as a separate stratum.
- **Why this is a deviation and not an operationalization:** the signal source changed
  (record field → cross-ecosystem join), changing measurement error properties and coverage.
  Initially mislabeled [REFINE] in the v0.1 design doc; the Gate-1 panel (P-A finding 8,
  P-C finding 5) corrected the classification. Logged same day.
- **Status:** folded into Amendment A1 (below).

## AMENDMENT A1 · 2026-08-21 · **FROZEN 2026-08-21** (with design v0.2; closure check
## REVIEWS-gate1-closure-check.md: 17 CLOSED / 1 PARTIAL→fixed / NEW-1..7 all remediated)
Adopted from the Gate-1 panel's consolidated verdict:
1. Estimand split (unconditional; the C4 probe spike PASSED — 30/50 negotiated, results in
   gate1_probe_results.json): "capability adoption" (static, artifacts) AND "behavioral
   adoption" (live initialize-probe negotiation on sampled https remotes; n=400 + frozen n=50
   pilot; biweekly waves to freeze). Divergence between the two is a reported result.
2. RQ1 headline reporting = FOUR-denominator table (D_all=23,931 / D_active / D_resolvable /
   D_probeable) with the D_resolvable stratum bias stated (94.4% stdio); remotes-only stratum
   (11,823) is a first-class population measured by the probe.
3. NEW explanatory layer (was PC's single highest-value addition): Cox proportional-hazards
   time-to-capability-adoption model + strategy-choice model; covariates (FROZEN): SDK language
   ecosystem; publisher type (org vs individual); pre-RC activity (version-publication rate);
   transport type; repo age; dependency depth on MCP SDK (direct vs transitive). [Panel's
   illustrative "SDK maturity" realized as ecosystem + repo age — acknowledged per closure
   check.] Schoenfeld PH checks; stratified Cox on violation. Direction expectations recorded,
   two-sided tests regardless.
4. RQ1 reporting quantile: 25th percentile pre-committed as primary (median may be undefined
   in the 10.5-week window); interval-censored sensitivity analysis (probe waves are natively
   interval-censored).
5. Active vs passive adoption split for ranged dependents (PA-2): active = manifest commit;
   passive = range-eligible without commit; both reported, never merged.
6. Registry cohort partition (NEW-2): pre-RC incumbents (10,040) / RC-era joiners (8,704) /
   post-release entrants (5,187); time origin max(first_pub, 2026-07-28); pooled + stratified
   KM. Monorepo headline dedup at repo level (PA-3).

## AMENDMENT A2 · 2026-08-21 · **FROZEN 2026-08-21** — publisher-level clustering (P-C v2 NR-1)
- **Trigger (verified in raw wave-1 data before any analysis):** 36/43 (84%) of servers
  behaviorally negotiating 2026-07-28 share ONE publisher namespace (io.github.pipeworx-io);
  29/87 of the 2025-11-25 line share io.github.mcp-dir. Server-level independence assumptions
  are untenable in this ecosystem.
- **Frozen fixes, effective before probe wave 2 and all analysis code:**
  1. ALL adoption shares reported DUALLY: server-level and publisher-level (unit = registry
     namespace prefix; mapping rule frozen: name up to first '/').
  2. Publisher-concentration statistic (share of adopters from top-1/top-3 publishers + HHI)
     reported alongside every adoption number.
  3. Cox models fit with publisher-level clustering (shared frailty by publisher, or robust
     clustered SEs if frailty fails to converge — choice recorded, both reported if they differ).
  4. Platform-mediated adoption (one publisher migrating many servers at once) is REPORTED AS A
     FINDING about how this ecosystem actually migrates — not treated as a nuisance.
- **Also logged per P-C v2 PC-5(b):** prereg RQ4 bins = 2-week (unchanged; design v0.2 §7 made
  explicit). No deviation — clarification only.

## AMENDMENT A3 · 2026-08-22 · **FROZEN 2026-08-22** — RQ4 model respecification (methods review M-1/M-2)
- **Trigger:** the pre-registered placebo DIAGNOSTIC fired at the non-event date (level −795,
  t=−3.47 on 2026-06-15, preliminary run): the registry's secular growth is steep (2-week
  volumes 4,019→9,788 across the window) and a LINEAR-trend counts ITS misreads growth as
  effects. This is the placebo doing its pre-registered job — the model, not the data, changes.
- **Frozen respecification (before freeze, before any release-effect estimate):**
  1. PRIMARY: Negative-Binomial (log link) segmented regression on WEEKLY counts — the
     no-effect null is exponential growth; level and slope effects are multiplicative.
  2. Robustness twins: log-OLS with spline trend; original linear spec reported in appendix
     for transparency.
  3. Placebo gate unchanged and now TWO placebos: 2026-06-15 and a clean pre-RC date
     2026-05-04; any release-effect claim must show null at both.
  4. Release-week exclusion robustness retained.
- Prereg §RQ4's linear OLS is superseded; deviation reported transparently in the paper
  (the placebo-triggered respecification is itself reusable methods guidance).

## AMENDMENT A4 · 2026-08-22 · **FROZEN 2026-08-22** — RQ2/RQ3 re-scoped to mechanical detection (authorial-independence decision; 3-specialist consult, unanimous C > B > A)
- **Trigger:** author directive — the paper must have no external-human dependency. Consults:
  draft/CONSULT-rq23-msr-pc.md (risk-adjusted acceptance C ~48-55% > B ~38-47% > A ~30-38%),
  draft/CONSULT-rq23-methods.md (C is a valid CONSTRUCT REALIGNMENT, not a rigor discount, iff
  conditions below), gate2/DETECTOR-SPEC.md (implementable, ~23 person-days, freeze
  `detectors-frozen-2026-09-19`).
- **Frozen re-scope:**
  1. RQ2 becomes ARTIFACT-SIGNATURE detection: {DS-P parallel package line, DS-N runtime
     negotiation, VG version-gated paths, HC cut-signature, VEN vendored, NS no-signature
     residual}. Detectors certify PRESENCE ONLY; all prevalences phrased as lower bounds;
     the NS residual is never glossed as "no action."
  2. Detector discipline: dev-set-only iteration → single dated freeze commit
     (detectors-frozen-2026-09-19) BEFORE the production run; golden test set; precision
     validation 50 hits/detector with Wilson CIs, 80% precision floor (below floor → detector
     reported as exploratory); 200-repo negative audit characterizes NS; author validation
     labeling ~24h total (author-as-validator is in-scope for solo authorship).
  3. RQ3 demoted from coded taxonomy to DESCRIPTIVE corpus characterization: volumes,
     timing, resolution times, label distributions, quote-anchored exemplars. Claims shrink
     accordingly ("what maintainers reported," not "the taxonomy of failures").
  4. Triangulation (methodologist's free assets): DS-N criterion validity via the live probe
     panel — probe waves 3+ ALTERNATE the offered protocolVersion (2026-07-28 / 2025-11-25)
     on split halves to observe negotiation behavior directly (probe-wave amendment,
     frame unchanged); member-checking via PUBLIC maintainer statements (quoted, linked).
  5. Rationale codes R1-R7 retained but QUALITATIVE AND UNQUANTIFIED (no prevalence claims).
  6. ~~Co-author upgrade ladder~~ **CLOSED EARLY 2026-08-22 by author directive ("no co author").**
     C stands alone; solo authorship is final. No second-rater layer will be added regardless
     of timing. (Ladder originally open to 2026-09-12; closed 21 days early, logged here to
     keep the no-post-hoc property.)

## AMENDMENT A5 · 2026-08-22 · **FROZEN 2026-08-22** — joint panel + probe-design hardening (zero-context review round 1, W1≡V2 convergent)
- **Trigger:** two independent zero-context reviewers found the headline capability-vs-behavior
  GAP is not measured on shared units (capability: SDKs/repos/registry entries; behavior:
  probed remotes — different populations). Fix available before wave 2; frozen now.
- **A5.1 JOINT PANEL:** second frozen probe frame = ALL pkg+remote-stratum servers with https
  remotes (population 1,299; frame built from the 2026-08-22 dump, seed 47, frozen at first
  use). For each: capability adoption via package→SDK resolution AND behavioral adoption via
  probe, PER SERVER. The paper's headline gap statistic = divergence WITHIN this panel;
  the n=400 general panel remains the ecosystem-wide behavioral series.
- **A5.2 panel/experiment split clarified (W5):** in ALL waves the EVEN half of each frame is
  always offered 2026-07-28 (the longitudinal series — comparable across waves); from wave 3
  the ODD half alternates offers (the negotiation experiment). No mid-series design break.
- **A5.3 MNAR bounds (W4≡V5):** auth-walled non-response handled by pre-committed worst-case
  bounds (all-adopters / none-adopters) reported alongside point estimates, plus observable-
  covariate comparison (registry metadata exists for responders AND auth-walled).
- **A5.4 detector recall (W6≡V7):** the 200-repo negative audit doubles as a recall estimate
  (random sample labeled for ALL signatures, not only NS); recall reported with Wilson CIs
  next to precision; dev/validation split discipline stated in-paper.
- **A5.5 freeze-day refresher cross-section (V10):** one-off n=200 sample from servers FIRST
  SEEN after the panel frames froze, probed once at freeze — quantifies panel aging against
  the growing registry.
- **A5 ADDENDUM (2026-08-23, author challenge "why not now"):** the joint panel's BASELINE
  wave was run 2026-08-23 (not waiting for the Sep-4 cadence date — the wait was convention,
  not design; an earlier baseline adds a timepoint at zero cost). General n=400 panel remains
  exactly on its biweekly cadence. Baseline: 1,232 probed → 495 negotiated (40%), 376
  auth-walled; negotiated versions: 2025-11-25 65% · 2026-07-28 9.5% · older 25%.
- Zero-spend items (draft text): stale kappa threat line replaced; priority claims scoped
  ("to our knowledge", "at least one official SDK"); registry-event sentence added to §4.

## AMENDMENT A6 · 2026-08-23 · **FROZEN 2026-08-23** — dependent-repo adoption-event sampling design
- **Trigger:** manifest HISTORY extraction (needed for active-adoption event dates) is
  API-infeasible as a census over 84,972 repos; the prereg left dependent-repo n to Gate-1/2.
  Frozen before any extraction runs.
- **Design:**
  1. **Time-to-adopt sample (KM/Cox):** stratified random sample, seed=53, drawn from the
     hydrated fork-free frames EXCLUDING archived and deleted repos: maven = census (all
     eligible ≤666) · go = 800 · rust = 800 · npm = 2,000. Strata proportional within
     ecosystem by owner type (User/Organization). Total ≈ 4,266 repos.
  2. **Event extraction, two stages:** stage 1 = full commit-date history of the matched
     manifest path + CURRENT manifest content (per repo); stage 2 = manifest content at the
     commits inside the RC→freeze window only (bounded walk) to locate the first
     stateless-supporting requirement change (active adoption) per design §3 rules.
  3. **Prevalence cross-section:** at freeze, CURRENT-manifest state for the FULL frames
     (single-file fetch per repo, batched) gives full-population passive/current-requirement
     prevalence — census where cheap, sample where expensive.
  4. Right-censoring at freeze; left-censoring rules per design §5 unchanged.

## AMENDMENT A7 · 2026-08-23 · **FROZEN 2026-08-23** — the gap estimand, named and defined (ZC round-2 A#1)
- **Name:** the **deployment gap** Δ(t).
- **Definition (frozen before any post-baseline joint-panel wave):** within the joint panel
  (1,232-server census, frame frozen 2026-08-23), at wave time t:
  Δ(t) = P[capable(s,t)] − P[negotiates-2026-07-28(s,t)], computed over the RESPONDING
  subset with capability resolvable; reported with (a) paired counts (capable & negotiating /
  capable & not / not-capable & negotiating / neither), (b) McNemar-style discordance, and
  (c) MNAR bounds per A5.3 (auth-walled treated as all-negotiating / none-negotiating).
- **Publisher-level twin (primary per ZC-2A):** Δ_pub(t) computed over publishers (a publisher
  is capable/negotiating if ANY of its panel servers is), with the same bounds.
- **Trajectory claim discipline:** "the gap closes/persists" requires the same sign in both
  server- and publisher-level Δ across ≥3 waves; otherwise reported as wave-wise description.
- Capability(s,t) = A6/DEV-1 rules (package→SDK resolution, version admitted at t).
- CODING-PROTOCOL.md §RQ2/RQ3 superseded accordingly (marked in place).
- [REDACTED 2026-08-25 for the public log: a personal note about a previously-considered
  co-author introduction — methodologically void since A4 froze solo authorship; removed as
  both an anonymity and a privacy matter. Redaction itself logged, per log discipline.]

## AMENDMENT A8 · 2026-08-25 · **FROZEN 2026-08-25** — behavioral instrument re-specified on server/discover (devdsk v0.12 review P0-1; CONSTRUCT-VALIDITY, near-fatal)
- **Trigger (verified against the primary source by the authoring session — not taken on faith):**
  the official 2026-07-28 changelog states verbatim "Make MCP stateless: **remove the
  initialize/notifications/initialized handshake**" and "Add **server/discover: servers MUST
  implement this RPC**... or use it as a backward-compatibility probe on STDIO". Fetched from
  modelcontextprotocol.io/specification/2026-07-28/changelog, 2026-08-25.
- **The flaw:** the wave-1/2 + joint-baseline probe used the `initialize` handshake. A FULLY
  migrated server does not implement `initialize` → the instrument classifies the most-migrated
  servers as NON-adopters. Behavioral adoption is systematically UNDERstated and Δ is INFLATED
  in exactly the hypothesized direction — a measurement artifact was manufacturing the headline.
  The 43 "new-revision negotiators" are DUAL-STACK/backward-compatible deployments (still
  implement the removed handshake AND advertise the new version), not full adopters.
- **Re-specification (FROZEN, effective before detector-freeze 2026-09-19):**
  1. Behavioral probe rebuilt on `server/discover` (MUST-implement on the new revision → clean
     positive discriminator) + per-request `_meta io.modelcontextprotocol/protocolVersion`;
     `UnsupportedProtocolVersionError` is an INFORMATIVE response, not a failure.
  2. Behavioral states, mutually exclusive: `new-only` (answers server/discover, no initialize) ·
     `dual-stack` (both) · `legacy-only` (initialize only) · `unreachable` · `auth-walled`.
     The old design could not express `new-only` — the true full-migration state.
  3. ALL behavioral numbers re-derived. Wave-1/2 + joint-baseline `initialize` data are relabeled
     as DUAL-STACK PREVALENCE (a real but narrower construct), not adoption; the paper says which.
  4. A4's alternating-offer probe amendment was `initialize`-era → re-specified against the new
     instrument; superseded portions marked.
  5. §3 and §9 state plainly that an initialize-based probe is blind to full migration, that this
     was found in review and corrected, and that server/discover being mandatory makes the
     corrected instrument STRONGER (required RPC vs handshake inference).
- **A8 ADDENDUM (2026-08-25, same-day, before wave 2): instrument v0.3 — verified positives.**
  The v0.2 probe counted ANY non-null JSON-RPC result to `server/discover` as a positive
  (found in the v0.15 crew review, K1). v0.3 adds: (a) the per-request `_meta`
  io.modelcontextprotocol/protocolVersion stamp item 1 already specified but v0.2 omitted;
  (b) a same-session NEGATIVE CONTROL — a nonsense method sent only after a discover result;
  genuine implementations must reject it (JSON-RPC/HTTP error), permissive echo endpoints
  cannot count; (c) A5.2 arm logic implemented (even half always new revision; odd half
  alternates from wave 3), arm + offer recorded per result; (d) max three requests per server
  per wave (was two). Wave-1 positives were REVALIDATED same-day with v0.3
  (probe_v2_validation_2026-08-25.json): 14 of 21 verified; 4 echo artifacts retired
  (including one publisher's entire 3-server general-panel "fleet"); 3 unverifiable at
  revalidation and conservatively downgraded. All wave-1 analysis uses verified states only.
- **Net:** this finding improves the paper. But it invalidates every behavioral number collected
  so far; the behavioral series effectively restarts on the new instrument. Impact on the Oct-10
  freeze timeline assessed next.
