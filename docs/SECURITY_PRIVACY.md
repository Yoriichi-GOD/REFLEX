# Security and privacy

## Local service controls

- Decode PNG, JPEG, or WebP by content signature; reject mismatched claimed MIME types.
- Enforce 12 MB compressed size, 4096-pixel edges, and 20-million-pixel limits. PNG/JPEG/WebP headers are checked before OpenCV decode.
- Normalize EXIF orientation using orientation metadata; published image artifacts are re-encoded PNGs without original EXIF metadata.
- Never use an uploaded filename as a filesystem path. Artifact names are generated UUIDs and served from one static directory.
- Limit inspection and alignment uploads to 10 per client per 10 minutes by default.
- Return security headers including `nosniff`, `no-referrer`, frame denial, and a same-origin CSP.
- Keep the original source SHA256, model/profile hashes, thresholds, trace, and review record separate.
- Delete local inspection JSON, reviews, and generated image artifacts after 30 days by default (`INSPECTION_RETENTION_DAYS`).
- Do not train on uploads or reviewer feedback.

The local demo leaves reviewer authentication unset. The live AWS demo also has no user sign-in and currently leaves reviewer authentication unset. It is intentionally limited to public synthetic demonstrations, not private or production data.

## Cloud status

The deployed demo uses one Sydney Fargate task. Uploaded originals, derived assets, inspection JSON, and reviewer notes are stored only on the task's ephemeral filesystem, with one-day scheduled cleanup; task replacement may erase them sooner. No inspection payload is written to S3. CloudWatch logs record request/inspection IDs, decision, score, tool names, OpenCV version, and duration, but omit source-image hashes and image bytes. The HTTPS demo is public and has no user sign-in; rate limiting is per application process. The page directs visitors to synthetic images only. Do not send private, identifying, customer, or production imagery to this demo.

## Security boundary and remaining work

The current in-memory rate limit is per application process and is not a distributed quota. There is no multi-tenant authentication or shared persistent cloud store. The public demo is suitable only for synthetic examples, not customer or production uploads. Do not infer that its public HTTPS endpoint is an authenticated production API.
