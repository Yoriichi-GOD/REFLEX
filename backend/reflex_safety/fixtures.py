"""Owned, deterministic OpenCV video fixtures -- never real industrial data.

The split, scenario parameters and expected outcomes are frozen in protocol.json
before media generation. Expected outcomes and intervals live in annotations,
separate from the runtime input index. Neutral asset names do not encode labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


SOURCE = "SYNTHETIC_SOFTWARE_TEST"
VERSION = "reflex-procedure-fixtures-v1"
SIZE = (640, 480)
FPS = 10
FRAME_COUNT = 60
SLOTS = {
    "spacer_left": (.18, .22, .38, .42),
    "spacer_right": (.62, .22, .82, .42),
    "cover": (.36, .45, .64, .62),
    "left_fastener": (.18, .67, .38, .87),
    "right_fastener": (.62, .67, .82, .87),
}
COLORS = {
    "short_spacer": (220, 80, 30),
    "long_spacer": (220, 80, 30),
    "cover_plate": (40, 180, 40),
    "m3_bolt": (20, 210, 230),
    "red_part": (30, 30, 210),
    "unknown_part": (180, 50, 180),
}

# Parameters are deliberately explicit and versioned, never selected by scores.
SCENARIOS: dict[str, dict[str, Any]] = {
    "normal_fast": {"times": [400, 1200, 2200], "expected": "PASS"},
    "normal_slow": {"times": [1200, 2700, 4200], "expected": "PASS"},
    "long_spacer": {"replace": ["spacer_left", "long_spacer"], "expected": "REJECT_RECOMMENDATION", "error": "WRONG_COMPONENT_CLASS", "onset": 800, "boundary": 2000},
    "red_spacer": {"replace": ["spacer_right", "red_part"], "expected": "REJECT_RECOMMENDATION", "error": "WRONG_COMPONENT_CLASS", "onset": 800, "boundary": 2000},
    "wrong_order": {"times": [2300, 600, 3600], "expected": "REJECT_RECOMMENDATION", "error": "ORDER_VIOLATION", "onset": 600, "boundary": 2300},
    "missing_screw": {"missing": "right_fastener", "expected": "REJECT_RECOMMENDATION", "error": "MISSING_COMPONENT", "onset": None, "boundary": None},
    "wrong_slot_corrected": {"transient": ["left_fastener", "short_spacer", 2100, 3300], "times": [800, 1700, 3500], "expected": "PASS", "error": "WRONG_PLACEMENT", "onset": 2100, "error_end": 3300, "boundary": 3500},
    "occlusion": {"effect": "occlusion", "effect_from": 600, "expected": "HOLD_FOR_REVIEW"},
    "glare": {"effect": "glare", "effect_from": 600, "expected": "HOLD_FOR_REVIEW"},
    "blur": {"effect": "blur", "effect_from": 600, "expected": "HOLD_FOR_REVIEW"},
    "low_light": {"effect": "low_light", "effect_from": 600, "expected": "HOLD_FOR_REVIEW"},
    "mid_start": {"times": [0, 0, 0], "start": "unknown", "expected": "HOLD_FOR_REVIEW"},
    "sampling_gaps": {"sampling_gaps": True, "expected": "PASS"},
    "repeated_frames": {"repeated_frames": True, "expected": "HOLD_FOR_REVIEW"},
    "unknown_part": {"replace": ["spacer_left", "unknown_part"], "expected": "HOLD_FOR_REVIEW", "error": "UNRECOGNIZED_COMPONENT", "onset": 800, "boundary": 2000},
    "glare_wrong_part": {"effect": "glare", "effect_from": 600, "replace": ["spacer_right", "long_spacer"], "expected": "HOLD_FOR_REVIEW", "error": "WRONG_COMPONENT_CLASS", "onset": 800, "boundary": None, "error_observable": False},
    "blur_recovery": {"effect": "blur", "effect_from": 1000, "effect_to": 2100, "times": [400, 2600, 3800], "expected": "PASS"},
    "wrong_slot": {"replace": ["left_fastener", "short_spacer"], "expected": "REJECT_RECOMMENDATION", "error": "WRONG_PLACEMENT", "onset": 3200, "boundary": None},
}
SPLITS = {
    "train": ["normal_fast", "long_spacer", "wrong_order", "occlusion"],
    "validation": ["normal_slow", "red_spacer", "missing_screw", "low_light"],
    "test": list(SCENARIOS),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def _write_immutable(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Refusing to replace frozen fixture metadata: {path}")
    else:
        path.write_bytes(payload)


def protocol() -> dict[str, Any]:
    return {
        "schema_version": 1, "generator_version": VERSION,
        "source": SOURCE, "disclosure": "SYNTHETIC SOFTWARE TEST. Not filmed, staged human, industrial, or independently captured real-world data.",
        "width": SIZE[0], "height": SIZE[1], "fps": FPS,
        "frame_count": FRAME_COUNT, "codec": "MJPG", "slots": SLOTS,
        "colors_bgr": COLORS, "scenarios": SCENARIOS, "splits": SPLITS,
        "seeds": {"train": 1000, "validation": 2000, "test": 3000},
        "partition_limit": "Split seeds differ; all clips share one generated board grammar. This is software integration coverage, not real-world generalization.",
        "freeze_rule": "Write protocol before media generation; no test-driven threshold or fixture adjustment.",
        "timing_limit": "MJPG clips have fixed-rate replay timestamps. sampling_gaps skips synthetic source scene frames; it does not establish variable-rate capture handling.",
    }


def scene_state(scenario: str, timestamp_ms: int) -> dict[str, str]:
    cfg = SCENARIOS[scenario]
    first, second, third = cfg.get("times", [800, 2000, 3200])
    state: dict[str, str] = {}
    if timestamp_ms >= first:
        state.update(spacer_left="short_spacer", spacer_right="short_spacer")
    if timestamp_ms >= second:
        state["cover"] = "cover_plate"
    if timestamp_ms >= third:
        state.update(left_fastener="m3_bolt", right_fastener="m3_bolt")
    if cfg.get("missing"):
        state.pop(cfg["missing"], None)
    if cfg.get("replace"):
        slot, part = cfg["replace"]
        if slot in state:
            state[slot] = part
    if cfg.get("transient"):
        slot, part, begin, end = cfg["transient"]
        if begin <= timestamp_ms < end:
            state[slot] = part
    return state


def render_frame(scenario: str, frame_index: int, seed: int) -> tuple[np.ndarray, dict[str, Any]]:
    """Render one frame and separate generator truth; truth is not a model input."""
    cfg = SCENARIOS[scenario]
    # The generated source clock is intentionally distinct from decoded AVI time.
    source_index = frame_index
    if cfg.get("sampling_gaps"):
        source_index = frame_index + sum(frame_index >= k for k in (12, 24, 36, 48)) * 2
    timestamp_ms = source_index * 100
    rng = np.random.default_rng(seed * 10000 + frame_index)
    frame = np.full((SIZE[1], SIZE[0], 3), 220, dtype=np.uint8)
    noise = rng.integers(-3, 4, size=frame.shape, dtype=np.int16)
    frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    cv2.rectangle(frame, (60, 70), (580, 440), (175, 175, 175), 2)
    for rect in SLOTS.values():
        x1, y1, x2, y2 = rect
        cv2.rectangle(frame, (round(x1 * SIZE[0]), round(y1 * SIZE[1])), (round(x2 * SIZE[0]), round(y2 * SIZE[1])), (170, 170, 170), 1)
    state = scene_state(scenario, timestamp_ms)
    for slot, part in state.items():
        x1, y1, x2, y2 = SLOTS[slot]
        # A small per-clip offset and per-frame jitter are known generator effects,
        # not independent people, cameras or manufacturing sessions.
        jx, jy = rng.integers(-1, 2, size=2)
        cx = round((x1 + x2) * SIZE[0] / 2) + int(jx)
        cy = round((y1 + y2) * SIZE[1] / 2) + int(jy)
        color = COLORS[part]
        if part == "cover_plate":
            cv2.rectangle(frame, (cx - 40, cy - 17), (cx + 40, cy + 17), color, -1)
        elif part == "long_spacer":
            cv2.rectangle(frame, (cx - 37, cy - 12), (cx + 37, cy + 12), color, -1)
        else:
            cv2.circle(frame, (cx, cy), 17, color, -1, cv2.LINE_AA)
    effect_active = cfg.get("effect") and cfg.get("effect_from", 0) <= timestamp_ms < cfg.get("effect_to", 10**9)
    if effect_active:
        effect = cfg["effect"]
        if effect == "occlusion":
            cv2.rectangle(frame, (70, 75), (570, 440), (65, 65, 65), -1)
        elif effect == "glare":
            cv2.rectangle(frame, (70, 75), (570, 440), (255, 255, 255), -1)
        elif effect == "blur":
            frame = cv2.GaussianBlur(frame, (65, 65), 18)
        elif effect == "low_light":
            frame = np.clip(frame.astype(np.float32) * .16, 0, 255).astype(np.uint8)
    cv2.putText(frame, "SYNTHETIC SOFTWARE TEST", (14, 24), cv2.FONT_HERSHEY_SIMPLEX, .60, (25, 25, 25), 2, cv2.LINE_AA)
    cv2.putText(frame, f"Frame {frame_index:03d} | replay {frame_index * 100:04d} ms", (14, 463), cv2.FONT_HERSHEY_SIMPLEX, .44, (25, 25, 25), 1, cv2.LINE_AA)
    return frame, {"frame_index": frame_index, "replay_timestamp_ms": frame_index * 100, "source_frame_index": source_index, "source_timestamp_ms": timestamp_ms, "visible_scene_state": state, "effect_active": bool(effect_active)}


def generate(root: str | Path) -> list[dict[str, Any]]:
    """Generate or verify frozen media. Return annotation records for evaluators."""
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    videos = root / "videos"
    annotations = root / "annotations"
    videos.mkdir(exist_ok=True)
    annotations.mkdir(exist_ok=True)
    spec_bytes = _json_bytes(protocol())
    _write_immutable(root / "protocol.json", spec_bytes)
    result = []
    inputs = []
    number = 0
    for split, scenarios in SPLITS.items():
        for offset, scenario in enumerate(scenarios):
            number += 1
            cfg = SCENARIOS[scenario]
            clip_id = f"clip_{number:03d}"
            path = videos / f"{clip_id}.avi"
            seed = {"train": 1000, "validation": 2000, "test": 3000}[split] + offset
            truths = []
            writer = None
            if not path.exists():
                writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, SIZE)
                if not writer.isOpened():
                    raise RuntimeError("OpenCV MJPG video writer could not open")
            repeated = None
            try:
                for index in range(FRAME_COUNT):
                    frame, truth = render_frame(scenario, index, seed)
                    if cfg.get("repeated_frames") and index >= 5:
                        if repeated is None:
                            repeated, _ = render_frame(scenario, 4, seed)
                        frame = repeated.copy()
                        truth["repeated_source_frame"] = 4
                        truth["visible_scene_state"] = scene_state(scenario, 400)
                    if writer is not None:
                        writer.write(frame)
                    truths.append(truth)
            finally:
                if writer is not None:
                    writer.release()
            capture = cv2.VideoCapture(str(path))
            decoded = 0
            try:
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    if frame.shape != (SIZE[1], SIZE[0], 3):
                        raise ValueError(f"Unexpected decoded fixture shape: {path}")
                    decoded += 1
            finally:
                capture.release()
            if decoded != FRAME_COUNT:
                raise ValueError(f"Fixture incomplete: {path}: {decoded} frames")
            truth_payload = b"".join((json.dumps(row, sort_keys=True) + "\n").encode() for row in truths)
            _write_immutable(annotations / f"{clip_id}.frames.jsonl", truth_payload)
            record = {
                "clip_id": clip_id, "path": str(path), "sha256": sha256(path),
                "split": split, "source": SOURCE, "recipe_id": "demo_panel_v1",
                "start_state": cfg.get("start", "empty_confirmed"),
                "expected_status": cfg["expected"], "error_type": cfg.get("error"),
                "error_visible_from_ms": cfg.get("onset"),
                "error_end_ms": cfg.get("error_end"),
                "error_observable": cfg.get("error_observable", True),
                "last_safe_decision_ms": cfg.get("boundary"),
                "camera_id": "generated_planar_front", "fps_declared": FPS,
                "fps_observed": FPS, "frame_count": FRAME_COUNT,
                "scenario": scenario, "seed": seed,
                "ground_truth_verified_by": "deterministic_generator_not_human_real_video_review",
                "frame_annotations": str(annotations / f"{clip_id}.frames.jsonl"),
            }
            result.append(record)
            inputs.append({key: record[key] for key in ("clip_id", "path", "sha256", "split", "source", "recipe_id", "start_state")})
    _write_immutable(root / "annotations.jsonl", b"".join((json.dumps(row, sort_keys=True) + "\n").encode() for row in result))
    _write_immutable(root / "inputs.json", _json_bytes(inputs))
    _write_immutable(root / "manifest.json", _json_bytes({"version": VERSION, "protocol_sha256": hashlib.sha256(spec_bytes).hexdigest(), "clips": result, "count": len(result), "real_video_benchmark": {"status": "NOT_RUN", "reason": "No matched authorized real/staged video and human-reviewed labels acquired."}}))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    clips = generate(args.root)
    print(json.dumps({"status": "GENERATED_AND_DECODE_VERIFIED", "clips": len(clips), "split_counts": {s: sum(c["split"] == s for c in clips) for s in SPLITS}, "source": SOURCE, "root": str(args.root.resolve())}))


if __name__ == "__main__":
    main()
