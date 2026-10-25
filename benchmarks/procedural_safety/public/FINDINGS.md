# Synthetic procedure run: findings and limits

This is **SYNTHETIC SOFTWARE TEST** evidence, not filmed staged assembly or industrial performance. There are 18 held-out generated clips, 60 decoded frames each, and 54 repeated-policy runs. All policies use identical video bytes, recipe, calibration, stable-observation thresholds and maximum two additional replay frames. Train/validation/test seeds differ but share one drawing grammar. No test results were used to change thresholds, fixtures or engine logic.

## Source and public projection

This page summarizes the native saved inference run. The public `results.json`, `results.csv` and `cases/` files are projections of that run: local filesystem references were replaced with relative paths; observations, events, decisions and timings are retained. [PROVENANCE.json](PROVENANCE.json) records original and public hashes, the five frozen source hashes and the original verification receipt. Raw run manifests, source snapshots and environment-failure logs remain in the retained build-host evidence rather than this public directory.

## Measured outcome

All three policies produce the same final decisions: 15/18 exact expected statuses, zero false PASS decisions, five of seven timely supported matching error clips, two normal false HOLD decisions among four uncomplicated normal clips, and one wrong-order clip held for review rather than explicitly rejected. No runtime failures. The error-type confusion and individual outcomes are in `results.json` and `results.csv`.

There is **no observed agent accuracy advantage** over either the base or seeded random policy. Single uses zero extra frames; random and agent each use two per clip. Full offline video processing including evidence writes has p50/p95: single 215.3265/289.4372 ms, random 237.9018/259.8560 ms, agent 240.7138/249.9388 ms. These are shared-host repeated runs on six-second fixed-rate clips, not live capture latency or isolated throughput capacity.

## Failures retained

1. `clip_009`, fast normal assembly: expected PASS, all policies HOLD with PARTIAL_OBSERVATION. The first component appears at 400 ms; the base sampling cadence cannot establish three temporally separated empty-board observations first. Agent spends its extra frames at 100 and 200 ms, but the 100 ms frame does not satisfy the frozen minimum 150 ms support gap. Empty-start verification never becomes true.
2. `clip_013`, cover-before-spacers: expected explicit REJECT, all policies HOLD with PARTIAL_OBSERVATION and no supported ORDER_VIOLATION event. Cover appears at 600 ms before empty-start confirmation. The guard abstains instead of inventing certainty about history. This is a missed specific error, even though it avoids a false PASS.
3. `clip_025`, blur then recovery: expected PASS, all policies HOLD with PARTIAL_OBSERVATION. Degraded observations create a permanent history gap; later clean assembly evidence does not automatically repair that history. No recovery success is claimed.
4. `clip_023`, unknown purple component: final HOLD is correct, but no explicit UNRECOGNIZED_COMPONENT event is emitted. It remains one of the two missing matching error-type findings; generic uncertainty is not relabeled as specific detection.

Agent extra-frame choices for the three status failures are the same first 100/200 ms frames, before later ambiguity. The existing policy spends its budget on initialization. This trace supports investigating action timing and initialization/recovery design with a new predeclared development protocol; it does not justify retuning or replacing this held-out score.

Wrong-part errors first receive supported warnings at 1500 ms (700 ms after synthetic onset and 500 ms before declared synthetic boundary). Corrected wrong-slot error is supported at 2700 ms (600 ms after onset, 800 ms before declared boundary), and the correction remains in the timeline. Missing-screw detection occurs at the final checkpoint (5700 ms); no preemptive boundary or onset is asserted for that final-only condition. Median lead among the three detected cases with boundaries is 500 ms; two observable boundary cases lack a matching warning. These are generator-timed illustrations, not human intervention or accident-prevention measurements.

## What the software checks establish

- Nine focused tests passed in the application environment. They include runtime-label allowlisting, opening annotations only after all predictions are persisted, refusal to replace frozen metadata, actual support-ID validation, retaining late transient misses and runtime errors in denominators, deterministic rendering, and geometric/color fixture checks.
- All 26 generated AVI files (four train, four validation, eighteen test) were decoded with 60 frames each, totaling 1,560 frames. Every frame visibly carries the synthetic disclosure except exact repeated-frame repeats, which preserve the same stamped source image.
- Prediction provenance records source SHA, OpenCV 5 version, recipe SHA, analyzed frame IDs and actual saved overlays. The gallery retains every policy/clip, including both successes and failures.

## Acquisition and operational blocks

`real_video_benchmark.status = NOT_RUN`: no matched authorized physical tabletop recording, alternative camera view or human-reviewed onset/boundary set was supplied. Synthetic software cases do not satisfy the brief's request for twelve physically recorded videos. No Assembly101, LOCO, employee behavior, fatigue, machinery actuation, physical safety certification, real operator burden, live camera-to-alert latency, AWS safety-video latency or interval IoU is measured here. The nominal 300 final false HOLD clips per synthetic replay hour is merely two false final decisions divided by 24 seconds of generated normal footage; it is not a credible real-world false-alarm estimate.

## Reproduction

Use the pinned application environment (Python 3.14.6, OpenCV 5.0.0, NumPy 2.3.3, Pydantic 2.12.5) and set `PYTHONPATH` to the backend package directory. Run:

```text
python -m reflex_safety.fixtures --root <new-fixture-folder>
python -m reflex_safety.benchmark --fixtures <fixture-folder> --output <new-empty-run-folder>
```

Fixture paths are local input-index metadata and must be regenerated for a different machine. Generator metadata is immutable within an output directory. Benchmark refuses a nonempty run directory. Runtime labels are read separately only after all predictions. In the retained native run, exact sources are copied under `source_snapshot`, and `run_manifest.json` records their pre/post hashes. The public projection exposes the frozen hashes in `PROVENANCE.json`; it does not include those raw directories. Regeneration executes the current source and produces a new run, not the original run receipt.

The retained build-host logs record that the first launch used a separate benchmark environment lacking Pydantic and failed before inference; `benchmark-full-run-r1.log` preserves the exception. The rerun used the existing application environment. Initial pytest temporary-directory setup failed under the sandbox default; selecting a writable workspace temporary folder resolved the three setup errors, and all nine focused tests passed. These environment failures were not detector scores and were not silently counted as passes.
