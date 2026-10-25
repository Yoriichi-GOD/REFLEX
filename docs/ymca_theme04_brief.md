# REFLEX Safety for YMCA Theme 04

REFLEX is a vision-assisted, uncertainty-aware bench assembly quality gate. It compares visible parts and assembly history with a small explicit recipe, records its evidence and preserves human control. It does not identify workers, infer fatigue, actuate machines or certify industrial safety.

The official Theme 04 document addresses procedure mistakes, incompatible component configurations, unsafe actions and early detection without excessive interruption. A colored teaching fixture provides a bounded software implementation of that workflow. Broader accident prevention remains an intended application requiring physical validation.

## Current implementation

The new `/api/safety` namespace supports consented replay uploads, supplied camera/still frames, a versioned three-step recipe, perspective calibration, OpenCV color/shape recognition and quality checks. The recipe engine requires stable temporally spaced observations. It reports PASS, HOLD FOR REVIEW or REJECT RECOMMENDATION and retains frame IDs, hashes, time basis and reason codes. It can request additional input, preserve human acknowledgements separately and export actual JSON/printable HTML. Implementation presence and software tests do not establish successful camera use or browser interaction.

The existing Anomaly Lab and frozen VisA evidence remain separate. Prior AWS anomaly execution does not prove the new safety-video route executed on AWS. Extension cloud video and native camera-to-alert timing are NOT RUN in the evidence used for this deck.

## Evidence actually available

The completed synthetic suite contains 18 held-out generated videos and 54 predictions across base, seeded random and uncertainty policies. Every policy matches 15/18 expected final statuses and detects 5/7 supported matching error clips. Two of four uncomplicated normal clips falsely end in HOLD. All three policies tie, so no agent accuracy gain is observed. Zero false PASS in these generated cases does not establish safety.

Shared-host offline video-processing p50/p95, including evidence writes: base 215.3265/289.4372 ms, random 237.9018/259.8560 ms, uncertainty 240.7138/249.9388 ms. These are six-second synthetic replays, not camera-to-alert latency, production throughput or physical intervention measurements. Full precision, counts, failures and sources are in `sources/results.json`, `results.csv`, `FINDINGS.md` and the immutable run manifest.

One wrong-order clip ends in HOLD instead of the expected explicit rejection. An unknown-part clip gets generic HOLD without its specific expected event. Both stay in the denominator. The policy spends its two extra frames during initialization; improving that behavior requires a fresh development protocol rather than changing this held-out result.

## Required physical validation

Acquire at least 12 consented recordings spanning four fault types, plus normal-session duration, physical fixture calibration and independent session/fixture/operator/background groups. Have a human review observable error onset and last safe intervention boundaries. Real procedural F1, operational false holds/hour, operator burden, true alternate-view benefit and live latency remain unmeasured.

Assembly101's 328 annotation CSVs were lawfully acquired with pinned hashes, but matched video remains gated and mistake timestamp units require confirmation. Annotation parsing supplies no vision performance. No physically recorded evaluation is substituted with synthetic scores.

## Submission status

The accompanying editable ten-slide deck is review material. Team/institution/contact fields intentionally remain blank. Official listing: PPT due 25 October 2026 at 23:59 IST, 3–4 students from the same institution. Actual submission and its receipt require the team's action. Offline pre-existing-work permission is not established.

Sources: [YMCA listing](https://api.unstop.com/hackathons/cypher-digiweek-jc-bose-university-of-science-and-technology-ymca-faridabad-1771873), [official theme document](https://drive.google.com/file/d/1pS4oJgDjLmRYuLvVLlawaNc_V9LGopEB/view), `sources/CONTEST_VERIFICATION.md`.
