# AWS deployment status

**Status: deployed and smoke-verified on October 24, 2026.** The Sydney endpoint is [https://re-c0a0c131729f4898bb80d160feb0ccc7.ecs.ap-southeast-2.on.aws/](https://re-c0a0c131729f4898bb80d160feb0ccc7.ecs.ap-southeast-2.on.aws/). The `reflex-foundation` and `reflex-service` CloudFormation stacks are stable at `UPDATE_COMPLETE`.

## Verified cloud run

### Current real-image release

Build `reflex-20261024t095525z` serves the real candle/cashew models and six licensed VisA photographs with the solar interface and Original / Heatmap / Overlay comparison. The image digest is `sha256:a7a6de72935e94a43460a2a0125a07b7214624de2940eb1bd097f4a7f106ef34`. Local regression passed41tests; the exact extracted package and cloud gate each passed39tests with2standalone integration checks skipped. Packaged tests run real inference for both categories.

The service reached `UPDATE_COMPLETE` with one running task. Six live real-image inspections returned all three evidence images, preserved decoded original pixels, and matched frozen scores within0.000001. All six request/inspection pairs were correlated in CloudWatch; served static assets matched the reviewed source. See the [complete release evidence](../reports/real_demo_20261024/RELEASE.md). These checks establish operation of the real models on AWS; a full performance benchmark remains outstanding. The existing template was reused without IAM or network changes.

### Historical synthetic release

The historical synthetic release used image tag `reflex-20261024t034312z`, with ECR digest `sha256:f31ae52e9aade8823695d9b57542310fc3a6200b80bdd8f933ea3b2bb0177df0`. CodeBuild run `reflex-image-builder:c9b9b321-a913-4570-8ead-271f6c04f884` completed successfully; the deployment script advances only after its remote test gate succeeds. The exact build ID and source archive fingerprint are preserved in [`results/aws-evidence-20261024t034312z.json`](../results/aws-evidence-20261024t034312z.json). The deployment image was assembled from the allowlisted source package; local databases, credentials, and evaluation outputs are excluded from that build package.

The remote smoke used the bundled synthetic scratch fixture. It reported OpenCV 5.0.0, AWS runtime, `DEFECT_FOUND`, score 15.600005 against threshold 2.288754, and the actual `inspect_full → inspect_crop` trace. The service returned a 223,618-byte overlay PNG with SHA-256 `1e49eddf443f3a7bf40c1f045b7dabaf3e8d0473dfeae7c9f3fb3d181e72bbc9`. The `inspection_completed` and `request_completed` CloudWatch events share that smoke's request ID; the inspection event also matches its inspection ID, decision, OpenCV version, and crop tool. The full evidence and a clean live screenshot are in [`results/`](../results/) and [`demo/screenshots/`](../demo/screenshots/).

The smoke above is one operational check, not a performance benchmark or a real-product evaluation. A separate synthetic-only AWS profile completed 10 warm-ups and 100 measured requests, spaced at least 62 seconds apart to honor the deployed upload guard. Client end-to-end latency was 2,719.2 ms mean, 2,656.3 ms p50, 3,571.2 ms p95, and 5,893.3 ms max; server-reported runtime was 53.1 ms mean, 56.3 ms p50, 62.2 ms p95, and 75.9 ms max. This sequential profile does not measure saturation capacity. Exact-window ECS CPU/memory and application-log metrics were not captured because the AWS MCP server and signed-in console surface were unavailable in this session; the full report records the blocker and does not substitute earlier values. Offline classification results include two VisA benchmark classes; those runs were performed locally and are not evidence about the AWS service. No MVTec or physical-camera images were sent to AWS.

## Runtime and data boundary

- ECS Express serves HTTPS through an AWS-managed internet-facing load balancer to one Fargate task, capped at 1 vCPU and 2 GiB. The service scaling target is one task.
- The service is public and has no user sign-in. The browser warns that images are sent to Sydney. Use the licensed examples or other non-private images; do not upload private, identifying, customer, or production imagery.
- Images, derived artifacts, inspection records, and reviews use the task's ephemeral filesystem. The app does not write inspection payloads to S3. A 24-hour retention policy runs every 15 minutes; task replacement can remove data sooner.
- The API allows up to 10 upload requests per client per 10-minute window, enforced in process memory. This is not a distributed quota or a production abuse control.
- CloudWatch application logs retain structured request and inspection metadata for seven days, including request/inspection IDs, decision, score, tool names, OpenCV version, and duration. They omit source-image hashes and image bytes.
- The private source bundle in S3 expires after one day. ECR uses immutable image tags and retains the latest three images. The build role and ECS execution/infrastructure roles are separately scoped.

## Recheck and update

`backend/scripts/aws_preflight.py` is read-only. It reports profile authentication, stack state, and endpoint. `infra/aws/verify.ps1` sends one bundled synthetic request, then verifies the matching build, image digest, CloudWatch events, and writes local evidence without changing AWS resources. `infra/aws/deploy.ps1 -UpdateService` packages source, runs the remote build/test gate, and updates the existing service. It refuses to replace an existing deployment unless that switch is provided.

```powershell
& .\.venv\Scripts\python.exe backend\scripts\aws_preflight.py
.\infra\aws\verify.ps1
.\infra\aws\deploy.ps1 -UpdateService
```

## Cost and teardown

AWS reports the project plan as Free and active, with promotional credits available when checked. This is not a cost estimate or a guarantee that all resources are covered. Fargate usage, the load balancer, public IPv4, CloudWatch logs, CodeBuild, and ECR can consume credits or incur charges. No actual bill or cost-per-request measurement was collected. See [Fargate pricing](https://aws.amazon.com/fargate/pricing/) and [Elastic Load Balancing pricing](https://aws.amazon.com/elasticloadbalancing/pricing/).

The service and its load balancer remain live until deleted. Teardown is guarded by exact stack names and permanently removes AWS resources; local proof files remain:

```powershell
.\infra\aws\destroy.ps1 -Profile reflex-aws -Region ap-southeast-2 -ConfirmStackNames reflex-service,reflex-foundation
```

Do not run teardown while judges need the endpoint. Confirm the current resources have not been adopted elsewhere before using the script.
