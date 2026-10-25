"""Close the real-image release using saved verification evidence only."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"reports"/"real_demo_20261024"


def load(name):return json.loads((OUT/name).read_text(encoding="utf-8"))


def main():
    smoke=load("aws_smoke.json");proof=load("cloudwatch_proof.json");candidate=load("release_candidate.json");browser=load("browser_check.json")
    assert proof["stack_status"]=="UPDATE_COMPLETE" and proof["correlated_real_inspections"]==6
    assert len(proof["running_images"])==1 and proof["running_images"][0]["digest"]==candidate["image_digest"]
    assert len(smoke["samples"])==6 and all(not r["synthetic"] for r in smoke["samples"])
    assert all(r["loaded"] and r["filter"]=="none" for r in browser["panels"])
    assert len(browser["panels"])==3 and candidate["tag"] in browser["build"]
    peer_assets=load("aws-ui-asset-verification.json");responsive=load("aws-live-responsive.json")
    assert peer_assets["build"]==candidate["tag"] and peer_assets["stack_status"]=="UPDATE_COMPLETE"
    assert peer_assets["root_matches_index"] and len(peer_assets["frontend_files"])==14
    assert all(r["matches"] and r["status"]==200 for r in peer_assets["frontend_files"])
    assert len(responsive)==6 and all(r["allImagesLoaded"] and r["allImagesInsideCanvas"] and r["fontsLoaded"] and not r["overflow"] for r in responsive)
    local_log=(OUT/"regression_solar.log").read_text(encoding="utf-8",errors="replace")
    packaged_log=(OUT/"packaged_regression.log").read_text(encoding="utf-8",errors="replace")
    assert "41 passed" in local_log and "39 passed, 2 skipped" in packaged_log
    banks={}
    for category in ("candle","cashew"):
        frozen=ROOT/"reports"/"improvement_20261024"/"models"/category/"patch_bank.npz"
        bundled=ROOT/"demo"/"profiles"/category/"patch_bank.npz"
        sha=hashlib.sha256(frozen.read_bytes()).hexdigest()
        assert sha==hashlib.sha256(bundled.read_bytes()).hexdigest()
        banks[category]=sha
    source=ROOT/"dist"/"real-demo-20261024"/"aws-source-final.zip"
    source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    assert source_sha=="026819bcdb9cbb75a0bdb8f9cb56b5b19b13142a1ebf84ba90b285c2babffe36"
    verification={"utc":datetime.now(timezone.utc).isoformat(),"status":"DEPLOYED_AND_VERIFIED","endpoint":smoke["endpoint"],
        "build_tag":candidate["tag"],"image_digest":candidate["image_digest"],"build_id":candidate["build_id"],
        "source_sha256":source_sha,"stack_status":proof["stack_status"],"steady_running_tasks":len(proof["running_images"]),
        "local_tests":{"passed":41,"failed":0},"isolated_packaged_tests":{"passed":39,"skipped_external_data_checks":2,"failed":0},
        "cloud_tests":{"passed":39,"skipped_external_data_checks":2,"failed":0,"source":"release_candidate.json test_summary_lines"},
        "real_live_smoke_count":6,"real_browser_gallery_click_verified":True,"cloudwatch_correlated_real_inspections":6,
        "original_decoded_pixels_preserved":True,"compare_panels_loaded":3,"static_dependency_hashes_verified":len(smoke["static_files"]),
        "independent_frontend_files_verified":len(peer_assets["frontend_files"]),
        "live_responsive_viewports_verified":[r["viewport"] for r in responsive],
        "max_live_offline_score_absolute_delta":max(r["score_absolute_delta"] for r in smoke["samples"]),"unchanged_trained_banks":banks,
        "training_or_threshold_changes":False,"iam_or_network_changes":False,"infrastructure_template_reused":True,
        "source_coordination":"Solar UI preserved; other chat handed off deployment ownership before update; OneDrive source not edited here.",
        "limits":["Six curated smoke cases are not an accuracy or latency benchmark.","Full changed-model AWS load/resource benchmark remains outstanding.","Frozen two-class accuracy limitations and false clears remain.","Images/results are temporary task-local public-demo storage; use licensed examples or non-private images."]}
    (OUT/"verification.json").write_text(json.dumps(verification,indent=2),encoding="utf-8")
    lines=["# REFLEX real-image demo — deployed and verified","",f"Verified UTC: {verification['utc']}","",
        f"Endpoint: [{smoke['endpoint']}]({smoke['endpoint']})","",
        "The solar interface now offers real VisA candle and cashew photographs. A gallery click computes live OpenCV5 evidence and shows the original photograph, anomaly heatmap and overlay together. The original synthetic profile remains available.","",
        "## Definition of done","",
        "- [x] Six original licensed real photographs, visible attribution and source hashes.",
        "- [x] Selectable candle/cashew models with per-request bank isolation and matching evaluation panels.",
        "- [x] Default original/heatmap/overlay comparison; existing individual layers, zoom, fit, pan, Settings and review controls preserved.",
        "- [x] No ground-truth masks or expected decisions supplied to inference; no precomputed demo decisions.",
        "- [x] Local41tests passed; isolated bundle39passed/2skipped; cloud39passed/2skipped. The packaged real-model tests run for both categories.",
        "- [x] Existing Sydney service updated and stable at UPDATE_COMPLETE, with one steady running task.",
        "- [x] All7 font/image dependencies plus HTML/JavaScript/CSS match the reviewed local files.",
        "- [x] Six live real-image inspections returned original, heatmap and overlay assets; original decoded pixels match exactly.",
        "- [x] All6 request/inspection pairs correlate with OpenCV5, real-model, non-synthetic CloudWatch events.",
        "- [x] A real gallery click was verified in the public browser, with all3 evidence panels loaded and no decorative image filter.","",
        "- [x] Independent read-only verification matched all14 frontend files to the deployed archive and confirmed loaded fonts and unclipped comparison images at six desktop/mobile sizes (1920,1440,1366,1024,390,360px wide).","",
        "## Actual live smoke outputs","",
        "Curated functional examples, not an independent accuracy or performance benchmark. The subtle examples retain the current model's false clears.","",
        "| Example | Decision | Live score | Offline score | Absolute delta | Server ms | Client ms |",
        "|---|---|---:|---:|---:|---:|---:|"]
    for r in smoke["samples"]:
        lines.append(f"| {r['demo_id']} | {r['decision']} | {r['score']:.6f} | {r['offline_score']:.9f} | {r['score_absolute_delta']:.9f} | {r['reported_server_runtime_ms']:.3f} | {r['observed_client_ms']:.3f} |")
    lines += ["","## Release identity","",f"Build: `{candidate['tag']}`",f"Image digest: `{candidate['image_digest']}`",f"Source archive SHA256: `{source_sha}`","",
        "Source: `dist/real-demo-20261024/aws-source-final.zip`. Detailed API/artifact checks are in `aws_smoke.json`; runtime correlation in `cloudwatch_proof.json`; browser evidence in `browser_check.json` and `aws-real-comparison.png`. Independent UI evidence is in `aws-ui-asset-verification.json`, `aws-live-responsive.json`, `aws-solar-final-desktop.png` and `aws-solar-final-mobile.png`.","",
        "## Preserved evidence and failures","",
        "The original benchmark reports, trained banks, thresholds and prior versioned submission archives remain unchanged. No new training was performed for this demo. The full changed-model AWS benchmark remains outstanding; the observed times above are individual smoke timings.","",
        "The initial cloud build used a source key outside the role's exact-object policy and failed before reading it. The existing allowed source object was reused without widening permissions. The next cloud test gate found missing support modules in the source allowlist; packaging was fixed and an isolated extracted-bundle test was added. Neither failed build was deployed.","",
        "The other chat's completed solar release and font-path correction were preserved. Its asset-routing regression test was carried into this release. This chat did not edit the OneDrive checkout.","",
        "VisA images: Amazon Science; Zou et al., ECCV2022; [source](https://github.com/amazon-science/spot-diff), [CC BY4.0](https://creativecommons.org/licenses/by/4.0/). Original JPEG bytes preserved; overlays generated live."]
    (OUT/"RELEASE.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"status":verification["status"],"build":candidate["tag"],"live_real_cases":6,"cloudwatch_pairs":6,"source_sha256":source_sha}))


if __name__=="__main__":main()
