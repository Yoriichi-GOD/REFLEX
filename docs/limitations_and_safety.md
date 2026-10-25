# Limits and advisory scope

REFLEX is a vision-assisted, uncertainty-aware bench assembly quality gate. It detects visible component and procedure errors while preserving human control. It is not employee monitoring or a certified machine-safety system.

## Recognition and observed failures

Only one manually calibrated teaching fixture and known color/shape classes are supported. Confidence expresses heuristic image support, not a calibrated probability. General part recognition, metric measurement, benefit from a new camera view, human fatigue inference and machinery control are not implemented.

An unknown start or occlusion produces partial-observation status, not proof of wrong order. Brief occlusion recovery leaves history uncertain. A fast initial assembly can prevent empty-start confirmation. These produce measured false HOLD decisions. Wrong-order and unknown-component findings were missed as specific errors. The extra-frame agent budget was spent during initialization and showed no accuracy advantage over random or single policies. Do not retune against these held-out results.

## Evaluation gaps

All procedure evaluation uses generated software-test data. The requested minimum of 12 physically recorded clips has not been acquired. Matched Assembly101 media, human-reviewed onset/intervention boundaries, real operator-burden measurements, physical-webcam trials and independent factory-lot validation are also absent. Real procedural and external logical-data tables remain **NOT_RUN**; VisA scores do not fill those gaps.

Live camera-to-display latency and capacity are unmeasured. Browser control was disabled in Work settings, so interactive browser behavior, responsive rendering and native codec support remain **NOT_RUN**. Actual API, static and CV checks establish a narrower scope.

## Storage and processing controls

Local demo storage retains media until user deletion. Deleting a session requires its capability and an idle worker. Prototype limits are:

- 50 sessions and a 1 GiB quota checked at session creation.
- 50 MiB per video and 12 MiB per submitted frame.
- 120 seconds per video; no more than 5 MP or 2560 pixels per video edge.
- 600 decoded frames, a 90-second worker loop and two active clip jobs.

These controls do not establish a hardened hostile multi-tenant service. Native decoder calls run in process; a blocked codec call can exceed the loop deadline. Serving untrusted video publicly requires a process-isolated decoder and supervisor, shared quotas, authentication, storage policies and operational review. No new public Safety Station server was deployed.

Uploads must be authorized and should avoid people or private facilities. The application does not request audio, infer identity or location, or upload media to the cloud without control. The old AWS service has its own published v1 retention and limits.

## Access and provenance limits

A session capability grants bearer access; it is not organization role-based authentication. Report exports omit the token, secret hash and input filesystem path. Authorized operators can access raw observations. The hash-chained append audit detects record changes only while a trusted head is retained; a filesystem owner can rewrite both records and head. Human refutation does not overwrite the model result.

VisA source images retain CC BY 4.0 terms. Acquired Assembly101 annotations and publisher PDFs are private evidence and are excluded from public code. The supplied 96-image kit has unconfirmed redistribution rights, so its bytes are excluded. User-supplied brand artwork is not covered by a blanket MIT grant. See [third-party notices](../THIRD_PARTY_NOTICES.md).
