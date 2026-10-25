# Pre-evaluation accounting addendum

Written on 25 October 2026 before any v2 accuracy evaluation or final-label access.

The primary method, nine arms, three seeds, normal-only thresholds and review budget stay as predeclared. All five categories additionally receive the unchanged legacy OpenCV5 spatial median/MAD baseline fitted on exactly the same normal fitting/calibration members. Its internal120x90 grid differs from the deep256 input; this is disclosed rather than called a backbone-matched ablation.

The evaluator also records primary native-coordinate threshold confusion counts, precision, recall, IoU and Dice separately from the common maximum-side256 grid. It does not report native AUROC/AP without actually computing them.

Second-inspection controls compute one global pass and four scale-specific tile passes in a batch. Chosen/random outcomes reuse that batch. Logical chosen/random policies each use one equal-sized crop; all4 uses four. This is a counterfactual call-budget comparison, not independently timed end-to-end execution. The actual integrated API performs at most one extra call and has separate uncached runtime measurements.

Report both standalone crop scores and full-plus-crop fusion. The fixed fusion rule is the maximum component score divided by that component's frozen normal threshold, with decision threshold1. Pixel fusion is the maximum component map divided by its frozen normal pixel threshold, restored to source coordinates. Chosen/random/all4 components have their separately calibrated image thresholds. The union's false-alert rate is measured; it is not guaranteed to retain a5%budget and is not a proposed release winner. Pixel metrics and decision changes may worsen.

Selective controls retain the same initial score, region extraction and review bounds: static quality-gated initial pass, chosen detail, random detail, chosen with quality gate off and chosen with ROI off. They report actual decision flips, unresolved reviews, false clears and trace completeness. Logical call counts are distinguished from the batch executor's four physical extra passes. Registration and a second physical view are not invoked by this v2 path; their OFF ablations have no causal effect. No new physical view is claimed.

The original13-artifact scientific freeze is checked before the new overall freeze. Existing reports, model banks and submission artifacts remain historical. Source/model/manifest hashes freeze before the first v2 accuracy case; final partitions cannot be used to revise methods. Source-cache timings are excluded from production-speed claims.

The public AWS performance profile was interrupted after10warmups and30measured uploads when the local worker stopped. A resumed segment retains the original state and records the gap, verifies the same build, and continues the original fixed image order. This is a segmented measurement, not a continuous-capacity test.

Dedicated Fargate request correlation verifies820successful requests. Its one malformed stdout line contained two concatenated JSON objects; the raw log is retained and consecutive JSON decoding recovers both records, all linked to their backend inspection/request records. No per-task CPU utilization metric existed; configured1vCPU is not measured utilization.
