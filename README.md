# The deployment gap — artifact

Instruments, data and analysis code for an empirical study of how a young AI-protocol
ecosystem absorbs its first breaking change: the Model Context Protocol (MCP)
statelessness revision released 2026-07-28.

The study pairs two measurements over the **same units at the same time**:

- **capability** — what a published artifact *could* negotiate, resolved version-aware from
  registry packages and their SDK dependency requirements;
- **behavior** — what a running deployment *actually* negotiates, measured by a live probe.

Their difference is the *deployment gap*.

Preprint: [`paper/arxiv/main.pdf`](paper/arxiv/main.pdf)

## Status: wave-1 snapshot, superseded

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22181811.svg)](https://doi.org/10.5281/zenodo.22181811)

This repository is the **wave-1 (August 2026) artifact** and is kept as the record of that
release. The study's current, archived artifact (instrument correction, validation bench across
five official MCP SDKs, per-endpoint records, frozen frames, all analysis scripts, the
pre-registration and the deviation log) is on Zenodo:
**DOI [10.5281/zenodo.22181811](https://doi.org/10.5281/zenodo.22181811)** (v046, 2026-09-03),
replication package for *One Release, Two Answers: Call-Site Dependence in Model Context
Protocol Revision Instruments*. Cite that DOI, not this repository (see `CITATION.cff`).

The original wave-1 status note follows unchanged.

This is a **wave-1 release**. Numbers marked `[PF]` (pending freeze) or `[PW]` (pending probe
waves) in the paper are regenerated at the **2026-10-10 data freeze**. The paper's own
inference rule requires ≥3 waves agreeing in sign at both units of analysis before any
directional claim about the gap is licensed; at wave 1 the missingness bounds straddle zero,
so the gap's sign is **not identified** and the paper does not claim it is.

What is already settled and does not depend on further waves:

- the **instrument correction**: a probe built on the legacy `initialize` handshake — which the
  revision deletes — measures dual-stack prevalence, not adoption. 41 of 43 apparent
  "new-revision negotiators" under the old instrument were legacy-only servers answering a
  removed handshake;
- the **negative control**: permissive echo endpoints answer any method, including a nonsense
  one. Adding a same-session negative control retired 4 of 21 wave-1 positives, including one
  publisher's entire three-server fleet;
- the **SDK census**: version names are not adoption dates. One official SDK ships a `2.0.0`
  release with no support for the new protocol.

## Layout

| Path | Contents |
|---|---|
| `paper/arxiv/main.pdf` | the preprint |
| `instruments/probe_v2.py` | live probe, v0.3 — per-request `_meta` protocol version, same-session negative control, `revalidate` mode |
| `instruments/resolve_joint_capability.py` | version-aware capability resolver (T1 direct / T2 one-hop / T3 artifact scan) |
| `instruments/derive_capability_state.py` | capability state for dependent repositories |
| `instruments/detectors/` | frozen capability detectors + `golden_tests.py` (16 known-answer cases) |
| `data/` | mapping table, SDK census, banked manifests, dependency frames, hydrated repository metadata, adoption events, probe waves, wave-1 revalidation record |
| `analysis/` | survival (Kaplan–Meier), Firth-penalised Cox, log-rank, negative-binomial ITS — scripts and emitted results |
| `reproduce.sh` | regenerates every reported number; prints PASS / SKIP / FAIL per step |
| `PREREGISTRATION.md` | the registered plan (frozen 2026-08-21) |
| `DEVIATIONS.md` | every amendment to that plan, in order |

## Reproducing

The golden suite is self-contained and needs no network:

```sh
cd instruments/detectors && python3 golden_tests.py     # 16/16 expected, exit 0
```

Everything else:

```sh
./reproduce.sh
```

Each step prints `PASS`, `SKIP` (a required input is absent from this checkout) or `FAIL`.
Probe waves regenerate only with network access, and re-probing a live ecosystem months later
will not reproduce a past wave — the banked wave files in `data/` are the record.

Analyses need `numpy`, `scipy`, `pandas`, `statsmodels`, `lifelines`.

## Pre-registration and deviations

The plan was registered before the analysis ran and is frozen. `DEVIATIONS.md` records every
amendment against it, including the ones that changed the study's scope — most consequentially
A4, which re-scoped RQ2 to mechanical artifact-signature detection and made authorship solo.
Both files are included so that every reported number can be checked against what was
registered rather than against what the results made convenient.

## Ethics

Probing targets only endpoints that publishers advertised in the public registry, at low volume,
with an identifying user agent. Registry metadata and repository manifests are public. No
credentials were used, no authentication was bypassed, and auth-walled servers are recorded as a
bounded stratum rather than probed further.

## Licence

MIT — see `LICENSE`.
