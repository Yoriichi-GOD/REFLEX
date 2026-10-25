# Demo and submission preparation

## Competition text

**Title:** REFLEX — An Industrial Inspector That Knows When to Look Again  
**Tagline:** Agentic OpenCV 5 inspection that detects anomalies, requests the right second look, and explains every decision.

**Problem:** A single image may be blurred, poorly exposed, or visually ambiguous. A fixed one-pass score can hide uncertainty.

**Solution:** REFLEX scores an image against a normal-only reference, marks suspicious regions, and selects a bounded next inspection action from measured evidence. It can inspect a native-pixel crop or request a retake/human review. The operator retains the final decision.

## Verified outcomes

- Runtime: OpenCV 5.0.0 locally and in the live AWS demo.
- Fitted profile: one synthetic machined-plate normal bank; 40 train normals and 12 calibration normals.
- Evaluation: 32 held-out synthetic cases plus a separate, explicitly synthetic-only kit QA run. Real VisA, robustness, agent ablation, and AWS profile results are in the [complete benchmark report](../reports/FINAL_BENCHMARK_REPORT.md); the historical synthetic run details are in [`EVALUATION.md`](EVALUATION.md).
- Real-image benchmark: offline official VisA candle and cashew test splits. At frozen thresholds, the baseline detected 16/100 candle anomalies and 5/100 cashew anomalies. The 84 and 95 false clears show that this baseline is not ready for a practical inspection claim; see [`EVALUATION.md`](EVALUATION.md).
- Agent examples: normal → no second tool; localized synthetic scratch → native-resolution crop measurement; blurred image → new-capture request.
- AWS: deployed in `ap-southeast-2`; a live synthetic scratch run returned `DEFECT_FOUND`, followed the `inspect_full → inspect_crop` trace, and produced an overlay. Matching CloudWatch events are recorded in [`aws-evidence-20261024t034312z.json`](../results/aws-evidence-20261024t034312z.json). A separate 10-warm-up/100-measurement profile completed with hash-verified synthetic fixtures at a 62-second minimum gap. It measured client and server latency, not service capacity; exact-window ECS CPU/memory and application-log counts were not captured. The live endpoint is [REFLEX AWS demo](https://re-c0a0c131729f4898bb80d160feb0ccc7.ecs.ap-southeast-2.on.aws/).
- Limits: the deployed profile is synthetic-only. Offline VisA results are poor; agent decisions did not improve over single-pass on either VisA class or the fixed synthetic evaluation. No factory-floor or physical-product performance is established.
- The AWS endpoint is public and unauthenticated. Use only the bundled synthetic samples; never upload private, identifying, customer, or production imagery. Its task-local records expire under a 24-hour cleanup policy.

## Links that still need operator input

- Team name and presenter: `NEEDS_OPERATOR_INPUT`
- Public/unlisted judge endpoint: [REFLEX AWS demo](https://re-c0a0c131729f4898bb80d160feb0ccc7.ecs.ap-southeast-2.on.aws/) (verified live; external judging access remains subject to endpoint availability)
- Public source repository/archive URL: `NEEDS_OPERATOR_INPUT` (local benchmarked draft: `dist/benchmark-submission-20261024/reflex-submission.zip`; publish it or provide a judge-accessible repository)
- Video URL (maximum five minutes): `NEEDS_OPERATOR_INPUT`
- Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Evaluation: [`EVALUATION.md`](EVALUATION.md)
- Technical report: [`TECHNICAL_REPORT.md`](TECHNICAL_REPORT.md)
- Submission receipt: `NEEDS_OPERATOR_INPUT`

The deployed AWS data boundary is synthetic-only; no real VisA images were sent to the service. Do not publish MVTec data or imply physical-product validation. The official PatchCore run and VisA `pcb1` class remain blocked; the final report records each blocker. No special prize is selected here: actual competition eligibility is not established without external submission review.

## Recording plan (not a recording)

The presenter must introduce the team on camera, then capture a real live run of the normal, scratch, and blurred cases; show the actual trace, source/overlay/ROI views, exports, the synthetic evaluation and the poor VisA results including failure cases, and the live AWS endpoint. End with the prototype boundary and human confirmation. Keep the finished video below five minutes. Do not replace live outputs with precomputed results. The screenshots in [`../demo/screenshots/`](../demo/screenshots/) document the current AWS page and scratch trace; they do not replace the required recording.

## Deadline note

Checked October 24, 2026: the public rules/header show October 26 at 11:45 PM PDT (October 27 at 12:15 PM IST). The overview narrative says 11:59 PM Pacific, six minutes later. Use the earlier public cutoff; the attached build contract sets the internal hand-in to October 26 at 9:00 PM IST. Verify the submission countdown in the signed-in Devpost account before hand-in: [official rules](https://opencv26.devpost.com/rules), [competition overview](https://opencv26.devpost.com/).
