# Documentation and evidence

[Project home](../README.md) · [Watch the demo](https://youtu.be/WvnKxOTxkvw) · [OpenCV project](https://devpost.com/software/reflex-xqn8i7)

## Choose an entry point

| You want to… | Read |
| --- | --- |
| Understand REFLEX in a minute | [Reviewer guide](REVIEWER_GUIDE.md) |
| Run the actual application | [Setup, troubleshooting and verification](GETTING_STARTED.md) |
| See deployed, local, planned and untested capabilities | [Current status](PROJECT_STATUS.md) |
| Find the architecture and relevant modules | [Architecture and source map](ARCHITECTURE_GUIDE.md) |
| Audit implementation and measured claims in detail | [85-question technical report](REFLEX_YMCA_PPT_INTELLIGENCE_PUBLIC.md) |

## Benchmark evidence

- **Real industrial photographs:** [study overview](../benchmarks/anomaly_v2/README.md), [frozen protocol](../benchmarks/anomaly_v2/PROTOCOL.md), [88 method/group rows](../benchmarks/anomaly_v2/ALL_RESULTS.csv), [release decision](../benchmarks/anomaly_v2/RELEASE_ASSESSMENT.md), [upstream PatchCore comparison](../benchmarks/anomaly_v2/REFERENCE_COMPARISON.md), [robustness](../benchmarks/anomaly_v2/ROBUSTNESS.csv) and [cloud runtime](../benchmarks/anomaly_v2/RUNTIME.csv).
- **Metric correction:** read [the AU-PRO notice](../benchmarks/anomaly_v2/METRIC_CORRECTION.md) and [evaluator addendum](../benchmarks/anomaly_v2/PROTOCOL_EVALUATOR_ADDENDUM.md) before interpreting older pixel/region results.
- **Numeric provenance:** [ledger overview](../benchmarks/intelligence_20261025/README.md), [full numeric ledger](../benchmarks/intelligence_20261025/BENCHMARK_LEDGER.csv) and [independent image-metric recheck](../benchmarks/intelligence_20261025/ORACLE_RECHECK.json).
- **Generated procedure software tests:** [findings](../benchmarks/procedural_safety/public/FINDINGS.md), [all 54 policy rows](../benchmarks/procedural_safety/public/results.csv) and [all-case HTML gallery](../benchmarks/procedural_safety/public/index.html). Open the downloaded HTML locally; GitHub displays its source. These are 18 generated clips reused across three policies, not real assembly videos.
- **Historical software checks:** [source-export verification](verification/PUBLIC_SOURCE_VERIFICATION.json) and [dynamic HTTP receipt](verification/DYNAMIC_HTTP_VERIFICATION.json). Their dates and scopes matter; documentation checks do not rerun those experiments.

## Reports and presentations

The [submitted OpenCV project](https://devpost.com/software/reflex-xqn8i7) is the current external entry and includes the team video. The following committed artifacts remain available as earlier editable review materials; they are not evidence of publication acceptance or a newer deployment.

| Material | Files |
| --- | --- |
| Project research manuscript | [PDF](../submission/opencv_current/REFLEX_Research_Paper_v2.pdf) · [editable Markdown](../submission/opencv_current/REFLEX_Research_Paper_v2.md) · [Word](../submission/opencv_current/REFLEX_Research_Paper_v2.docx) |
| Required metric context | [Correction addendum](../submission/opencv_current/REFLEX_Correction_Addendum_v2.pdf) · [metric notice](../submission/opencv_current/METRIC_CORRECTION.md) |
| All-methods supplement | [PDF](../submission/opencv_current/REFLEX_All_Methods_Supplement_v2.pdf) · [Markdown](../submission/opencv_current/REFLEX_All_Methods_Supplement_v2.md) |
| Earlier six-slide pitch | [Editable PowerPoint](../submission/opencv_current/REFLEX_Pitch_V2_6_Slides.pptx) |
| Separate evidence library | [Editable charts and evidence](../submission/opencv_current/REFLEX_Editable_V2_Evidence.pptx) |
| YMCA Theme 04 material | [Ten-slide deck](../submission/ymca_20261025/REFLEX_YMCA_Theme04_10_Slides.pptx) · [slide previews](../submission/ymca_20261025/renders) |

## Data, operation and historical context

Use [Third-party notices](../THIRD_PARTY_NOTICES.md), [data provenance](data_license_manifest.md), [AWS evidence](aws_evidence.md), [extension architecture](system_architecture.md) and [extension safety/storage limits](limitations_and_safety.md) for their stated scopes.

[STATUS.md](../STATUS.md) is a **25 October snapshot**. Older uppercase reports such as [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md), [DEMO_AND_SUBMISSION.md](DEMO_AND_SUBMISSION.md) and [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) describe earlier stages and may contain superseded pending items or synthetic-only deployment descriptions. They are preserved for provenance. Start with [current status](PROJECT_STATUS.md) and the dated [technical intelligence report](REFLEX_YMCA_PPT_INTELLIGENCE_PUBLIC.md) for the combined project.

No documentation polish changes the frozen study, releases the v2 candidate, or validates physical safety. Private raw datasets, credentials, uploads, databases and build/runtime folders are not required to browse this public evidence.
