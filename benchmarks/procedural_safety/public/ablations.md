# Synthetic procedural software evaluation

**SYNTHETIC SOFTWARE TEST. Real procedural video benchmark: NOT RUN.**

These numbers come from the native saved inference run. This public projection retains the measured values and replaces local path references; [PROVENANCE.json](PROVENANCE.json) links it to the original run and source hashes.

18 unique generated clips; 54 repeated-policy rows. Shared board grammar is integration coverage, not industrial generalization.

| Policy | Exact final status | False clears | Timely supported error clips | Processing p50/p95 ms | Mean extra frames |
|---|---:|---:|---:|---:|---:|
| single | 15/18 | 0 | 5/7 | 215.32649999426212 / 289.43716499634263 | 0 |
| random | 15/18 | 0 | 5/7 | 237.90184999234043 / 259.8559549849597 | 2 |
| agent | 15/18 | 0 | 5/7 | 240.71379999804776 / 249.93879501125775 | 2 |

## Paired deltas versus single

- random: exact-status delta +0.0000; false-clear delta +0. Budget caps match; actual actions used are shown above.
- agent: exact-status delta +0.0000; false-clear delta +0. Budget caps match; actual actions used are shown above.

All successes, misses, false passes, false holds, early/late warnings and runtime failures remain in results.csv and gallery. No test labels or timing entered model inference. No thresholds were changed after scoring. Fixed-rate synthetic source-frame gaps are not a variable-frame-rate camera test. Real/staged-video results remain NOT RUN.
