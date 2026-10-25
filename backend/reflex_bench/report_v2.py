"""Render saved v2 outcomes; do not choose a test winner or alter models."""
from __future__ import annotations
import csv
import hashlib
import html
import json
from pathlib import Path

import cv2
import numpy as np

from reflex_bench.improve_v2 import OUT,ROOT,ARMS,check_freeze,eval_cases,checked_mask
from reflex_bench.metrics import binary_auroc
from app.core.model import render_evidence


def load(path):return json.loads(path.read_text())


def rows(path):
    with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def interval(k,n):
    if not n:return None
    z=1.95996398454;p=k/n;d=1+z*z/n
    center=(p+z*z/(2*n))/d
    radius=z*((p*(1-p)/n+z*z/(4*n*n))**.5)/d
    return [max(0,center-radius),min(1,center+radius)]


def fmt(value):return 'Not measured' if value is None else f'{value:.4f}' if isinstance(value,float) else str(value)


def chart(path,title,labels,series,maximum=1):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure,axis=plt.subplots(figsize=(11.6,max(3,len(labels)*.58+1.5)),layout='constrained')
    y=np.arange(len(labels));height=.7/max(len(series),1)
    for j,(name,values) in enumerate(series):
        values=np.array([np.nan if v is None else v for v in values],dtype=float)
        bars=axis.barh(y+(j-(len(series)-1)/2)*height,values,height=height,label=name)
        axis.bar_label(bars,fmt='%.4f',fontsize=7,padding=3)
    axis.set(yticks=y,yticklabels=labels,xlim=(0,maximum*1.10),title=title);axis.invert_yaxis()
    axis.legend(loc='upper center',bbox_to_anchor=(.5,-.05),ncols=len(series));axis.grid(axis='x',alpha=.2)
    for suffix in ('.svg','.png','.pdf'):figure.savefig(path.with_suffix(suffix),dpi=180)
    plt.close(figure)
    return


