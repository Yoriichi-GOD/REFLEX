from __future__ import annotations
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from reflex_safety import benchmark, fixtures


def test_synthetic_split_protocol_declared_and_render_deterministic():
    spec = fixtures.protocol()
    assert spec['source'] == 'SYNTHETIC_SOFTWARE_TEST'
    assert {k: len(v) for k, v in spec['splits'].items()} == {'train': 4, 'validation': 4, 'test': 18}
    a, truth = fixtures.render_frame('normal_fast', 12, 1234)
    b, same_truth = fixtures.render_frame('normal_fast', 12, 1234)
    assert a.shape == (480, 640, 3)
    assert np.array_equal(a, b) and truth == same_truth
    c, _ = fixtures.render_frame('normal_fast', 13, 1234)
    assert not np.array_equal(a, c)


def test_generated_scene_has_actual_color_geometry_and_separate_truth():
    frame, truth = fixtures.render_frame('normal_fast', 35, 123)
    for slot, expected in [('spacer_left', (220, 80, 30)), ('cover', (40, 180, 40)), ('left_fastener', (20, 210, 230))]:
        x1, y1, x2, y2 = fixtures.SLOTS[slot]
        cx, cy = round((x1+x2)*320), round((y1+y2)*240)
        assert tuple(frame[cy, cx]) == expected
    assert truth['visible_scene_state']['left_fastener'] == 'm3_bolt'
    assert 'expected_status' not in truth


def test_transient_and_source_clock_are_explicit():
    assert fixtures.scene_state('wrong_slot_corrected', 2400)['left_fastener'] == 'short_spacer'
    assert fixtures.scene_state('wrong_slot_corrected', 4000)['left_fastener'] == 'm3_bolt'
    _, truth = fixtures.render_frame('sampling_gaps', 25, 123)
    assert truth['source_timestamp_ms'] > truth['replay_timestamp_ms']
    assert truth['replay_timestamp_ms'] == 2500


def test_immutable_protocol_does_not_silently_replace(tmp_path):
    path = tmp_path / 'protocol.json'
    fixtures._write_immutable(path, b'first')
    fixtures._write_immutable(path, b'first')
    with pytest.raises(ValueError, match='Refusing'):
        fixtures._write_immutable(path, b'second')


def test_evaluator_requires_real_supporting_ids_and_preserves_late_transient_miss():
    label = {'clip_id': 'clip_009', 'scenario': 'transient', 'expected_status': 'PASS', 'error_type': 'WRONG_PLACEMENT',
             'error_visible_from_ms': 100, 'error_end_ms': 1000, 'last_safe_decision_ms': 1100, 'frame_count': 60, 'fps_observed': 10}
    result = {'decision': {'status': 'PASS', 'reason_codes': []}, 'observations': [{'observation_id': 'real:1'}],
              'events': [{'reason_code': 'WRONG_PLACEMENT', 'source_timestamp_ms': 1200, 'evidence_ids': ['real:1']}], 'evidence': []}
    prediction = {'clip_id': 'clip_009', 'policy': 'agent', 'asset_sha256': 'sha', 'result': result, 'predicted_status': 'PASS', 'processing_latency_ms': 1, 'result_path': 'run.json'}
    row = benchmark.evaluate([prediction], {'clip_009': label})[0]
    assert row['status_correct']
    assert row['supported_matching_error'] and not row['timely_matching_error']
    result['events'][0]['evidence_ids'] = ['fabricated-missing-id']
    row = benchmark.evaluate([prediction], {'clip_009': label})[0]
    assert not row['supported_matching_error']


def test_final_only_fault_is_timed_at_actual_last_frame():
    result = {'decision': {'status': 'REJECT_RECOMMENDATION', 'reason_codes': ['WRONG_COMPONENT_CLASS'], 'supporting_observation_ids': ['real:1']},
              'observations': [{'observation_id': 'real:1'}], 'events': [], 'evidence': [{'id': 'frame-7', 'source_timestamp_ms': 700}]}
    found = benchmark._findings(result)
    assert found == [{'reason_code': 'WRONG_COMPONENT_CLASS', 'video_ms': 700, 'evidence_ids': ['real:1'], 'kind': 'final_checkpoint_decision'}]


