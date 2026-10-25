# REFLEX Fixed Methods and Seed Results



All fixed methods and seeds are retained below. Raw threshold counts differ from final policy dispositions when review is possible. No method or seed is selected from these results. TP denotes a confirmed defect decision; FC denotes automatic false clear; FP denotes a final false-defect alert. Unresolved reviews are excluded from confirmed detections.

The independent image oracle verifies 88 method/group rows and 9,460 predictions over 860 unique population cases. Repeated arms are paired evaluations, not additional independent observations.

## candle replay

| Recorded method | AUROC | AP | Raw TP FP FN TN | Final TP FP FC TN | Reviews |
| --- | --- | --- | --- | --- | --- |
| classical_cv5 | 0.7575 | 0.7313 | 16 / 4 / 84 / 96 | 16 / 4 / 84 / 96 | 0 |
| dense128_max | 0.9489 | 0.9535 | 69 / 3 / 31 / 97 | 69 / 3 / 21 / 94 | 13 |
| dense128_pose | 0.9441 | 0.9486 | 71 / 4 / 29 / 96 | 71 / 4 / 29 / 96 | 0 |
| dense128_region | 0.9566 | 0.9546 | 69 / 3 / 31 / 97 | 78 / 6 / 18 / 94 | 4 |
| dense128_seed20261025 | 0.9476 | 0.9509 | 75 / 6 / 25 / 94 | 75 / 6 / 25 / 94 | 0 |
| dense128_seed20261026 | 0.9298 | 0.9317 | 64 / 3 / 36 / 97 | 64 / 3 / 26 / 94 | 13 |
| dense128_top4 | 0.9519 | 0.9537 | 72 / 3 / 28 / 97 | 72 / 3 / 19 / 93 | 13 |
| dense512_max | 0.9373 | 0.9374 | 73 / 6 / 27 / 94 | 73 / 6 / 19 / 92 | 10 |
| dense512_seed20261025 | 0.9273 | 0.9332 | 70 / 4 / 30 / 96 | 70 / 4 / 23 / 92 | 11 |
| dense512_seed20261026 | 0.9375 | 0.9409 | 70 / 5 / 30 / 95 | 70 / 5 / 30 / 95 | 0 |
| v1_recomputed_metrics | 0.9005 | 0.8967 | 42 / 3 / 58 / 97 | 42 / 3 / 58 / 97 | 0 |

## cashew replay

| Recorded method | AUROC | AP | Raw TP FP FN TN | Final TP FP FC TN | Reviews |
| --- | --- | --- | --- | --- | --- |
| classical_cv5 | 0.5964 | 0.7124 | 5 / 3 / 95 / 47 | 5 / 3 / 95 / 47 | 0 |
| dense128_max | 0.9512 | 0.9778 | 73 / 0 / 27 / 50 | 73 / 0 / 27 / 50 | 0 |
| dense128_pose | 0.9650 | 0.9841 | 75 / 0 / 25 / 50 | 75 / 0 / 10 / 43 | 22 |
| dense128_region | 0.9600 | 0.9818 | 77 / 0 / 23 / 50 | 77 / 0 / 23 / 50 | 0 |
| dense128_seed20261025 | 0.9606 | 0.9817 | 77 / 1 / 23 / 49 | 77 / 1 / 23 / 49 | 0 |
| dense128_seed20261026 | 0.9564 | 0.9798 | 72 / 0 / 28 / 50 | 72 / 0 / 28 / 50 | 0 |
| dense128_top4 | 0.9582 | 0.9810 | 74 / 0 / 26 / 50 | 74 / 0 / 26 / 50 | 0 |
| dense512_max | 0.9636 | 0.9824 | 74 / 1 / 26 / 49 | 74 / 1 / 26 / 49 | 0 |
| dense512_seed20261025 | 0.9488 | 0.9772 | 73 / 0 / 27 / 50 | 73 / 0 / 27 / 50 | 0 |
| dense512_seed20261026 | 0.9478 | 0.9767 | 76 / 0 / 24 / 50 | 76 / 0 / 24 / 50 | 0 |
| v1_recomputed_metrics | 0.9476 | 0.9744 | 70 / 2 / 30 / 48 | 70 / 2 / 30 / 48 | 0 |

