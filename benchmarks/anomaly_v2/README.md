# Real VisA study — separate from procedural software tests

The fixed study contains 88 method/group rows over 860 distinct VisA cases: 350 previously exposed candle/cashew replay cases, 255 new-category development cases and 255 sealed final cases. Repeated methods and transformed copies are not independent samples. The full-precision CSV tables are copied unchanged from the retained study.

REFLEX's adaptation and the pinned upstream WRN50 reference differ in configuration. The center-crop reference pixel metrics use a different denominator. Historical custom AU-PRO values are invalid; read [METRIC_CORRECTION.md](METRIC_CORRECTION.md). The corrected exact-event scorer passed independent checks, but publisher byte parity remains blocked.

## Outcome

The primary candidate remains **HOLD_CANDIDATE_LOCAL**. Replay improves, while final macro image AUROC falls from 0.852044 to 0.840978. Normal false alerts rise from 9 to 14 among 105 normal final cases. Capsules falsely clears 34 of 50 defective final images. The reference has higher image AUROC in all 8/8 groups.

These results do not establish factory readiness or broad agentic superiority. Read the [release assessment](RELEASE_ASSESSMENT.md) and all result rows. Real procedural video, external logical-anomaly data and independent physical captures remain separate, unmeasured questions.

## Reproduction scope

Large raw datasets, memories, arrays and the reference bundle are retained locally and excluded from the source release. The archive, per-case provenance, seed/model hashes and complete original outputs remain in the retained private evidence. Public source includes acquisition, fitting and evaluation code with model and licensing references.

Clean-machine relocation of the real-data benchmark has not been established. Acquire legitimate VisA data separately and follow [the evaluation guide](../../docs/IMPROVEMENT_V2_GUIDE.md). Preserve the original published study instead of overwriting it.
