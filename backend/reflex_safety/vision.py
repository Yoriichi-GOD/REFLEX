from __future__ import annotations
import hashlib,time
import cv2
import numpy as np
from .recipe import validate_quad

MODEL_VERSION='reflex-colored-panel-cv5-1.0.0'
CANVAS=(640,480)

def analyze_frame(frame,recipe,quad,frame_index,timestamp_ms):
    started=time.perf_counter()
    if int(cv2.__version__.split('.')[0])!=5:raise RuntimeError('OpenCV5 required')
    if frame.ndim!=3 or frame.shape[2]!=3 or frame.shape[0]*frame.shape[1]>5_000_000:raise ValueError('Unsupported frame geometry')
    q=validate_quad(quad);h,w=frame.shape[:2]
    matrix=cv2.getPerspectiveTransform(q*np.float32([w-1,h-1]),np.float32([[0,0],[639,0],[639,479],[0,479]]))
    board=cv2.warpPerspective(frame,matrix,CANVAS)
    gray=cv2.cvtColor(board,cv2.COLOR_BGR2GRAY)
    hsv=cv2.cvtColor(board,cv2.COLOR_BGR2HSV)
    focus=float(cv2.Laplacian(gray,cv2.CV_32F).var());mean=float(gray.mean())
    global_flags=[]
    if mean<35:global_flags.append('LOW_EXPOSURE')
    if np.mean(gray>249)>.65:global_flags.append('GLARE_OR_OVEREXPOSURE')
    if focus<12:global_flags.append('LOW_FOCUS')
    if np.mean(gray<45)>.4:global_flags.append('OCCLUDED')
    observations=[];overlay=board.copy()
    for slot_id,slot in recipe.slots.items():
        x1,y1,x2,y2=[int(v*scale) for v,scale in zip(slot.rect,[640,480,640,480])]
        # Ignore thin setup outlines; analyze the interior of the calibrated slot.
        rgb=board[y1+4:y2-4,x1+4:x2-4];patch=hsv[y1+4:y2-4,x1+4:x2-4];g=gray[y1+4:y2-4,x1+4:x2-4]
        flags=list(global_flags);dark=float(np.mean(g<75));white=float(np.mean(g>249))
        if dark>.52 or white>.65:flags.append('SLOT_OCCLUDED_OR_GLARE')
        masks={'blue':cv2.inRange(patch,np.array([90,90,45],np.uint8),np.array([135,255,255],np.uint8)),
               'green':cv2.inRange(patch,np.array([38,75,40],np.uint8),np.array([86,255,255],np.uint8)),
               'yellow':cv2.inRange(patch,np.array([17,85,70],np.uint8),np.array([38,255,255],np.uint8)),
               'red':cv2.bitwise_or(cv2.inRange(patch,np.array([0,85,45],np.uint8),np.array([10,255,255],np.uint8)),cv2.inRange(patch,np.array([170,85,45],np.uint8),np.array([179,255,255],np.uint8)))}
        color=max(masks,key=lambda c:cv2.countNonZero(masks[c]));mask=masks[color]
        contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        contour=max(contours,key=cv2.contourArea) if contours else None
        area=float(cv2.contourArea(contour)) if contour is not None else 0
        fraction=area/max(1,g.size);class_id='missing';confidence=.9;bbox=[x1,y1,x2,y2]
        if fraction>.025:
            bx,by,bw,bh=cv2.boundingRect(contour);bbox=[x1+4+bx,y1+4+by,x1+4+bx+bw,y1+4+by+bh]
            aspect=max(bw,bh)/max(1,min(bw,bh))
            class_id={'blue':'long_spacer' if aspect>1.7 else 'short_spacer','green':'cover_plate','yellow':'oversized_fastener' if fraction>.3 else 'fastener','red':'red_component'}[color]
            confidence=min(.99,.6+fraction*2)
        elif np.mean((patch[:,:,1]>80)&(patch[:,:,2]>60))>.03 or dark>.08:
            class_id='unknown';confidence=.25
        if flags:class_id='unobserved';confidence=0.0
        expected=recipe.parts[slot.requires].classes
        status='uncertain' if class_id in ['unknown','unobserved'] else 'missing' if class_id=='missing' else 'matched' if class_id in expected else 'mismatch'
        color_bgr={'uncertain':(0,165,255),'missing':(125,125,125),'matched':(80,200,80),'mismatch':(50,50,240)}[status]
        cv2.rectangle(overlay,(x1,y1),(x2,y2),color_bgr,2)
        cv2.putText(overlay,f'{slot_id}: {class_id}',(x1,max(15,y1-7)),cv2.FONT_HERSHEY_SIMPLEX,.38,color_bgr,1,cv2.LINE_AA)
        observations.append({'slot_id':slot_id,'class_id':class_id,'object_id':None if class_id in ['missing','unobserved','unknown'] else f'{slot_id}:{class_id}',
                             'expected_classes':expected,'bbox_xyxy':bbox,'confidence':round(confidence,4),'confidence_kind':'heuristic color/shape support, not a calibrated probability','image_quality':0.0 if flags else 1.0,'quality_flags':flags,'status':status})
    valid=not global_flags and not any(o['class_id']=='unobserved' for o in observations)
    signature=hashlib.sha256(frame.tobytes()).hexdigest()
    return {'frame_index':frame_index,'source_timestamp_ms':timestamp_ms,'frame_sha256':signature,'model_version':MODEL_VERSION,'cv_version':cv2.__version__,
            'quality':{'usable':valid,'flags':sorted(set(global_flags+[f for o in observations for f in o['quality_flags']])),'focus_variance':focus,'mean_gray':mean},
            'observations':observations,'calibration':{'kind':'manual_planar_quad','quad':q.tolist(),'reprojection_error':None,'note':'Manual calibration; no automatic homography inlier or metric accuracy claim'},
            'cv_functions':['getPerspectiveTransform','warpPerspective','cvtColor','Laplacian','inRange','findContours','boundingRect','rectangle','putText'],
            'processing_ms':(time.perf_counter()-started)*1000},board,overlay
