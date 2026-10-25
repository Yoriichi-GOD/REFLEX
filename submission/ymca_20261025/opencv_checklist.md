# OpenCV extension submission checklist

Earlier header cutoff: **27 October 2026, 12:15 IST** (26 October, 23:45 PDT). Official overview narrative has a later 23:59 Pacific time; use the earlier header. [Official rules](https://opencv26.devpost.com/rules).

| Requirement | Evidence/status in this review material |
|---|---|
| Substantive OpenCV 5 | Generated-video run manifest records OpenCV 5.0.0, decode/perspective/color/contour/quality operations and saved overlays. |
| Meaningful AWS | Prior anomaly deployment and correlated real-image logs exist. Extension safety-video AWS run: NOT RUN. |
| Code and reproduction | Source snapshots, recipe/fixture/evaluator hashes and existing pinned runtime retained. Root owns final integrated release and fresh-clone validation. |
| Evaluation | 18 unique held-out synthetic clips, 54 policy rows, all failures and no agent accuracy gain retained. Physical procedural benchmark NOT RUN. |
| Architecture | New recipe/CV/action/review architecture table in deck, source implementation snapshots and existing anomaly architecture. |
| Working demonstration | Existing anomaly endpoint has prior verification. Local extension API/UI verification is owned by integration chats; do not infer it from these slides. |
| Human control | Review fields remain separate from machine result, no physical actuation. Actual operator burden unmeasured. |
| Dataset rights | VisA attribution retained. Assembly101 media gated; raw annotation assets and unknown-license sample kit excluded from public source by default. |
| Agentic award | Actual visual outputs influence later bounded frame selection or input request. Measured outcome ties controls. Do not claim broad task-success superiority. |
| COOL award | NOT USED / not claimed. Ordinary OpenCV on Arm would not establish COOL integration. |
| <=5-minute video | SCRIPT PREPARED, recording/presenter/access URL and duration verification PENDING. |
| Team and eligibility | Actual names/contact and eligibility confirmation PENDING HUMAN INPUT. |
| Public repository | User authorized publication. Root owns review/push; do not insert a fictional URL. |
| Final submission | NOT SUBMITTED by this task. Receipt and external link/access checks PENDING. |

## Reproduction scope

The executed software benchmark uses the existing pinned application environment with backend package import path:

```text
python -m reflex_safety.fixtures --root <new-fixture-folder>
python -m reflex_safety.benchmark --fixtures <fixture-folder> --output <new-empty-run-folder>
```

The folders are explicit user-selected output locations, not existing sample output claims. The generator/run directories reject metadata replacement. Regenerate local input paths on another host. `sources/FINDINGS.md` records executed environment failures, rerun and all measured limitations. This checklist does not establish a fresh-machine run or a cloud video benchmark.
