# Current project status

Presentation reviewed 27 October 2026. Scientific results below remain the frozen 24–25 October study; this page does not create new experiment results.

[README](../README.md) · [Reviewer tour](REVIEWER_GUIDE.md) · [Setup](GETTING_STARTED.md) · [Technical report](REFLEX_YMCA_PPT_INTELLIGENCE_PUBLIC.md)

## Capability map

| Area | Implemented behavior | Delivery / evidence boundary |
| --- | --- | --- |
| Inspection Studio v1 | Real candle/cashew photographs, normal-patch scores, source images, heatmaps, overlays, trace, separate review and exports | Public AWS demo; curated examples plus separate offline image evaluation |
| Adaptive v2 | Quality/review routing and at most one separately calibrated crop of the original photograph | Local candidate; **release held** |
| Safety Station | Decoded video/supplied-frame observations, manual planar calibration, temporal recipe checks, evidence and advisory review | Local teaching-panel prototype; evaluated clips are generated software tests |
| Pair alignment | Optional ECC affine reference comparison with rejection of unstable alignment | Separate utility; downstream detection benefit has not been established |
| Physical cameras / factories | Interfaces and future validation work are distinct from measured field operation | Physical-camera, independent factory-lot and real procedural validation remain open |

There is no LLM deciding the inspection, automated machinery control or employee monitoring. Deterministic image-quality/score/map outputs change later bounded actions. The demonstration does not fake successful tool responses. The generated plates and procedure clips are explicit software fixtures, not substitutes for real-world evidence.

## Why v2 is held

The study contains **860 unique real VisA images**: 350 exposed replay, 255 diagnostic development and 255 custom final images across five categories. Eleven fixed methods/arms over eight groups produce 88 rows, not 9,460 independent images.

| Population | v1 detected / defects | Primary v2 detected / defects |
| --- | ---: | ---: |
| Reused candle/cashew replay: 350 cases | 112/200 | 155/200 |
| New-category final: 255 cases | 92/150 | 105/150 |

In replay, v2 automatically clears **41/200 defects** and leaves **4 defects under review**. In final, it automatically clears **42/150 defects**, with **3 defect reviews and 8 normal reviews**. The frozen release flag is `HOLD_CANDIDATE_LOCAL`.

Reviews are unresolved outcomes, not successful detections. Among 105 final normal images, v2 produces 14 false alerts versus v1's 9. Equal-category final image AUROC falls from **0.852044 to 0.840978**. Capsules falsely clears **34/50** final defects. The upstream PatchCore reference has higher image AUROC in all eight groups, with different backbone, memory and preprocessing settings; it is not a controlled architecture-only comparison.

The policy triggers one detail crop on **46/860** images. The matched controls show that the lower review boundary accounts for the reduced automatic false clears; crop selection alone does not explain that reduction. General superiority over random crops is not established.

Dedicated Fargate handler p95 increases **1070.469 → 1256.220 ms** and peak observed process RSS increases **43.90%**. The run used 300 measured requests/version on a 1-vCPU/2-GiB task. This is not external network latency, saturation capacity, an actual bill or a compute-saving result.

Sources: [release assessment](../benchmarks/anomaly_v2/RELEASE_ASSESSMENT.md), [all fixed results](../benchmarks/anomaly_v2/ALL_RESULTS.csv), [policy controls](../benchmarks/anomaly_v2/AGENT_POLICIES.csv), [reference comparison](../benchmarks/anomaly_v2/REFERENCE_COMPARISON.md) and [numeric ledger](../benchmarks/intelligence_20261025/BENCHMARK_LEDGER.csv).

## Separate procedure evidence

The test population is **18 generated clips**, replayed under three policies: 54 repeated policy runs. Each policy gets **15/18** exact final statuses and **5/7** timely supported error clips. Two of four uncomplicated normal clips remain HOLD. There is **no observed agent accuracy gain**. No physical procedure dataset was evaluated; gated Assembly101 annotations are not a video benchmark. [All cases and failures](../benchmarks/procedural_safety/public/FINDINGS.md).

## Verification and presentation status

The 25 October audit recorded 138 Python, 14 frontend, 5 markup and 20 separate API checks. The source-only export has its own narrower receipt. Counts describe tested software behavior, not scientific accuracy or a fresh install. [Historical check evidence](verification/PUBLIC_SOURCE_VERIFICATION.json).

The 26 October AWS screenshots show actual real-image runs. The submitted [OpenCV project](https://devpost.com/software/reflex-xqn8i7) embeds the [team video](https://youtu.be/WvnKxOTxkvw). This supersedes the earlier submission-pending language in the preserved [25 October snapshot](../STATUS.md); that file remains a historical record. The video and project page do not establish factory readiness or deployment of v2/Safety Station.

Historical custom AU-PRO values are invalid. The [correction](../benchmarks/anomaly_v2/METRIC_CORRECTION.md) and [evaluator addendum](../benchmarks/anomaly_v2/PROTOCOL_EVALUATOR_ADDENDUM.md) take precedence over obsolete values in earlier documents. Publisher byte parity remains a separate open limitation.

## Next evidence gates

Acquire authorized item/lot-separated captures and real procedure recordings; freeze a new protocol; compare static, review-only, chosen and random policies under matched evidence and timing budgets. Measure operator burden before claiming ROI. Isolate native video decoding and add appropriate shared persistence/access controls before any public extension deployment. These are planned gates, not completed product capabilities.
