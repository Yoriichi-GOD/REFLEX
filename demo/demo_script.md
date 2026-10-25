# REFLEX live demo outline (under five minutes)

This is an outline only. No video has been recorded.

1. Introduce the team and describe the inspection uncertainty problem.
2. Select the normal synthetic fixture; show the OpenCV 5 health version, quality, score, and threshold.
3. Select the scratch fixture; show the source image, localized overlay, `inspect_crop` input, native pixel dimensions, new measurements, and operator-confirmable decision.
4. Select the blurred fixture; show the `LOW_FOCUS` flag and request for another capture. If available, upload a real new capture and show the linked new inspection.
5. Show JSON/HTML export and separate reviewer record.
6. Show current measured synthetic holdout metrics and failure gallery. Say clearly that these are synthetic fixtures, not factory or MVTec results.
7. Show the deployed Sydney endpoint and its correlated synthetic CloudWatch proof. State that AWS use has been verified with a synthetic smoke only; do not present it as a real-data benchmark.
8. Close with limitations and human confirmation boundary.
