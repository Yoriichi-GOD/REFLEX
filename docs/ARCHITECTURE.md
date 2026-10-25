# Architecture

## Current local implementation

```mermaid
flowchart LR
  Browser[Local browser UI<br/>upload, layers, review, export]
  API[FastAPI service<br/>OpenCV 5 required]
  IO[Decode + quality + foreground proposal]
  Bank[Normal-only feature median/MAD bank<br/>synthetic profile by default]
  Agent[Bounded deterministic policy]
  Tools[inspect_crop on source pixels<br/>request capture / review]
  Align[Optional ECC affine pair comparison]
  Store[SQLite audit records<br/>local PNG artifacts]
  Eval[Seeded holdout evaluator]
  Browser -->|same-origin HTTP| API
  API --> IO --> Bank --> Agent
  Agent -->|new evidence needed| Tools --> Agent
  API --> Align
  API --> Store
  Eval -.reads synthetic heldout split.- Bank
  API -->|health, scores, trace, URLs| Browser
```

The default profile is synthetic and runs on the local service. The generic offline fit script can write a separate MVTec or VisA class model directory; set `MODEL_DIR` to that directory to activate the fitted class in a local service. The evaluated VisA profiles remain offline and are not deployed. Dataset images are not bundled or redistributed.

## Perception and action

```mermaid
flowchart TD
  A[Decode bytes with OpenCV 5] --> B[Quality, exposure, focus]
  B -->|quality flagged| C[Request a new capture]
  B -->|usable| D[Normal-bank anomaly map + threshold]
  D -->|below threshold| E[Qualified PASS]
  D -->|high, localized| F[Crop original source pixels]
  F --> G[Recompute model and edge/texture evidence]
  G -->|corroborated| H[DEFECT FOUND, operator confirms]
  G -->|conflicting| I[NEEDS REVIEW]
  D -->|high, not localized| I
  C -->|operator supplies another image| J[New inspection linked to prior trace]
```

The choice of `inspect_crop` depends on the first measured score and localized region. It is a distinct OpenCV operation with an actual crop input and computed result. The held-out synthetic experiment found no change in final decisions versus single-pass thresholding, so the agent's task-success benefit is not established yet.

## AWS deployment

The live judge path is browser → HTTPS ECS Express ingress → one ECS/Fargate OpenCV 5 task. The task writes inspection artifacts and audit rows to its ephemeral filesystem, with scheduled one-day cleanup; it does not write user images to S3. Structured metadata goes to CloudWatch. CodeBuild pulls a one-day private source bundle from S3, builds/tests the container, and publishes an immutable ECR image.

```mermaid
flowchart LR
  Browser[Public browser<br/>synthetic images only] -->|HTTPS| Gateway[ECS Express<br/>managed load balancer]
  Gateway --> Task[Fargate task<br/>OpenCV 5 + FastAPI<br/>1 vCPU / 2 GiB]
  Task --> Ephemeral[Task-local SQLite + PNGs<br/>24-hour cleanup]
  Task --> Logs[CloudWatch<br/>7-day structured metadata]
  Source[S3 source bundle<br/>1-day lifecycle] --> Build[CodeBuild<br/>runs API tests]
  Build --> Image[ECR<br/>immutable tag]
  Image --> Task
```

The service is public and has no user sign-in. Its page warns that images go to Sydney and that only synthetic samples should be used. Its per-process rate limit is not a shared quota. The endpoint, smoke evidence, and teardown steps are recorded in [`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md).

## Implementation links

- [FastAPI routes and startup guard](../backend/app/main.py)
- [Image decode and EXIF handling](../backend/app/core/image_io.py)
- [Quality and foreground proposal](../backend/app/core/quality.py)
- [Normal-only model, thresholds, regions, and rendering](../backend/app/core/model.py)
- [Agent policy and crop tool](../backend/app/agent/controller.py)
- [SQLite persistence and retention](../backend/app/storage.py)
- [ECC registration and difference](../backend/app/core/alignment.py)
- [Synthetic fixture generator](../backend/scripts/make_fixtures.py)
- [Evaluation method](../backend/scripts/evaluate.py)
- [Current evaluation](EVALUATION.md)
