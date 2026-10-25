from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
import hashlib
import json

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Part(Strict):
    classes: list[str]
    count: int = Field(ge=1,le=10)

class Slot(Strict):
    requires: str
    rect: tuple[float,float,float,float]

    @model_validator(mode='after')
    def valid_rect(self):
        a,b,c,d=self.rect
        if not (0<=a<c<=1 and 0<=b<d<=1):raise ValueError('Slot rectangle must be ordered normalized coordinates')
        return self

class Step(Strict):
    id: str
    title: str
    requires: list[str]
    slots: list[str]

class Confirmation(Strict):
    minimum_supporting_frames: int = Field(default=3,ge=2,le=10)
    minimum_temporal_gap_ms: int = Field(default=150,ge=100,le=2000)
    maximum_observation_gap_ms: int = Field(default=750,ge=200,le=5000)

class Recipe(Strict):
    recipe_id: str
    name: str
    version: str
    parts: dict[str,Part]
    slots: dict[str,Slot]
    steps: list[Step]
    confirmation: Confirmation = Field(default_factory=Confirmation)
    scope: str

    @model_validator(mode='after')
    def validate_graph(self):
        ids=[s.id for s in self.steps]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate step id')
        for p in self.parts.values():
            if not p.classes:raise ValueError('Missing component classes')
        for slot in self.slots.values():
            if slot.requires not in self.parts:raise ValueError('Unknown slot part')
        graph={s.id:s.requires for s in self.steps}
        def walk(node,visiting,done):
            if node in visiting:raise ValueError('Recipe prerequisite cycle')
            if node in done:return
            visiting.add(node)
            for dep in graph[node]:
                if dep not in graph:raise ValueError('Unknown prerequisite')
                walk(dep,visiting,done)
            visiting.remove(node);done.add(node)
        for s in self.steps:
            if not s.slots or any(k not in self.slots for k in s.slots):raise ValueError('Unknown or empty step slot')
            walk(s.id,set(),set())
        return self

    @property
    def sha256(self):
        return hashlib.sha256(json.dumps(self.model_dump(),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def load_recipe(recipe_id='demo_panel_v1'):
    if recipe_id!='demo_panel_v1':raise ValueError('Unknown recipe')
    return Recipe.model_validate({
        'recipe_id':recipe_id,'name':'Demo Sensor Panel — colored teaching fixture','version':'1.0.0',
        'scope':'Calibrated nonhazardous tabletop panel only. Blue short spacers, green cover, yellow fasteners. No general industrial part recognition or certified safety decision.',
        'parts':{'spacer_short':{'classes':['short_spacer'],'count':2},'cover':{'classes':['cover_plate'],'count':1},'bolt':{'classes':['fastener'],'count':2}},
        'slots':{'spacer_left':{'requires':'spacer_short','rect':[.18,.22,.38,.42]},'spacer_right':{'requires':'spacer_short','rect':[.62,.22,.82,.42]},'cover':{'requires':'cover','rect':[.36,.45,.64,.62]},'left_fastener':{'requires':'bolt','rect':[.18,.67,.38,.87]},'right_fastener':{'requires':'bolt','rect':[.62,.67,.82,.87]}},
        'steps':[{'id':'mount_spacers','title':'Place both blue short spacers','requires':[],'slots':['spacer_left','spacer_right']},{'id':'install_cover','title':'Place the green cover','requires':['mount_spacers'],'slots':['cover']},{'id':'fit_fasteners','title':'Place both yellow fasteners','requires':['install_cover'],'slots':['left_fastener','right_fastener']}],
        'confirmation':{},
    })

def validate_quad(quad):
    import cv2
    import numpy as np
    a=np.asarray(quad,dtype=np.float32)
    if a.shape!=(4,2) or not np.isfinite(a).all() or a.min()<0 or a.max()>1:raise ValueError('Four normalized calibration corners required')
    if not cv2.isContourConvex(a) or cv2.contourArea(a)<.12:raise ValueError('Calibration quad must be convex and cover at least12% of frame')
    # Require clockwise TL,TR,BR,BL in image coordinates, preventing mirrored recipes.
    cross=float(np.cross(a[1]-a[0],a[2]-a[1]))
    if cross<=0:raise ValueError('Use corners in top-left,top-right,bottom-right,bottom-left order')
    return a