## capsules development

| Recorded method | AUROC | AP | Raw TP FP FN TN | Final TP FP FC TN | Reviews |
| --- | --- | --- | --- | --- | --- |
| classical_cv5 | 0.6087 | 0.7197 | 5 / 2 / 45 / 28 | 5 / 2 / 45 / 28 | 0 |
| dense128_max | 0.6800 | 0.8029 | 14 / 2 / 36 / 28 | 14 / 2 / 36 / 28 | 0 |
| dense128_pose | 0.6593 | 0.7837 | 10 / 1 / 40 / 29 | 10 / 1 / 36 / 28 | 5 |
| dense128_region | 0.6680 | 0.7947 | 14 / 2 / 36 / 28 | 14 / 2 / 36 / 28 | 0 |
| dense128_seed20261025 | 0.6880 | 0.8087 | 16 / 1 / 34 / 29 | 16 / 1 / 30 / 27 | 6 |
| dense128_seed20261026 | 0.6727 | 0.8081 | 16 / 3 / 34 / 27 | 16 / 3 / 29 / 27 | 5 |
| dense128_top4 | 0.6720 | 0.7942 | 13 / 2 / 37 / 28 | 13 / 2 / 37 / 28 | 0 |
| dense512_max | 0.6593 | 0.7943 | 19 / 4 / 31 / 26 | 19 / 4 / 31 / 26 | 0 |
| dense512_seed20261025 | 0.6747 | 0.8060 | 11 / 1 / 39 / 29 | 11 / 1 / 39 / 29 | 0 |
| dense512_seed20261026 | 0.7013 | 0.8182 | 13 / 2 / 37 / 28 | 13 / 2 / 37 / 28 | 0 |
| v1_fresh | 0.7027 | 0.8137 | 16 / 1 / 34 / 29 | 16 / 1 / 34 / 29 | 0 |

## capsules final

| Recorded method | AUROC | AP | Raw TP FP FN TN | Final TP FP FC TN | Reviews |
| --- | --- | --- | --- | --- | --- |
| classical_cv5 | 0.5653 | 0.6971 | 9 / 4 / 41 / 26 | 9 / 4 / 41 / 26 | 0 |
| dense128_max | 0.6813 | 0.8345 | 17 / 1 / 33 / 29 | 17 / 1 / 33 / 29 | 0 |
| dense128_pose | 0.7540 | 0.8648 | 13 / 0 / 37 / 30 | 13 / 0 / 31 / 30 | 6 |
| dense128_region | 0.6713 | 0.8278 | 16 / 1 / 34 / 29 | 16 / 1 / 34 / 29 | 0 |
| dense128_seed20261025 | 0.6927 | 0.8459 | 18 / 0 / 32 / 30 | 18 / 0 / 27 / 30 | 5 |
| dense128_seed20261026 | 0.7067 | 0.8351 | 16 / 0 / 34 / 30 | 16 / 0 / 30 / 28 | 6 |
| dense128_top4 | 0.6747 | 0.8300 | 17 / 1 / 33 / 29 | 17 / 1 / 33 / 29 | 0 |
| dense512_max | 0.7253 | 0.8414 | 19 / 1 / 31 / 29 | 19 / 1 / 31 / 29 | 0 |
| dense512_seed20261025 | 0.7207 | 0.8513 | 14 / 0 / 36 / 30 | 14 / 0 / 36 / 30 | 0 |
| dense512_seed20261026 | 0.6567 | 0.8191 | 14 / 0 / 36 / 30 | 14 / 0 / 36 / 30 | 0 |
| v1_fresh | 0.7233 | 0.8421 | 16 / 0 / 34 / 30 | 16 / 0 / 34 / 30 | 0 |

## chewinggum development

