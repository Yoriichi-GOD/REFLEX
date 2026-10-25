"""SYNTHETIC report fixtures validate exports, never detector performance."""
import csv
import json

from reflex_bench import report_v2


def test_runtime_export_retains_proof_stages_and_scope(tmp_path,monkeypatch):
    monkeypatch.setattr(report_v2,'OUT',tmp_path)
    monkeypatch.setattr(report_v2,'chart',lambda *a,**k:None)
    stats={'n':3,'mean_ms':2.,'std_ms':1.,'p50_ms':2.,'p90_ms':2.8,'p95_ms':2.9,'max_ms':3.}
    run={'summaries':{'v2':{'latency':{'server_handler_ms':stats},'stage_timings':{'decode_validate_ms':stats},
            'max_observed_rss_bytes':123456789,'peak_rss_bytes':223456789,'failed_requests':0,
            'concurrency2':{'requests':100,'elapsed_seconds':50.,'observed_requests_per_second':2.,'latency':stats}}},'scope':'SYNTHETIC fixture, not performance'}
    parent=tmp_path/'local-http-profile-r4';parent.mkdir()
    (parent/'summary.json').write_text(json.dumps(run))
    (parent/'VERIFICATION.json').write_text(json.dumps({'passed':True}))
    public=tmp_path/'aws-current-real-profile';public.mkdir()
    (public/'summary.json').write_text(json.dumps({'measured_statistics':{'http_roundtrip_ms':stats},'scope':'SYNTHETIC public fixture'}))
    (public/'VERIFICATION.json').write_text(json.dumps({'passed':True}))
    (public/'VERIFIED_STATISTICS.json').write_text(json.dumps({'cloudwatch_full_handler_ms':stats,'scope':'Coarse service data; no per-request CPU'}))
    report=tmp_path/'report';report.mkdir();sources={}
    report_v2.extra_tables(report,tmp_path,[],sources)
    read=lambda name:list(csv.DictReader((report/name).open(newline='')))
    runtimes=read('RUNTIME.csv')
    assert len(runtimes)==3 and all(r['correlation_verified']=='True' for r in runtimes)
    assert runtimes[-1]['span']=='cloudwatch_full_handler_ms'
    assert 'Nested/overlapping' in read('STAGE_TIMINGS.csv')[0]['scope']
    assert read('THROUGHPUT.csv')[0]['concurrency']=='2'
    assert 'not saturation' in read('THROUGHPUT.csv')[0]['scope']
    assert str(parent/'VERIFICATION.json') in sources and str(public/'VERIFIED_STATISTICS.json') in sources


def test_runtime_without_proof_is_not_reported_verified(tmp_path,monkeypatch):
    monkeypatch.setattr(report_v2,'OUT',tmp_path)
    parent=tmp_path/'aws-current-real-profile';parent.mkdir()
    (parent/'summary.json').write_text(json.dumps({'measured_statistics':{'http_roundtrip_ms':{'n':1,'p50_ms':4.}},'scope':'SYNTHETIC'}))
    report=tmp_path/'report';report.mkdir()
    report_v2.extra_tables(report,tmp_path,[],{})
    result=list(csv.DictReader((report/'RUNTIME.csv').open(newline='')))
    assert len(result)==1 and result[0]['correlation_verified']=='False'
