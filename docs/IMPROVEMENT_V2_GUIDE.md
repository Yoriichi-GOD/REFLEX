# REFLEX v2 evaluation guide

## Read the current evidence

- `reports/improvement_v2_20261024/report/REPORT.md`: all fixed accuracy, control and robustness results.
- `reports/improvement_v2_20261024/report/ALL_RESULTS.csv`: 88 rows with original class denominators, raw threshold counts and separate final policy outcomes.
- `reports/improvement_v2_20261024/report/gallery/index.html`: all 860 real photographs with heatmaps, overlays and evaluator-only ground truth. The 46 selected detail files show actual crops of the source photograph.
- `reports/improvement_v2_20261024/report/VERIFICATION.json`: actual table, gallery and source-hash checks.
- `reports/improvement_v2_20261024/accuracy-verification/VERIFICATION.json`: independent pairwise ROC, tied-score AP and decision-count checks.
- `reports/improvement_v2_20261024/VERIFIED_PROGRESS.md`: observed queue state and limits.
- `reports/improvement_v2_20261024/RELEASE_ASSESSMENT.md`: candidate stays local.
- `submission-materials/METRIC_CORRECTION_NOTICE_20261025.md`: correction for historical AU-PRO claims.

The source JSON and saved predictions retain full precision. Do not type presentation numbers from a chart or select the highest-scoring final-test arm as a new winner.

## Population boundaries

Candle/cashew contain 350 reused official test cases and remain development replay. PCB1, capsules and chewinggum use separate custom published-test development/final partitions, 255 cases each. These categories are newly evaluated by REFLEX. They do not supply fresh factory captures or proven physical-part/lot independence.

Eleven methods on eight groups produce 88 rows and 9,460 predictions, not 9,460 independent images. Nine robustness families produce 5,445 dependent transformed cases over the 605 replay/final source cases. Synthetic fixture QA remains separate.

Normal fitting, calibration and reserved normal development memberships are disjoint. Final labels never select methods, seeds or thresholds. The primary `dense128_region` remains fixed. Registration and a second physical view are not invoked by its selective detail path. Capture suitability warnings remain advisory.

## Dataset acquisition and rights

The full official VisA archive was retrieved from `https://amazon-visual-anomaly.s3.us-west-2.amazonaws.com/VisA_20220922.tar` with stable ETag and byte-range checks. Its size is 1,929,840,640 bytes. Locally computed SHA256:

```text
2eb8690c803ab37de0324772964100169ec8ba1fa3f7e94291c9ca673f40f362
```

The publisher did not supply an independently published SHA256. The local hash is not a publisher signature. VisA publisher: Amazon Science / Zou et al., ECCV 2022, CC BY 4.0, `https://github.com/amazon-science/spot-diff`. Keep attribution on submitted photographs and derived panels. Do not include unrelated restricted datasets or private uploads in the submission bundle.

The original two-category acquisition and reports remain historical snapshots. Later acquisition adds PCB1, capsules and chewinggum with image/mask audits and frozen normal/development/final manifests. The complete archive contains additional categories that this study has not evaluated.

## Validated host layout

Canonical project: `C:\Users\nrgen\.codex\scratch\reflex`.

Adjacent `reflex-data` contains:

```text
models/resnet50-v1-12.onnx
visa/prepared/{candle,cashew}
reference_20261024/prepared/{capsules,chewinggum}
reference_20261024/manifests_v2/{fit,calibration,train_development,development,final,freeze}.json
reference_pcb1_20261024/prepared/pcb1
reference_pcb1_20261024/manifests/{fit,calibration,train_development,development,final,freeze}.json
```

The feature cache is regenerable and is not a dataset, metric source or production timing measurement. The saved Windows manifests contain original absolute provenance paths. These commands have been exercised on this host. A clean-machine relocation/build has not been verified; moving the frozen manifest paths without an explicit relocation audit is unsupported.

## Inspect or verify existing results