| Recorded method | AUROC | AP | Raw TP FP FN TN | Final TP FP FC TN | Reviews |
| --- | --- | --- | --- | --- | --- |
| classical_cv5 | 0.5520 | 0.6786 | 1 / 1 / 49 / 24 | 1 / 1 / 49 / 24 | 0 |
| dense128_max | 0.9920 | 0.9965 | 49 / 3 / 1 / 22 | 49 / 3 / 1 / 19 | 3 |
| dense128_pose | 0.9904 | 0.9958 | 48 / 0 / 2 / 25 | 48 / 0 / 2 / 23 | 2 |
| dense128_region | 0.9912 | 0.9964 | 49 / 1 / 1 / 24 | 49 / 1 / 1 / 21 | 3 |
| dense128_seed20261025 | 0.9864 | 0.9940 | 47 / 0 / 3 / 25 | 47 / 0 / 3 / 25 | 0 |
| dense128_seed20261026 | 0.9984 | 0.9992 | 48 / 1 / 2 / 24 | 48 / 1 / 1 / 24 | 1 |
| dense128_top4 | 0.9920 | 0.9967 | 49 / 1 / 1 / 24 | 49 / 1 / 1 / 24 | 0 |
| dense512_max | 0.9808 | 0.9928 | 48 / 2 / 2 / 23 | 48 / 2 / 2 / 23 | 0 |
| dense512_seed20261025 | 0.9880 | 0.9948 | 48 / 3 / 2 / 22 | 48 / 3 / 2 / 22 | 0 |
| dense512_seed20261026 | 0.9936 | 0.9971 | 48 / 1 / 2 / 24 | 48 / 1 / 2 / 24 | 0 |
| v1_fresh | 0.9680 | 0.9885 | 48 / 0 / 2 / 25 | 48 / 0 / 2 / 25 | 0 |

## chewinggum final

| Recorded method | AUROC | AP | Raw TP FP FN TN | Final TP FP FC TN | Reviews |
| --- | --- | --- | --- | --- | --- |
| classical_cv5 | 0.5736 | 0.7069 | 3 / 0 / 47 / 25 | 3 / 0 / 47 / 25 | 0 |
| dense128_max | 0.9744 | 0.9905 | 48 / 4 / 2 / 21 | 48 / 4 / 2 / 20 | 1 |
| dense128_pose | 0.9944 | 0.9972 | 47 / 2 / 3 / 23 | 47 / 2 / 1 / 23 | 2 |
| dense128_region | 0.9736 | 0.9894 | 48 / 4 / 2 / 21 | 48 / 4 / 2 / 20 | 1 |
| dense128_seed20261025 | 0.9848 | 0.9938 | 48 / 2 / 2 / 23 | 48 / 2 / 2 / 23 | 0 |
| dense128_seed20261026 | 0.9840 | 0.9931 | 47 / 2 / 3 / 23 | 47 / 2 / 1 / 22 | 3 |
| dense128_top4 | 0.9712 | 0.9890 | 48 / 3 / 2 / 22 | 48 / 3 / 2 / 22 | 0 |
| dense512_max | 0.9768 | 0.9909 | 47 / 2 / 3 / 23 | 47 / 2 / 3 / 23 | 0 |
| dense512_seed20261025 | 0.9840 | 0.9933 | 48 / 3 / 2 / 22 | 48 / 3 / 2 / 22 | 0 |
| dense512_seed20261026 | 0.9880 | 0.9954 | 49 / 0 / 1 / 25 | 49 / 0 / 1 / 25 | 0 |
| v1_fresh | 0.9840 | 0.9929 | 47 / 3 / 3 / 22 | 47 / 3 / 3 / 22 | 0 |

## pcb1 development

