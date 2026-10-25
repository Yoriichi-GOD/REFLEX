"""Synthetic fixtures test evaluator accounting, not detector accuracy."""
import json
from types import SimpleNamespace
import cv2
import numpy as np
from reflex_bench import improve_v2 as runner
from reflex_bench.data import Case


def test_detail_control_accounting_and_budget(tmp_path,monkeypatch):
    cases=[]
    for i in range(4):
        path=tmp_path/f'fixture-{i}.png'
        assert cv2.imwrite(str(path),np.full((32,40,3),40+i*40,np.uint8))
        cases.append(Case(str(i),path,None,i%2,'SYNTHETIC_FIXTURE'))
    class Model:
        config=SimpleNamespace(seed=20261024)
        metadata={'image_threshold':2.,'pass_threshold':1.,'pixel_threshold':1.,
                  'detail_thresholds':{'chosen':2.,'random':2.,'all4':2.}}
        def predict(self,image):
            score=float(image.mean()/60)
            return {'score':score,'score_map':np.full(image.shape[:2],score,np.float32)}
    model=Model();model.detail_model=Model()
    monkeypatch.setattr(runner,'OUT',tmp_path/'output')
    monkeypatch.setattr(runner,'check_freeze',lambda:None)
    monkeypatch.setattr(runner,'eval_cases',lambda category,split:cases)
    monkeypatch.setattr(runner.PatchMemoryV2,'load',lambda *a:model)
    monkeypatch.setattr(runner,'inspect_quality',lambda image:{'flags':[]})
    monkeypatch.setattr(runner,'extract_regions',lambda *a:[{'bbox_xyxy':[0,0,40,32]}])
    monkeypatch.setattr(runner,'checked_mask',lambda case,image:np.pad(np.ones((8,8),bool),((0,24),(0,32))) if case.label else np.zeros(image.shape[:2],bool))
    runner.detail_controls('fixture','final')
    result=json.loads((tmp_path/'output/detail_controls/fixture/final/metrics.json').read_text())
    assert result['active_trigger_count']==2
    assert result['active_trace_complete_count']==2
    assert result['operations_per_image']=={'chosen':1,'random':1,'all4':4}
    assert set(result['fixed_budget_fusion'])=={'full_chosen','full_random','full_all4'}
    for name,stats in result['fixed_budget_fusion'].items():
        assert stats['image']['sample_count']==4
        assert stats['extra_calls_per_case']==(4 if name=='full_all4' else 1)
    for stats in result['selective_policies'].values():
        assert sum(stats['flips'].values())==4


def test_gallery_renders_saved_predictions_only(tmp_path,monkeypatch):
    from reflex_bench import report_v2
    image=tmp_path/'fixture.png'
    assert cv2.imwrite(str(image),np.full((32,40,3),100,np.uint8))
    parent=tmp_path/'results/evaluation/candle/dense128_region'
    (parent/'maps').mkdir(parents=True)
    np.save(parent/'maps/0000.npy',np.ones((32,40),np.float32))
    runner.csv_write(parent/'per_case.csv',[{'case_id':'fixture','label':1,'image_sha256':runner.digest(image),
        'pixel_threshold':1.,'score':.5,'threshold':1.,'pass_threshold':.8,'decision':'PASS','second_look':False}])
    monkeypatch.setattr(report_v2,'OUT',tmp_path/'results')
    monkeypatch.setattr(report_v2,'eval_cases',lambda *a:[Case('fixture',image,None,1,'SYNTHETIC_FIXTURE')])
    monkeypatch.setattr(report_v2,'checked_mask',lambda case,img:np.zeros(img.shape[:2],bool))
    report=tmp_path/'report';report.mkdir()
    assert report_v2.gallery(report,[('candle','replay',[])])==1
    result=json.loads((report/'gallery/cases.json').read_text())
    assert result[0]['bucket']=='false_clear'
    assert (report/'gallery/candle_replay_0000.jpg').exists()
    assert '1 saved cases' in (report/'gallery/index.html').read_text()


def test_scientific_chart_exports_all_formats(tmp_path):
    from reflex_bench.report_v2 import chart
    chart(tmp_path/'synthetic.svg','SYNTHETIC fixture — not benchmark results',['A','B'],[('Example',[.2,.4])])
    assert all((tmp_path/f'synthetic{ext}').exists() for ext in ('.svg','.png','.pdf'))
    assert cv2.imread(str(tmp_path/'synthetic.png')).shape[0]>100