Run from the canonical project in PowerShell:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'backend'
$env:REFLEX_ONNX_WEIGHTS = Join-Path (Split-Path (Get-Location)) 'reflex-data/models/resnet50-v1-12.onnx'
$env:REFLEX_VISA_PREPARED = Join-Path (Split-Path (Get-Location)) 'reflex-data/visa/prepared'
$Python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
$Evidence = Join-Path (Get-Location) 'reports/improvement_v2_20261024'
& $Python -m reflex_bench.improve_v2 --help
& $Python -c 'from reflex_bench.improve_v2 import check_freeze; check_freeze(); print("Frozen sources and models match")'
& $Python "$Evidence/verify_accuracy_tables_v2.py"
& $Python "$Evidence/verify_local_http_v2.py"
& $Python "$Evidence/verify_fargate_v2.py"
& $Python "$Evidence/verify_public_profile_v2.py"
& $Python "$Evidence/verify_report_bundle_v2.py"
```

These readers verify retained evidence; they do not perform a new blind test. Pixel/map reproducibility receipts appear separately in `supplemental_maps` and `supplemental_control_maps`. Their finite workers save every arm's actual maps, check predictions and recompute metrics. Their state must say `COMPLETED` before claiming full map reproducibility.

The first local memory profile measured the Windows launcher incorrectly. R4 measures the actual server PID. Keep the failed attempts and their correction receipts. The full pre-evaluation regression passed 112 tests. After reporting-only changes, a fresh full suite passed 114 tests in 21.21 seconds (`regression-after-report-exports.log`). Five focused checks also passed in separate runs; do not add separate run counts together.

## Frozen evaluation commands

The implemented module accepts `train`, `train_classical`, `freeze`, `evaluate`, `detail`, `robustness` and `latency`, with `--category` and `--split`. `finish_v2_queue.py` records the exact finite sequence used. Run order was:

1. Fit all five category-specific candidate arms, detail banks and classical baselines on the frozen normal memberships.
2. Verify metric sanity, original evidence and regression; create the full source/model freeze.
3. Evaluate all eight category/population groups, then all matched detail controls.
4. Run nine deterministic robustness families on the five replay/final groups.
5. Generate reports, retain raw maps and independently reproduce the recorded metrics.

Examples of the executed interfaces:

```powershell
& $Python -m reflex_bench.improve_v2 evaluate --category pcb1 --split final
& $Python -m reflex_bench.improve_v2 detail --category candle --split replay
& $Python -m reflex_bench.improve_v2 robustness --category capsules --split final
& $Python -m reflex_bench.report_v2
```

Do not rerun `train`/`freeze` into the original result folder to redefine a published experiment. Preserve this evidence and use a separately registered study folder for a new method. Completed evaluator stages have explicit existing-output guards; an invocation that skips an existing result is not a new measured run.

## Runtime evidence

The local HTTP and dedicated AWS profiles each used the same 100 real VisA images, ten warmups per variant, three 100-request sequential rounds and a 100-request concurrency-two probe per variant: 820 requests per environment. Dedicated AWS used a finite 1 vCPU / 2 GiB Fargate task in `ap-southeast-2`; it stopped with exit 0. It exposed no public listener. Public-service guards stayed active.

The public v1 profile used ten warmups and 100 measured uploads, concurrency one and at least 62 seconds of pacing. It preserves an interrupted/resumed interval and the same build identity. All 110 request IDs match CloudWatch request and inspection events. The collector asserted input and bank hashes, while the old deployed log itself lacks those hashes. Do not describe this as server-side image-hash logging.

Internet roundtrip, full backend handling, model/inspection runtime and nested stage spans have different boundaries. Stage quantiles do not add. Service-level 60-second CloudWatch CPU/memory can include other traffic and is not peak per-request CPU or process RSS. The finite concurrency probes and guarded public uploads do not establish saturation capacity.

## Reference and publication gates

The separate reference owner fits pinned upstream WRN50 PatchCore with a full 10% coreset. Three standard fits and two explicitly labeled disk-backed assembly fits remain separate variants. Original failures stay retained. Its center-crop224 pixel scores have a different denominator from REFLEX full-frame localization; crop coverage accompanies them.

All reference export/copy gates and both map queues completed. Root verified all 2,604 reference-bundle files and paired all 860 image hashes. The final six-slide pitch, 37-slide evidence library and all 12 paper/supplement/correction pages were visually reviewed. Canonical delivery: submission-materials/20261025-v2. See CLOSURE.md and the delivery manifests for exact scope. Artifact PNG/package checks do not establish native PowerPoint execution or browser interaction.

Historical custom AU-PRO is invalid for comparison. Corrected exact-event scoring passed independent curve checks, but publisher implementation byte parity remains blocked by the recorded evaluation archive HTTP404. The other measured metrics are assessed separately.

The current release assessment keeps v2 local. In particular, capsules remains weak, normal false-alert burden increases in parts of the new final population, and dedicated AWS p95/memory rise. Preserve these findings in research and presentation updates.