def test_runtime_error_kept_in_denominator_and_no_metrics_fabricated():
    rows = [{'policy': 'single', 'expected_status': 'PASS', 'predicted_status': 'ERROR', 'expected_error_type': None, 'error_observable': True,
             'timely_matching_error': False, 'supported_error_types': [], 'expected_error_clip': False, 'duration_ms': 1000,
             'runtime_failure': 'decode error', 'status_correct': False, 'false_clear': False, 'normal_false_hold': False,
             'normal_false_reject': False, 'extra_inspections': None, 'onset_error_ms': None, 'lead_time_ms': None,
             'last_safe_decision_ms': None, 'early_matching_alert': False}]
    summary = benchmark.summarize(rows)
    assert summary['single']['n_clips'] == 1
    assert summary['single']['final_status_confusion']['PASS']['ERROR'] == 1
    assert summary['single']['final_status_accuracy'] == 0
    assert summary['single']['processing_latency_ms']['p50'] is None
    assert summary['single']['clip_level_error_detection']['recall'] is None


def test_annotation_read_happens_after_all_predictions_and_no_gt_arguments(tmp_path, monkeypatch):
    root = tmp_path / 'fixtures'
    root.mkdir()
    media = root / 'clip_001.avi'
    media.write_bytes(b'unit-only-runtime-spy')
    sha = hashlib.sha256(media.read_bytes()).hexdigest()
    item = {'clip_id': 'clip_001', 'path': str(media), 'sha256': sha, 'split': 'test', 'source': fixtures.SOURCE, 'recipe_id': 'demo_panel_v1', 'start_state': 'unknown'}
    (root / 'inputs.json').write_text(json.dumps([item]))
    (root / 'protocol.json').write_text('{}')
    (root / 'annotations.jsonl').write_text(json.dumps({**item, 'scenario': 'label-must-not-reach-runtime', 'expected_status': 'HOLD_FOR_REVIEW', 'error_type': None, 'frame_count': 60, 'fps_observed': 10}) + '\n')
    calls = []
    original = Path.read_text
    def read_spy(path, *args, **kwargs):
        if path.name == 'annotations.jsonl':
            assert len(calls) == 3
            assert len(list((tmp_path / 'run' / 'predictions').glob('*.json'))) == 3
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read_spy)
    def runtime(path, recipe, **kwargs):
        assert path == media
        assert recipe == {'unit_recipe': True}
        assert set(kwargs) == {'policy', 'calibration_quad', 'start_state', 'final_checkpoint', 'on_frame'}
        assert kwargs['start_state'] == 'unknown'
        calls.append(kwargs['policy'])
        return {'decision': {'status': 'HOLD_FOR_REVIEW', 'reason_codes': []}, 'events': [], 'observations': [], 'evidence': [], 'source_sha256': sha}
    result = benchmark.run(root, tmp_path / 'run', analyzer=runtime, recipe={'unit_recipe': True})
    assert calls == ['single', 'random', 'agent']
    assert result['prediction_rows'] == 3
    assert result['real_video_benchmark']['status'] == 'NOT_RUN'
    assert all(s['final_status_correct'] == 1 for s in result['summary'].values())


def test_input_label_leakage_is_rejected_before_inference(tmp_path):
    media = tmp_path / 'clip.avi'
    media.write_bytes(b'not-used')
    item = {'clip_id': 'clip_1', 'path': str(media), 'sha256': fixtures.sha256(media), 'split': 'test', 'source': fixtures.SOURCE,
            'recipe_id': 'demo_panel_v1', 'start_state': 'unknown', 'expected_status': 'PASS'}
    (tmp_path / 'inputs.json').write_text(json.dumps([item]))
    with pytest.raises(ValueError, match='label leakage'):
        benchmark.run(tmp_path, tmp_path / 'run', analyzer=lambda *a, **k: pytest.fail('Runtime must not run'), recipe={})
