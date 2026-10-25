from __future__ import annotations
from collections import deque
import hashlib,random,time,uuid
from pathlib import Path
import cv2
from .vision import analyze_frame,MODEL_VERSION

POLICIES=('single','random','agent')
DEFAULT_QUAD=[[0,0],[1,0],[1,1],[0,1]]

class RecipeEngine:
    """Deterministic observation-sourced state; labels/clip names never enter it."""
    def __init__(self,recipe,start_state='unknown'):
        self.recipe=recipe;self.start_state=start_state
        self.windows={s:deque(maxlen=recipe.confirmation.minimum_supporting_frames) for s in recipe.slots}
        self.slots={s:{'slot_id':s,'expected_classes':recipe.parts[v.requires].classes,'observed_class':'unobserved','state':'UNOBSERVED','supporting_observation_ids':[]} for s,v in recipe.slots.items()}
        self.steps={s.id:{'step_id':s.id,'title':s.title,'state':'PENDING','requires':s.requires,'slot_ids':s.slots} for s in recipe.steps}
        self.events=[];self.observations=[];self.agent_trace=[];self.seen=set();self.last_time=None
        self.empty_verified=False;self.history_gap=start_state not in ['empty_observed','empty_confirmed'];self.quality_usable=False;self.quality_flags=[]
        self.active_order=set();self.previous_classes={};self.last_frame=None;self.cancelled=False;self.truncated=False

    def event(self,kind,reason,t,ids,step=None):
        event={'event_id':uuid.uuid4().hex,'procedure_id':self.recipe.recipe_id,'step_id':step,'source_timestamp_ms':t,'observed_at_ms':t,'state':kind,'reason_code':reason,'evidence_ids':list(ids)}
        self.events.append(event);return event

    def feed(self,record):
        t=record['source_timestamp_ms'];sig=record['frame_sha256']
        if self.last_time is not None and t<self.last_time:raise ValueError('Source timestamps must be monotonic')
        if sig in self.seen:
            self.quality_usable=False;self.quality_flags=['REPEATED_FRAME'];return False
        self.seen.add(sig)
        if self.last_time is not None and t-self.last_time>self.recipe.confirmation.maximum_observation_gap_ms:self.history_gap=True
        self.last_time=t;self.last_frame=record
        self.quality_usable=record['quality']['usable'];self.quality_flags=record['quality']['flags']
        if not self.quality_usable:
            self.history_gap=True
            for window in self.windows.values():window.clear()
            return True
        for i,obs in enumerate(record['observations']):
            oid=f"{record['evidence_id']}:{i}"
            value={**obs,'observation_id':oid,'evidence_id':record['evidence_id'],'frame_index':record['frame_index'],'source_timestamp_ms':t,'source_id':record.get('source_id','input'),'model_version':MODEL_VERSION,'cv_version':cv2.__version__,'is_new_capture':True,'capture_kind':record.get('capture_kind','decoded_replay_frame')}
            self.observations.append(value)
            slot=obs['slot_id'];window=self.windows[slot];cls=obs['class_id']
            if window and window[-1][0]!=cls:window.clear()
            if cls in ['unknown','unobserved']:
                window.clear();self.slots[slot].update(observed_class=cls,state='UNCERTAIN',confidence=obs['confidence'],supporting_observation_ids=[oid]);continue
            if not window or t-window[-1][1]>=self.recipe.confirmation.minimum_temporal_gap_ms:window.append((cls,t,oid))
            stable=len(window)==self.recipe.confirmation.minimum_supporting_frames
            old=self.slots[slot]['observed_class'];was=self.slots[slot]['state']
            self.slots[slot].update(observed_class=cls,state='CONFIRMED' if stable else 'OBSERVED_CANDIDATE',confidence=obs['confidence'],supporting_observation_ids=[x[2] for x in window])
            if stable and (old!=cls or was!='CONFIRMED'):
                self.event('CONFIRMED','STABLE_SLOT_OBSERVATION',t,[x[2] for x in window])
                previous=self.previous_classes.get(slot);expected=self.slots[slot]['expected_classes']
                if cls not in ['missing']+expected:
                    reason='WRONG_PLACEMENT' if cls in ['short_spacer','cover_plate','fastener'] else 'WRONG_COMPONENT_CLASS'
                    self.event('VIOLATION',reason,t,[x[2] for x in window])
                elif previous and previous not in ['missing']+expected:self.event('CORRECTED','COMPONENT_CORRECTED',t,[x[2] for x in window])
                self.previous_classes[slot]=cls
        if not self.empty_verified and not self.history_gap and all(s['state']=='CONFIRMED' and s['observed_class']=='missing' for s in self.slots.values()):
            self.empty_verified=True;self.event('CONFIRMED','EMPTY_START_OBSERVED',t,self.evidence_ids())
        for step in self.recipe.steps:
            ready=all(self.slots[k]['state']=='CONFIRMED' and self.slots[k]['observed_class'] in self.slots[k]['expected_classes'] for k in step.slots)
            old=self.steps[step.id]['state'];prereq=all(self.steps[k]['state']=='CONFIRMED' for k in step.requires)
            if not ready:
                self.steps[step.id]['state']='PENDING'
                if step.id in self.active_order:self.active_order.remove(step.id);self.event('CORRECTED','LATER_COMPONENT_REMOVED',t,self.evidence_ids(),step.id)
            elif not prereq:
                # Only assert an order error when missing prerequisites were actually visible.
                required_slots=[k for s in self.recipe.steps if s.id in step.requires for k in s.slots]
                missing=all(self.slots[k]['state']=='CONFIRMED' for k in required_slots) and any(self.slots[k]['observed_class']=='missing' for k in required_slots)
                proven=self.empty_verified and not self.history_gap and missing
                self.steps[step.id]['state']='VIOLATION' if proven else 'NEEDS_REVIEW'
                if proven and step.id not in self.active_order:
                    self.active_order.add(step.id);self.event('VIOLATION','ORDER_VIOLATION',t,self.evidence_ids(),step.id)
            elif step.id in self.active_order:self.steps[step.id]['state']='NEEDS_REVIEW'
            else:self.steps[step.id]['state']='CONFIRMED'
            if self.steps[step.id]['state']=='CONFIRMED' and old!='CONFIRMED':self.event('CONFIRMED','STEP_CONFIRMED',t,self.evidence_ids(),step.id)
        return True

    def evidence_ids(self):
        return list(dict.fromkeys(oid for s in self.slots.values() for oid in s['supporting_observation_ids']))

    def snapshot(self,final_checkpoint=False):
        reasons=[]
        if not self.quality_usable:reasons.extend(self.quality_flags or ['NO_USABLE_OBSERVATION'])
        if self.cancelled:reasons.append('CANCELLED')
        if self.truncated:reasons.append('FRAME_OR_TIME_BUDGET_EXHAUSTED')
        stable=all(s['state']=='CONFIRMED' for s in self.slots.values())
        wrong=[]
        for slot,s in self.slots.items():
            if s['state']=='CONFIRMED' and s['observed_class'] not in ['missing']+s['expected_classes']:
                wrong.append('WRONG_PLACEMENT' if s['observed_class'] in ['short_spacer','cover_plate','fastener'] else 'WRONG_COMPONENT_CLASS')
        reasons.extend(wrong)
        if self.active_order:reasons.append('ORDER_VIOLATION')
        if final_checkpoint and stable and self.quality_usable and any(s['observed_class']=='missing' for s in self.slots.values()):reasons.append('MISSING_COMPONENT')
        if not stable:reasons.append('UNCONFIRMED_OR_OCCLUDED')
        if self.history_gap or not self.empty_verified:reasons.append('PARTIAL_OBSERVATION')
        all_done=all(s['state']=='CONFIRMED' for s in self.steps.values())
        clear_fault=any(r in reasons for r in ['WRONG_COMPONENT_CLASS','WRONG_PLACEMENT','ORDER_VIOLATION','MISSING_COMPONENT'])
        status='HOLD_FOR_REVIEW'
        if self.quality_usable and stable and not self.truncated and not self.cancelled and clear_fault:status='REJECT_RECOMMENDATION'
        elif all_done and not reasons:status='PASS'
        reasons=list(dict.fromkeys(reasons or ([] if status=='PASS' else ['ASSEMBLY_IN_PROGRESS'])))
        return {'decision':{'status':status,'reason_codes':reasons,'supporting_observation_ids':self.evidence_ids(),'required_human_action':None if status=='PASS' else 'Review the supporting frames; correct the fixture or provide a fresh unobstructed view. This is an advisory teaching-fixture gate.','time_to_alert_ms':None},
                'recipe_state':{'recipe_id':self.recipe.recipe_id,'recipe_sha256':self.recipe.sha256,'steps':list(self.steps.values()),'slots':list(self.slots.values()),'empty_start_verified':self.empty_verified,'partial_observation':self.history_gap or not self.empty_verified,'current_step':next((s['step_id'] for s in self.steps.values() if s['state']!='CONFIRMED'),None)},
                'events':list(self.events),'observations':list(self.observations),'agent_trace':list(self.agent_trace)}