| Recorded method | AUROC | AP | Raw TP FP FN TN | Final TP FP FC TN | Reviews |
| --- | --- | --- | --- | --- | --- |
| classical_cv5 | 0.7916 | 0.7713 | 12 / 2 / 38 / 48 | 12 / 2 / 38 / 48 | 0 |
| dense128_max | 0.9176 | 0.9171 | 34 / 3 / 16 / 47 | 34 / 3 / 16 / 47 | 0 |
| dense128_pose | 0.9172 | 0.9119 | 32 / 4 / 18 / 46 | 32 / 4 / 13 / 44 | 7 |
| dense128_region | 0.9112 | 0.9101 | 33 / 6 / 17 / 44 | 38 / 6 / 7 / 42 | 7 |
| dense128_seed20261025 | 0.8740 | 0.8793 | 37 / 6 / 13 / 44 | 37 / 6 / 12 / 40 | 5 |
| dense128_seed20261026 | 0.8856 | 0.8948 | 35 / 4 / 15 / 46 | 35 / 4 / 12 / 45 | 4 |
| dense128_top4 | 0.9248 | 0.9226 | 31 / 5 / 19 / 45 | 31 / 5 / 19 / 45 | 0 |
| dense512_max | 0.8912 | 0.8976 | 30 / 4 / 20 / 46 | 30 / 4 / 20 / 46 | 0 |
| dense512_seed20261025 | 0.9080 | 0.9169 | 33 / 3 / 17 / 47 | 33 / 3 / 17 / 47 | 0 |
| dense512_seed20261026 | 0.9200 | 0.9216 | 33 / 3 / 17 / 47 | 33 / 3 / 17 / 47 | 0 |
| v1_fresh | 0.8932 | 0.8901 | 30 / 3 / 20 / 47 | 30 / 3 / 20 / 47 | 0 |

## pcb1 final

| Recorded method | AUROC | AP | Raw TP FP FN TN | Final TP FP FC TN | Reviews |
| --- | --- | --- | --- | --- | --- |
| classical_cv5 | 0.7848 | 0.7412 | 10 / 4 / 40 / 46 | 10 / 4 / 40 / 46 | 0 |
| dense128_max | 0.8688 | 0.8629 | 33 / 5 / 17 / 45 | 33 / 5 / 17 / 45 | 0 |
| dense128_pose | 0.8916 | 0.8841 | 34 / 5 / 16 / 45 | 34 / 5 / 8 / 42 | 11 |
| dense128_region | 0.8780 | 0.8733 | 38 / 8 / 12 / 42 | 41 / 9 / 6 / 34 | 10 |
| dense128_seed20261025 | 0.8792 | 0.8872 | 36 / 7 / 14 / 43 | 36 / 7 / 9 / 40 | 8 |
| dense128_seed20261026 | 0.8512 | 0.8607 | 34 / 4 / 16 / 46 | 34 / 4 / 11 / 40 | 11 |
| dense128_top4 | 0.8856 | 0.8794 | 36 / 5 / 14 / 45 | 36 / 5 / 14 / 45 | 0 |
| dense512_max | 0.8596 | 0.8544 | 30 / 6 / 20 / 44 | 30 / 6 / 20 / 44 | 0 |
| dense512_seed20261025 | 0.8556 | 0.8721 | 33 / 5 / 17 / 45 | 33 / 5 / 17 / 45 | 0 |
| dense512_seed20261026 | 0.8608 | 0.8708 | 32 / 3 / 18 / 47 | 32 / 3 / 18 / 47 | 0 |
| v1_fresh | 0.8488 | 0.8539 | 29 / 6 / 21 / 44 | 29 / 6 / 21 / 44 | 0 |

## Interpretation

Seed 20261024 defines the original memory construction. Seeds 20261025 and 20261026 are the fixed repeats, not post-test choices. The classical arm is a practical baseline with different internal resolution. v1_fresh preserves the older algorithm fitted on the new category membership; v1_recomputed_metrics retains earlier replay predictions while correcting the historical AU-PRO definition. The complete runtime, pixel, native-coordinate, crop-control, robustness and reference exports retain their own scopes and verification receipts.

## Policy contribution accounting

A post-evaluation descriptive audit of unchanged outcomes finds identical false-clear case-ID sets for review-only, chosen-crop and random-crop paths in every group. The review band removes those automatic passes; crop choice does not further reduce them. Across 46 executed active cases (29 defective and 17 normal), chosen detail resolves 17 additional true alerts and 4 false alerts relative to review without ROI. Random detail resolves 12 true alerts and 2 false alerts. Review-only leaves 46 unresolved, chosen 25, and random 32; all three retain 127 automatic false clears in the execution audit. These cross-population totals audit controller behavior, not pooled generalization or a superiority test.