def gallery(report,groups):
    """Every saved primary case, in membership order; no model inference or selection."""
    directory=report/'gallery';directory.mkdir(exist_ok=True)
    cards=[];index=[]
    for cat,split,_ in groups:
        parent=OUT/'evaluation'/cat/('' if split=='replay' else split)/'dense128_region'
        if not (parent/'per_case.csv').exists():continue
        saved=rows(parent/'per_case.csv');cases=eval_cases(cat,split)
        assert len(saved)==len(cases)
        for number,(record,case) in enumerate(zip(saved,cases)):
            assert record['case_id']==case.case_id
            image=cv2.imread(str(case.image_path))
            assert hashlib.sha256(case.image_path.read_bytes()).hexdigest()==record['image_sha256']
            score=np.load(parent/'maps'/f'{number:04d}.npy',allow_pickle=False)
            truth=checked_mask(case,image)
            heat,overlay,_=render_evidence(image,score,float(record['pixel_threshold']))
            gt=image.copy()
            contours,_=cv2.findContours(truth.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(gt,contours,-1,(0,255,0),max(2,round(max(image.shape[:2])/400)))
            panels=[]
            for name,panel in zip(('Original real photograph','Model heatmap','Model overlay','Evaluator ground truth'),(image,heat,overlay,gt)):
                h,w=panel.shape[:2];scale=min(300/w,280/h)
                thumb=cv2.resize(panel,(max(1,round(w*scale)),max(1,round(h*scale))))
                canvas=np.full((320,310,3),245,dtype=np.uint8)
                x=(310-thumb.shape[1])//2;y=30+(280-thumb.shape[0])//2
                canvas[y:y+thumb.shape[0],x:x+thumb.shape[1]]=thumb
                cv2.putText(canvas,name,(6,20),cv2.FONT_HERSHEY_SIMPLEX,.44,(30,30,30),1,cv2.LINE_AA)
                panels.append(canvas)
            filename=f'{cat}_{split}_{number:04d}.jpg'
            assert cv2.imwrite(str(directory/filename),np.hstack(panels),[cv2.IMWRITE_JPEG_QUALITY,88])
            label=int(record['label']);decision=record['decision']
            bucket=('false_clear' if decision=='PASS' else 'detected_defect' if decision=='DEFECT_FOUND' else 'defect_review') if label else ('false_alert' if decision=='DEFECT_FOUND' else 'correct_clear' if decision=='PASS' else 'normal_review')
            info={'category':cat,'population':split,'case_id':case.case_id,'label':label,'decision':decision,'bucket':bucket,
                  'image_sha256':record['image_sha256'],'score':float(record['score']),'threshold':float(record['threshold']),
                  'pass_threshold':float(record['pass_threshold']),'second_look':record['second_look'],
                  'gallery_image':filename,'saved_map_sha256':hashlib.sha256((parent/'maps'/f'{number:04d}.npy').read_bytes()).hexdigest()}
            roi_html=''
            if record.get('detail_bbox_json'):
                box=json.loads(record['detail_bbox_json']);x1,y1,x2,y2=box
                assert 0<=x1<x2<=image.shape[1] and 0<=y1<y2<=image.shape[0]
                roi_name=filename.replace('.jpg','_chosen_detail.png')
                assert cv2.imwrite(str(directory/roi_name),image[y1:y2,x1:x2])
                info.update(detail_bbox_xyxy=box,detail_source_dimensions=[x2-x1,y2-y1],detail_image=roi_name)
                roi_html=f'<details><summary>Actual selected detail from the same photograph ({x2-x1}×{y2-y1} source pixels)</summary><img loading="lazy" src="{roi_name}" style="max-width:500px" alt="Actual chosen source crop"><p>Detail score {html.escape(record.get("detail_score",""))}; separately calibrated threshold {html.escape(record.get("detail_threshold",""))}. This is not another camera view.</p></details>'
            index.append(info)
            heading=html.escape(f'{cat} / {split} / {case.case_id} — {bucket}: {decision}')
            details=html.escape(f"score={info['score']:.6f}; PASS≤{info['pass_threshold']:.6f}; defect>{info['threshold']:.6f}; second look={info['second_look']}")
            trace=html.escape(json.dumps(json.loads(record.get('agent_trace_json') or '[]'),indent=2))
            cards.append(f'<article data-category="{cat}" data-bucket="{bucket}"><h2>{heading}</h2><p>{details}</p><img loading="lazy" src="{filename}" width="1240" height="320" alt="Original, heatmap, overlay and evaluator mask for {heading}">{roi_html}<details><summary>Saved agent trace</summary><pre style="white-space:pre-wrap">{trace}</pre></details><p class="hash">Source SHA256: {info["image_sha256"]}</p></article>')
    options=lambda values:''.join(f'<option>{html.escape(v)}</option>' for v in sorted(set(values)))
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><title>REFLEX v2 — complete real-image gallery</title>
<style>body{font:15px system-ui;margin:24px;background:#f4f6f8;color:#172534}header{max-width:1100px}article{background:white;margin:20px 0;padding:16px;border:1px solid #ccd4dd;border-radius:8px}h2{font-size:17px}img{width:100%;max-width:1240px;height:auto}.hash{font:12px monospace;overflow-wrap:anywhere}select{padding:8px;margin:8px}article[hidden]{display:none}</style>
<header><h1>REFLEX v2: every evaluated primary case</h1><p>Real public VisA photographs. All cases appear in frozen membership order. Green contours are evaluator ground truth, supplied after prediction. Heatmaps use the frozen normal pixel threshold; saved evaluation maps have maximum side256 and are enlarged for display. Detail crops use the same photograph. Review is unresolved, not a correct detection.</p><p>Candle/cashew are reused development replay. Other categories use custom published-test partitions; physical capture independence is unknown.</p>'''
    document+=f'<p><b>{len(index)} saved cases</b> · Category <select id="category"><option value="">All</option>{options(r["category"] for r in index)}</select> Outcome <select id="bucket"><option value="">All</option>{options(r["bucket"] for r in index)}</select> <span id="count"></span></p></header>'
    document+='<p>Dataset: VisA, Amazon Science / Zou et al., ECCV2022. CC BY4.0. <a href="https://github.com/amazon-science/spot-diff">Publisher, citation and license</a>. Model/evaluator derivatives are identified above.</p>'
    document+='\n'.join(cards)+'''<script>const c=document.querySelector('#category'),b=document.querySelector('#bucket');function filter(){let n=0;document.querySelectorAll('article').forEach(a=>{a.hidden=!!((c.value&&a.dataset.category!==c.value)||(b.value&&a.dataset.bucket!==b.value));if(!a.hidden)n++});document.querySelector('#count').textContent=n+' shown'}c.onchange=b.onchange=filter;filter()</script></html>'''
    (directory/'index.html').write_text(document,encoding='utf-8')
    (directory/'cases.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
    return len(index)


def save_table(path,records):
    if not records:return
    fields=list(dict.fromkeys(key for row in records for key in row))
    with path.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(records)


def extra_tables(report,figures,all_rows,sources):
    policies=[];fusion=[];stress=[];localization=[];native=[];runtime=[];stages=[];throughput=[];macro=[]
    for path in (OUT/'detail_controls').rglob('metrics.json') if (OUT/'detail_controls').exists() else []:
        value=load(path);parts=path.parent.relative_to(OUT/'detail_controls').parts
        identity={'category':parts[0],'population':parts[1] if len(parts)>1 else 'replay'}
        for name,result in value.get('selective_policies',{}).items():
            d=result['decisions']
            policies.append({**identity,'policy':name,**{k:v for k,v in d.items() if not isinstance(v,dict)},
                             **d['confusion_matrix_on_resolved'],
                             'logical_extra_model_calls':result['logical_extra_model_calls'],
                             'active_trigger_count':value['active_trigger_count'],'active_trace_complete_count':value['active_trace_complete_count'],
                             'flips_json':json.dumps(result['flips']),'scope':result['execution_scope']})
        for name,result in value.get('fixed_budget_fusion',{}).items():
            fusion.append({**identity,'control':name,'extra_calls_per_case':result['extra_calls_per_case'],
                           **{f'image_{k}':v for k,v in result['image'].items() if not isinstance(v,dict)},
                           **{f'image_{k}':v for k,v in result['image']['confusion_matrix'].items()},
                           **{f'pixel_{k}':v for k,v in result['pixel']['pixel_confusion_matrix'].items()},
                           **{f'pixel_{k}':v for k,v in result['pixel'].items() if not isinstance(v,dict)}})
    for path in (OUT/'robustness').rglob('metrics.json') if (OUT/'robustness').exists() else []:
        value=load(path);parts=path.parent.relative_to(OUT/'robustness').parts
        for name,result in value['variants'].items():
            stress.append({'category':parts[0],'population':parts[1] if len(parts)>1 else 'replay','transform':name,
                           **{f'image_{k}':v for k,v in result['image'].items() if not isinstance(v,dict)},
                           **{f'image_{k}':v for k,v in result['image']['confusion_matrix'].items()},
                           **{f'pixel_{k}':v for k,v in result['pixel'].items() if not isinstance(v,dict)},
                           **{f'decision_{k}':v for k,v in result['decisions'].items() if not isinstance(v,dict)},
                           **{f'decision_{k}':v for k,v in result['decisions']['confusion_matrix_on_resolved'].items()},
                           'second_look_count':result['second_look_count']})
    for path in (OUT/'evaluation').rglob('dense128_region/metrics.json') if (OUT/'evaluation').exists() else []:
        value=load(path);parts=path.parent.parent.relative_to(OUT/'evaluation').parts
        identity={'category':parts[0],'population':parts[1] if len(parts)>1 else 'replay'}
        for name,result in value.get('localization_ablation',{}).items():
            localization.append({**identity,'configuration':name,**{k:v for k,v in result.items() if not isinstance(v,dict)},
                                 **result.get('pixel_confusion_matrix',{})})
        if value.get('native_pixel_metrics'):native.append({**identity,**value['native_pixel_metrics']})
    for label,relative in (('aws_fargate_loopback','fargate-profile/summary.json'),('local_loopback_r4','local-http-profile-r4/summary.json')):
        path=OUT/relative
        if not path.exists():continue
        value=load(path);sources[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        verification=path.parent/'VERIFICATION.json'
        verified=verification.exists() and load(verification).get('passed') is True
        if verification.exists():sources[str(verification)]=hashlib.sha256(verification.read_bytes()).hexdigest()
        for variant,result in value['summaries'].items():
            for span,stats in result['latency'].items():
                runtime.append({'environment':label,'variant':variant,'span':span,**stats,'max_observed_rss_bytes':result['max_observed_rss_bytes'],
                                'peak_rss_bytes':result['peak_rss_bytes'],'failed_requests':result['failed_requests'],
                                'correlation_verified':verified,'scope':value['scope']})
            for span,stats in result.get('stage_timings',{}).items():
                stages.append({'environment':label,'variant':variant,'span':span,**stats,
                               'correlation_verified':verified,'scope':'Nested/overlapping spans; do not sum quantiles. '+value['scope']})
            concurrent=result.get('concurrency2',{})
            if concurrent:
                throughput.append({'environment':label,'variant':variant,'concurrency':2,
                                   **{k:v for k,v in concurrent.items() if not isinstance(v,dict)},
                                   'correlation_verified':verified,'scope':'Finite two-request concurrency probe; not saturation capacity. '+value['scope']})
        if label=='aws_fargate_loopback':
            chart(figures/'aws_server_latency.svg','Dedicated AWS task: server-handler latency (milliseconds)',
                  ['v1','v2'],[(name,[value['summaries'][v]['latency']['server_handler_ms'][key] for v in ('v1','v2')]) for name,key in (('p50','p50_ms'),('p95','p95_ms'))],
                  maximum=max(value['summaries'][v]['latency']['server_handler_ms']['p95_ms'] for v in ('v1','v2'))*1.15)
    path=OUT/'aws-current-real-profile/summary.json'
    if path.exists():
        value=load(path);sources[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        proof=path.parent/'VERIFICATION.json'
        verified=proof.exists() and load(proof).get('passed') is True
        if proof.exists():sources[str(proof)]=hashlib.sha256(proof.read_bytes()).hexdigest()
        for span,stats in value['measured_statistics'].items():runtime.append({'environment':'aws_public_segmented','variant':'v1','span':span,**stats,'correlation_verified':verified,'scope':value['scope']})
        verified_stats=path.parent/'VERIFIED_STATISTICS.json'
        if verified and verified_stats.exists():
            measured=load(verified_stats);sources[str(verified_stats)]=hashlib.sha256(verified_stats.read_bytes()).hexdigest()
            runtime.append({'environment':'aws_public_segmented','variant':'v1','span':'cloudwatch_full_handler_ms',
                            **measured['cloudwatch_full_handler_ms'],'correlation_verified':True,'scope':measured['scope']})
    for split in ('replay','development','final'):
        for arm in ('v1','classical_cv5',*ARMS):
            selected=[r for r in all_rows if r['population']==split and r['arm']==arm]
            if not selected:continue
            macro.append({'population':split,'arm':arm,'category_count':len(selected),'categories':','.join(r['category'] for r in selected),
                          **{key:float(np.mean([r[key] for r in selected])) for key in ('auroc','ap','recall','normal_fpr','pixel_auroc','pixel_ap','pixel_iou')},
                          'scope':'Equalcategoryweights;populationskeptseparate;notpooledimageROC'})
    for filename,records in (('AGENT_POLICIES.csv',policies),('DETAIL_FUSION.csv',fusion),('ROBUSTNESS.csv',stress),
                             ('LOCALIZATION_ABLATIONS.csv',localization),('NATIVE_LOCALIZATION.csv',native),('RUNTIME.csv',runtime),
                             ('STAGE_TIMINGS.csv',stages),('THROUGHPUT.csv',throughput),('MACRO_RESULTS.csv',macro)):
        save_table(report/filename,records)


def main():
    check_freeze()
    report=OUT/'report';report.mkdir(exist_ok=True)
    figures=report/'figures';figures.mkdir(exist_ok=True)
    all_rows=[];sources={};comparisons={}
    lines=['# REFLEX v2: measured experiments','',
           'The predeclared primary is dense128_region. Every fixed arm and seed remains reported. Review is unresolved evidence, not a correct defect detection. No factory-readiness, official-PatchCore equivalence or state-of-the-art claim is supported.','',
           'Populations stay separate: candle/cashew are reused350-case development replay. PCB1, capsules and chewinggum have custom diagnostic development and sealed final partitions of previously published VisA images; these are new-to-REFLEX categories, not fresh factory captures or proven lot-independent validation.','',
           'Thresholds use normal calibration only. Review boundaries use reserved normal training-development cases under the fixed workload budget. No test label selects a threshold, scoring method, seed or release winner.','',
           '| Category / population | Arm | N | AUROC | AP | TP / FP / FN / TN | Raw recall | Normal FPR | Automatic false clears | Reviews | Decision coverage |',
           '|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|']
    groups=[]
    for cat in ('candle','cashew','pcb1','capsules','chewinggum'):
        for split in (('replay',) if cat in ('candle','cashew') else ('development','final')):
            parent=OUT/'evaluation'/cat/('' if split=='replay' else split)
            base_path=parent/'v1_recomputed_metrics/metrics.json' if split=='replay' else parent/'v1_fresh/metrics.json'
            if not base_path.exists():continue
            baseline=load(base_path)
            found=[]
            for arm in ('v1','classical_cv5',*ARMS):
                path=base_path if arm=='v1' else parent/arm/'metrics.json'
                if not path.exists():continue
                data=load(path);sources[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
                m=data['image_metrics'];d=data['decisions'];cm=m['confusion_matrix'];p=data['pixel_metrics']
                record={'category':cat,'population':split,'arm':arm,'primary':arm=='dense128_region',
                        'n':m['sample_count'],'auroc':m['auroc'],'ap':m['average_precision'],**cm,
                        'recall':m['recall'],'normal_fpr':m['false_positive_rate_on_negatives'],
                        'automatic_false_clears':d['false_clear_count'],'final_false_defect_alerts':d['false_defect_count'],
                        'final_detected_defects':d['confusion_matrix_on_resolved']['TP'],
                        'final_defect_recall_all_defects':d['confusion_matrix_on_resolved']['TP']/m['positive_count'],
                        'final_normal_false_alert_rate':d['false_defect_count']/m['negative_count'],
                        'final_false_clear_rate':d['false_clear_count']/m['positive_count'],
                        'defect_reviews':m['positive_count']-d['confusion_matrix_on_resolved']['TP']-d['false_clear_count'],
                        'normal_reviews':m['negative_count']-d['confusion_matrix_on_resolved']['TN']-d['false_defect_count'],
                        'review_count':d['abstention_count'],'coverage':d['coverage'],
                        'pixel_auroc':p['pixel_auroc'],'pixel_precision':p['pixel_precision'],'pixel_recall':p['pixel_recall'],
                        'pixel_iou':p['pixel_iou_at_frozen_normal_threshold'],'pixel_ap':p['pixel_average_precision'],
                        'au_pro_fpr_0_30':p['au_pro_fpr_0_30'],
                        'normal_count':m['negative_count'],'defect_count':m['positive_count'],
                        'pixel_dice':p['pixel_dice_at_frozen_normal_threshold'],'pixel_threshold':p['pixel_threshold'],
                        'pixel_sample_count':p['pixel_sample_count'],'au_pro_method':p.get('au_pro_method','Not recorded'),
                        'model_sha256':data.get('model_sha256','Not recorded'),
                        'feature_dimensions':data.get('config',{}).get('dimensions','Not recorded'),
                        'seed':data.get('config',{}).get('seed','Not recorded')}
                all_rows.append(record);found.append(record)
                lines.append(f"| {cat} / {split} | {arm} | {record['n']} | {fmt(record['auroc'])} | {fmt(record['ap'])} | {' / '.join(str(cm[k]) for k in ('TP','FP','FN','TN'))} | {fmt(record['recall'])} | {fmt(record['normal_fpr'])} | {record['automatic_false_clears']} | {record['review_count']} | {fmt(record['coverage'])} |")
            if not found:continue
            groups.append((cat,split,found))
            chart(figures/f'{cat}_{split}_detection.svg',f'{cat} / {split}: fixed arms',
                  [r['arm'] for r in found],[('AUROC',[r['auroc'] for r in found]),('Raw recall',[r['recall'] for r in found]),('Normal FPR',[r['normal_fpr'] for r in found])])
            primary_path=parent/'dense128_region/per_case.csv'
            baseline_csv=ROOT/f'reports/improvement_20261024/{cat}/per_case.csv' if split=='replay' else parent/'v1_fresh/per_case.csv'
            if primary_path.exists() and baseline_csv.exists():
                a,b=rows(baseline_csv),rows(primary_path)
                old={r['case_id']:r for r in a}
                assert all(old[r['case_id']]['image_sha256']==r['image_sha256'] for r in b)
                y=np.array([int(r['label']) for r in b]);before=np.array([float(old[r['case_id']]['score']) for r in b]);after=np.array([float(r['score']) for r in b])
                rng=np.random.default_rng(20261024);indices=[np.flatnonzero(y==k) for k in (0,1)];delta=[]
                for _ in range(2000):
                    ix=np.concatenate([rng.choice(g,len(g),replace=True) for g in indices])
                    delta.append(binary_auroc(y[ix],after[ix])-binary_auroc(y[ix],before[ix]))
                key=f'{cat}_{split}'
                comparisons[key]={'auroc_delta':binary_auroc(y,after)-binary_auroc(y,before),
                                  'paired_stratified_bootstrap_delta95':np.quantile(delta,[.025,.975]).tolist(),'replicates':2000,'seed':20261024,
                                  'scope':'finitecases;notcorrectionfortestreuse,capturedependenceormethodselection',
                                  'automatic_false_clear_binomial95':interval(sum(int(r['label']) and r['decision']=='PASS' for r in b),int(y.sum()))}
    if all_rows:
        with (report/'ALL_RESULTS.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(all_rows[0]));w.writeheader();w.writerows(all_rows)
    lines+=['','## Final policy outcomes, with original denominators','',
            'Raw threshold confusion above is separate from the final policy. Detail inspection can increase both true and false alerts. Defect recall below divides by all defective images, including unresolved reviews; reviews are never credited as detections.','',
            '| Category / population | Arm | Detected defects | Automatic defect passes | False defect alerts on normals | Defect / normal reviews | Final defect recall | Final normal false-alert rate |',
            '|---|---|---:|---:|---:|---|---:|---:|']
    for r in all_rows:
        lines.append(f"| {r['category']} / {r['population']} | {r['arm']} | {r['final_detected_defects']} | {r['automatic_false_clears']} | {r['final_false_defect_alerts']} | {r['defect_reviews']} / {r['normal_reviews']} | {fmt(r['final_defect_recall_all_defects'])} | {fmt(r['final_normal_false_alert_rate'])} |")
    lines+=['','## Localization at frozen normal thresholds','',
            '| Category / population | Arm | Pixel AUROC | Pixel AP | Precision | Recall | IoU | AU-PRO |','|---|---|---:|---:|---:|---:|---:|---:|']
    for r in all_rows:
        lines.append(f"| {r['category']} / {r['population']} | {r['arm']} | "+' | '.join(fmt(r[k]) for k in ('pixel_auroc','pixel_ap','pixel_precision','pixel_recall','pixel_iou','au_pro_fpr_0_30'))+' |')
    lines+=['','Sigma1/4 and normal pixel quantiles99.5/99.75/99.9 remain in each primary metrics.json. High pixel AUROC does not establish accurate masks. Compare precision and lost defect pixels beside IoU.','',
            '## Second-inspection controls','',
            'The batch control executor computes all four tile predictions and then reuses chosen/random results. One chosen versus one random describes matched hypothetical policy budgets, not two independently timed end-to-end agents. The primary runtime actually makes at most one extra call on triggered cases; uncached API profiling measures its real overhead. All crops come from the same photograph and add no physical camera view.','',
            '| Category / population | Control | N | Recall | Normal FPR | Recovered full-model false clears | New alerts on full-clear normals |','|---|---|---:|---:|---:|---:|---:|']
    for path in (OUT/'detail_controls').rglob('metrics.json') if (OUT/'detail_controls').exists() else []:
        x=load(path);rel=path.parent.relative_to(OUT/'detail_controls');sources[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        for name,m in x['controls'].items():
            lines.append(f"| {rel.as_posix()} | {name} | {m['sample_count']} | {fmt(m['recall'])} | {fmt(m['false_positive_rate_on_negatives'])} | {m['recovered_full_false_clears']} | {m['new_alerts_on_full_clear_normals']} |")
    lines+=['','## Robustness','',
            'Every stress row is a deterministic derived image, not an independent real capture. Defect-downsize uses evaluator-only masks to create a synthetic diagnostic. Central occlusion is median-color fill over20%width x20%height (~4%area). Raw anomaly rates and routed decisions remain separate.','',
            '| Category / population | Transform | AUROC | Recall | Normal FPR | False clears | Reviews |','|---|---|---:|---:|---:|---:|---:|']
    for path in (OUT/'robustness').rglob('metrics.json') if (OUT/'robustness').exists() else []:
        x=load(path);rel=path.parent.relative_to(OUT/'robustness');sources[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        for name,v in x['variants'].items():
            m=v['image'];d=v['decisions']
            lines.append(f"| {rel.as_posix()} | {name} | {fmt(m['auroc'])} | {fmt(m['recall'])} | {fmt(m['false_positive_rate_on_negatives'])} | {d['false_clear_count']} | {d['abstention_count']} |")
    lines+=['','## Runtime and cloud evidence','',
            'Accuracy replay uses a verified-feature cache; its elapsed times are engineering observations, not production latency. Use uncached latency/API profiles. Dedicated Fargate measurements are loopback HTTP within a finite1vCPU/2GiBtask, separate from public internet roundtrip. The public real-image profile uses the existing10/600secondguard and is pacing-limited, not saturation capacity. Sources and measured counts accompany their individual summaries.','',
            'The first local HTTP attempt failed during fallback-profile bootstrap before inference. R2 completed, but its ~4MiB memory values measured the Windows launcher and are invalid as worker memory. Corrected worker-PID profiling is required; keep all failed/exploratory logs. Concurrent training/reference jobs during R2 also limit its timing interpretation.','',
            'Capture suitability remains advisory. See ../suitability_v2_20261024/REPORT.md;40/200defective older images also trigger warnings, so warnings must not be credited as successful retakes or detections. No independently labeled physical suitability set exists.','',
            'Official upstream PatchCore and its disk-backed feature-assembly variant are separate references. Preserve original allocation failures, native224center-crop coverage, squared-L2 scoring and full10%memory details. REFLEX scores are not official PatchCore results.','',
            '## Release decision','',
            'This report does not promote a test winner. The original deployed release and delivered paper/PPT remain historical evidence. A candidate release requires a separate explicit acceptance assessment using false clears, normal false alerts, unresolved review burden, localization and runtime evidence. No favorable metric alone proves factory readiness.','',
            '## Reproduction','',
            'Use backend/reflex_bench/improve_v2.py train/freeze/evaluate/detail/robustness/latency with explicit category and split. Sources, model manifests and frozen normal memberships are hash-bound. Final labels never enter the detector. All negative outcomes remain in the CSV/JSON records. No automatic regression or benchmark success is asserted before the corresponding logs complete.']
    lines+=['','## Machine-readable evidence tables','',
            'ALL_RESULTS.csv contains every fixed arm/seed. MACRO_RESULTS.csv uses equal category weights within replay/development/final separately. AGENT_POLICIES.csv reports decision flips, logical call budgets and unresolved reviews. DETAIL_FUSION.csv contains fixed-budget image/pixel controls. ROBUSTNESS.csv, LOCALIZATION_ABLATIONS.csv and NATIVE_LOCALIZATION.csv retain each measured configuration. RUNTIME.csv separates local loopback, dedicated AWS loopback and completed public internet measurements. JSON/per-case logs contain full precision and additional counts.','',
            'Metric correction: historical custom AU-PRO failed reversed-ranking unit examples. Old files stay preserved; baseline AU-PRO in this comparison is recomputed from unchanged saved maps using the separately verified versioned implementation. Do not interpret a metric-implementation change as detector improvement. Publisher-package byte parity remains a separate claim.','',
            'Data attribution: VisA, Amazon Science / Zou et al., ECCV2022, CC BY4.0; https://github.com/amazon-science/spot-diff. This report identifies transformed/model-derived outputs.']
    extra_tables(report,figures,all_rows,sources)
    (report/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (report/'COMPARISONS.json').write_text(json.dumps(comparisons,indent=2))
    (report/'SOURCE_SHA256.json').write_text(json.dumps(sources,indent=2))
    gallery_count=gallery(report,groups)
    print(json.dumps({'reported_metric_rows':len(all_rows),'groups':len(groups),'graphs':len(list(figures.glob('*.svg'))),'gallery_cases':gallery_count,'report':str(report/'REPORT.md')}))


if __name__=='__main__':main()
