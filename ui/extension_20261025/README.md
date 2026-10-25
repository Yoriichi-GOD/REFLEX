# Safety Station UI

The additive page is served at `/safety` by `app.extension_main:app`. Start with `python backend/scripts/dev.py`; use the printed OS-assigned loopback URL. The original Inspection Studio remains at `/`.

The page uses the existing solar logo, space background, planet imagery, fonts and stylesheet. Its own layout is scoped to `safety-*` classes. The existing studio's `app.js` and `styles.css` are unchanged. Its index receives one link outside `.navigation`, avoiding that script's hash-only selector handler.

## Working UI paths

- Select a validated teaching recipe and policy, consent to the source, and verify the normalized clockwise panel corners. Unknown prior state and no final checkpoint are the default.
- Upload a supported video or still, or load a generated fixture whose bytes must match its published hash. The server validates media bounds and recognizes synthetic fixture hashes. Browser codec failure offers decoded JPEG evidence rather than claiming playback succeeded.
- Follow actual session state and measured frame counts. Select a timeline event, step or slot to inspect recorded frame/observation evidence. The calibrated frame is a transformed panel, not an untouched source image.
- Request additional input; a returned child session has its own capability and preserves the parent's original machine finding. Supply a real image and finalize the child. A still cannot establish the sequence of an assembly.
- Append operator acknowledgement or refutation with an explanation. Download actual evidence JSON or printable HTML, which can be printed to PDF by the user.
- Reopen sessions whose capabilities are saved in this browser tab. Compare completed different-policy runs only when the media hash, recipe hash, panel calibration, prior-state setting, final-checkpoint setting and source mode agree. Results are recorded runs, not a benchmark claim.
- Camera requests video only. It serializes frame uploads, stops all tracks on stop/disconnect/navigation, and is bounded by 120 seconds / 200 submitted frames. Permission failure offers the upload path. This implementation is not physical-camera verification.

Capabilities are sent in Authorization headers, never querystrings. Protected fetches reject cross-origin/cross-session paths and redirects. UI text uses DOM text nodes. Session keys remain in sessionStorage and are not included in reports or verification receipts.

## Verification

Run from the repository root:

```text
node --check frontend/safety.js
node --test ui/extension_20261025/test_safety_core.cjs ui/extension_20261025/test_safety_lifecycle.cjs
python ui/extension_20261025/test_safety_markup.py
python ui/extension_20261025/check_api_integration.py
```

Use the repository Python environment for the API check. It creates isolated runtime data under the test output directory; set `REFLEX_UI_TEST_OUTPUT` to choose a location outside tracked source. It never edits models or frozen scientific sources. Test session runtime folders contain local storage and should not be published.

The JavaScript tests exercise capability boundaries, input/calibration validation, genuine saved-run identity requirements, camera-track teardown and DOM/HTTP-substitute lifecycle paths for still upload and denied camera. The markup checks verify IDs, assets, consent defaults and accessibility structure. The actual API check exercises FastAPI routes and OpenCV 5 pixel evidence, authorization, report escaping, review and child-session boundaries. These are separate kinds of evidence and do not add to benchmark sample counts.

**Browser/visual gate: NOT RUN.** The available browser tool reports “Local browser use is disabled in Work settings.” No browser screenshots or Playwright pass are claimed. Real webcam capture, responsive rendering, native video playback, and interactive browser upload→process→report remain unverified. No authorized physical assembly clips have been acquired; generated fixtures are `SYNTHETIC_SOFTWARE_TEST`, and real-assembly performance remains NOT RUN.

The frontend itself performs no machine actuation, identity or fatigue inference, model training, AWS deployment or publication. Integration and public-repository publication are owned by the coordinating REFLEX chat.
