import importlib.util
import hashlib
import json
import os
import pytest

from reflex_bench.runtime_stats_v2 import memory_snapshot
from reflex_bench.improve_v2 import _members


def test_actual_process_memory_counter_is_positive():
    value=memory_snapshot()
    assert value['rss_bytes']>0 and value['peak_rss_bytes']>=value['rss_bytes'] and value['ram_bytes']>value['rss_bytes']


def test_membership_remains_normal_only_disjoint():
    old=_members('cashew')
    assert {k:len(v) for k,v in old.items()}=={'fit':324,'calibration':90,'development':36}


def test_sealed_manifest_tamper_is_rejected(tmp_path,monkeypatch):
    import reflex_bench.improve_v2 as module
    path=tmp_path/'fit.json';path.write_text('[]')
    (tmp_path/'freeze.json').write_text(json.dumps({'manifest_sha256':{'fit.json':hashlib.sha256(path.read_bytes()).hexdigest()}}))
    monkeypatch.setattr(module,'manifest_root',lambda category:tmp_path)
    assert module.verified_manifest('capsules','fit')==[]
    path.write_text('[1]')
    with pytest.raises(RuntimeError,match='manifest changed'):module.verified_manifest('capsules','fit')


def test_worker_pid_header_only_in_benchmark_mode(client,monkeypatch):
    monkeypatch.delenv('REFLEX_BENCHMARK_MODE',raising=False)
    assert 'x-reflex-process-id' not in client.get('/api/health').headers
    monkeypatch.setenv('REFLEX_BENCHMARK_MODE','1')
    response=client.get('/api/health')
    assert int(response.headers['x-reflex-process-id'])==os.getpid()
    assert float(response.headers['x-reflex-server-ms'])>=0
