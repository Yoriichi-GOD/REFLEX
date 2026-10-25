# REFLEX v2 release assessment

**Decision: keep the candidate local. Keep the existing demo release.**

The primary method was fixed before final evaluation. This assessment uses the independent image-result verification and the dedicated AWS performance receipt. It does not turn a test winner into the next release.

| Population | Method | Detected / defects | False clears / defects | False alerts / normals | Unresolved reviews / cases | Equal-category AUROC |
|---|---|---:|---:|---:|---:|---:|
| replay | v1 | 112 / 200 | 88 / 200 | 5 / 150 | 0 / 350 | 0.9241 |
| replay | dense128_region | 155 / 200 | 41 / 200 | 6 / 150 | 4 / 350 | 0.9583 |
| development | v1 | 94 / 150 | 56 / 150 | 4 / 105 | 0 / 255 | 0.8546 |
| development | dense128_region | 101 / 150 | 44 / 150 | 9 / 105 | 10 / 255 | 0.8568 |
| final | v1 | 92 / 150 | 58 / 150 | 9 / 105 | 0 / 255 | 0.8520 |
| final | dense128_region | 105 / 150 | 42 / 150 | 14 / 105 | 11 / 255 | 0.8410 |

## What improved

On the reused candle/cashew cases, the candidate reduces automatic false clears. The new PCB1 and chewinggum final cases also show fewer automatic defect passes than unchanged-v1 fits. These gains have explicit false-alert and review costs, recorded above. A review never counts as a detected defect.

## Why this version stays local

1. Capsules final remains at 16/50 detected defects and 34/50 automatic false clears. Its AUROC falls from the unchanged-v1 fit. The fixed normal-development workload rule selected no extra review band, so its selective detail path never activates. This is a measured failure to help the weak category, not evidence that detail inspection would never help under another independently designed policy.
2. PCB1 final has 9/50 normal false alerts and seven additional normal reviews. Chewinggum final has 4/25 normal false alerts and one normal review. The normal-development workload budget did not guarantee this held-out workload.
3. The final population equal-category AUROC declines even though final detected-defect count increases. Score ranking, threshold decisions and abstention describe different behavior. Neither alone establishes a release improvement.
4. Dedicated AWS full-handler p95 rises from 1070.469 to 1256.220 ms (17.35%). Peak observed process RSS rises 43.90%. Both variants used the same finite 1vCPU/2GiB task and fixed real fixtures. The loopback test is separate from public network capacity.
5. Active chosen-versus-random controls are smaller than the 30-trigger target in each category. Candle shows more recovered alerts with more false alerts; PCB1 final chosen and random end with the same aggregate outcomes. There is no broad action-selection superiority claim.
6. No new factory capture or physical-lot-independent validation set exists. The three new categories use previously published VisA partitions. Suitability warnings remain advisory.

## Engineering stop rule

Finish the frozen robustness, reference and saved-map verification queues. Preserve every fixed arm and seed. Do not retune thresholds, select the best final-test arm, add a larger agent loop, or deploy this candidate to conceal the weaknesses. Any next method needs a new protocol and new independent validation before a performance claim.

Research and presentation updates must include the failed categories, false-alert/review burden, runtime/memory costs and AU-PRO correction. The historical paper and slides stay preserved with the separate correction notice.
