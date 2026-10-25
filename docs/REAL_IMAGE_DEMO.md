# Real-image inspection demo

The combined release preserves the solar interface and adds real VisA photographs with live OpenCV5 analysis.

## Use it

1. Select **VisA · candle** or **VisA · cashew** under Inspection profile.
2. Click one of the three real photographs, or upload an image from that category.
3. The default **Compare** view shows **Original photograph / Anomaly heatmap / Model overlay** together. Original, Heatmap and Overlay also remain available individually. Zoom, fit, pan, fullscreen, reference alignment, review, retake and report controls remain available.
4. The evaluation panel follows the selected profile. It reports the frozen offline benchmark, independently of the current example's live prediction.

The synthetic machined-plate profile remains available and is explicitly labeled. Real photographs are not artificial crack fixtures.

## Images and model boundaries

- Six original VisA JPEGs: three candle and three cashew examples. Original bytes and SHA256 hashes are preserved.
- Attribution: Amazon Science; Zou et al., ECCV2022; [VisA source](https://github.com/amazon-science/spot-diff), [CC BY4.0](https://creativecommons.org/licenses/by/4.0/). Attribution is shown in the gallery and returned inspection record.
- Examples are curated illustrations, including a subtle defective example that the model misses in each category. They are not a random sample or a new accuracy benchmark. Selection/audit details remain in `reports/real_demo_20261024/fixture_audit.json`.
- No ground-truth masks, labels or expected decisions are supplied to live inference. Each click uploads the selected photograph and runs the model; decisions and heatmaps are not precomputed demo responses.
- The frozen normal-only pretrained patch-memory model, trained banks and thresholds are unchanged. The main benchmark results and original submission archives remain preserved.
- Per-request category selection chooses an immutable model bank. It does not change a shared global active model, so different visitors can inspect different categories safely.
- Heatmaps visualize anomaly distances, not defect probabilities or ground-truth masks. A PASS remains a limited model result; the published benchmark contains false clears.

## Deployment and verification

The existing Sydney service, URL, one-task limit, upload guard and temporary storage policy are reused. Images/results expire after24hours on the AWS demo and may disappear sooner if the task is replaced. Do not upload private or production imagery to this public demonstration.

Local regression:41passed. The exact packaged source was separately extracted and tested:39passed,2skipped. The two standalone integration checks require explicit pretrained-weight environment configuration and the external VisA training tree; the packaged multi-profile tests configure the bundled weights and execute real pretrained inference for both categories.

Release `reflex-20261024t095525z` is deployed and stable at `UPDATE_COMPLETE`. The cloud test gate passed39tests with2skipped. All six real-image inspections returned original, heatmap and overlay assets; decoded original pixels matched the source exactly and scores matched frozen results within0.000001. All six request/inspection pairs were correlated in CloudWatch. Served HTML, JavaScript, CSS and all seven font/image dependencies matched the reviewed files. A real gallery click and all three loaded comparison panels were verified in the public browser.

Cloud build, deployment, served-file hashes, real-image smoke results, CloudWatch correlation and screenshots are recorded in the [release verification record](../reports/real_demo_20261024/RELEASE.md). The six smoke cases are not an accuracy or performance benchmark.

The other chat independently verified all14 frontend files against the deployment archive and checked the saved real inspection without uploading again. All three images and fonts loaded without horizontal overflow or clipping at1920×1080,1440×900,1366×768,1024×768,390×844 and360×800. The mobile comparison stacks the images vertically. Its evidence and screenshots are copied into the same scratch release folder.

## Coordinated source ownership

The solar UI was implemented in the OneDrive checkout by the **Build REFLEX solar UI** chat. Its final font-path correction and static-asset regression test were carried into the scratch checkout. The combined backend/gallery release is built from scratch. The other chat handed off deployment ownership before this release; its OneDrive files were not edited here.

The first build attempt used a source object outside the build role's exact-object policy and failed before reading it. The existing permitted object was reused without changing permissions. A subsequent cloud gate caught omitted test-support modules; the package allowlist and isolated bundle test were corrected. Failed attempts remain recorded; no failed image was deployed.