def analyze_video(path,recipe,policy='agent',calibration_quad=None,start_state='unknown',final_checkpoint=True,on_frame=None,cancel=None):
    if policy not in POLICIES:raise ValueError('Unknown policy')
    path=Path(path);started=time.perf_counter();engine=RecipeEngine(recipe,start_state)
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened():raise ValueError('Video cannot be decoded')
    fps=float(cap.get(cv2.CAP_PROP_FPS));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not (0<fps<=240) or width*height>5_000_000 or width>2560 or height>2560:
        cap.release();raise ValueError('Unsupported or unknown video dimensions/frame rate')
    if count/fps>120:
        cap.release();raise ValueError('Video exceeds120second limit')
    stride=max(1,round(fps*.3));rng=random.Random(26261);extra_budget=2
    candidates=[i for i in range(min(count,600)) if i%stride]
    random_extra=set(rng.sample(candidates,min(extra_budget,len(candidates)))) if policy=='random' else set()
    pending=False;extra=0;decoded=0;analyzed=0;durations=[];evidence=[];used_times=[]
    try:
        for idx in range(600):
            if cancel and cancel():engine.cancelled=True;break
            if time.perf_counter()-started>90:engine.truncated=True;break
            ok,frame=cap.read()
            if not ok:break
            decoded+=1
            pos=float(cap.get(cv2.CAP_PROP_POS_MSEC));fallback=idx*1000/fps
            ts=pos if pos>=0 and (not used_times or pos>used_times[-1]) else fallback
            selected=idx%stride==0
            extra_selected=not selected and (idx in random_extra or (policy=='agent' and pending and extra<extra_budget))
            if not (selected or extra_selected):continue
            if extra_selected:extra+=1;pending=False
            record,board,overlay=analyze_frame(frame,recipe,calibration_quad or DEFAULT_QUAD,idx,round(ts,3))
            record['evidence_id']=f"frame-{idx:05d}-{record['frame_sha256'][:12]}";record['source_id']='input';record['capture_kind']='decoded_replay_frame'
            accepted=engine.feed(record);analyzed+=1;used_times.append(ts);durations.append(record['processing_ms'])
            entry={'id':record['evidence_id'],'frame_index':idx,'source_timestamp_ms':record['source_timestamp_ms'],'frame_sha256':record['frame_sha256'],'quality':record['quality'],'cv_functions':record['cv_functions'],'processing_ms':record['processing_ms']}
            if on_frame:entry.update(on_frame(record,board,overlay) or {})
            evidence.append(entry)
            if extra_selected:engine.agent_trace.append({'action':'OBSERVE_NEXT_FRAMES','reason':'Seeded random extra frame' if policy=='random' else 'Uncertain or newly changed slot; seek a temporally distinct supporting frame','executed':True,'source_frame_index':idx,'source_timestamp_ms':ts,'evidence_id':record['evidence_id'],'is_new_capture':True,'capture_kind':'existing_replay_frame_not_new_camera_view','cost_ms':record['processing_ms'],'budget_remaining':extra_budget-extra,'observation_accepted':accepted})
            if policy=='agent' and extra<extra_budget and (not record['quality']['usable'] or any(s['state']!='CONFIRMED' for s in engine.slots.values())):pending=True
        if decoded>=600 and count>decoded:engine.truncated=True
    finally:cap.release()
    result=engine.snapshot(final_checkpoint and not engine.cancelled and not engine.truncated)
    if 'MISSING_COMPONENT' in result['decision']['reason_codes']:
        engine.event('VIOLATION','MISSING_COMPONENT',engine.last_time or 0,engine.evidence_ids())
        result['events']=list(engine.events)
    if extra==0 and policy=='agent':result['agent_trace'].append({'action':'STOP_AND_REPORT','executed':True,'reason':'No additional supported inspection required or available','budget_remaining':2})
    result.update(evidence=evidence,policy=policy,source_mode='STREAM_REPLAY',model_version=MODEL_VERSION,cv_version=cv2.__version__,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),recipe_sha256=recipe.sha256,
                  processing={'elapsed_ms':(time.perf_counter()-started)*1000,'decoded_frames':decoded,'analyzed_frames':analyzed,'extra_inspections':extra,'extra_frame_budget':2,'base_stride_frames':stride,'fps_declared':fps,'decoded_fps':decoded/max(.001,time.perf_counter()-started),'timestamp_basis':'OpenCV POS_MSEC when monotonic, otherwise frame_index/declared_fps; not verified live capture timing','source_duration_ms':count*1000/fps,'frame_processing_ms':durations,'truncated':engine.truncated,'cancelled':engine.cancelled,'live_capture_to_alert_ms':None},
                  benchmark_scope='Not a real-world procedure benchmark. Upload provenance and evaluator labels must be supplied separately.')
    return result
