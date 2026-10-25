"""Versioned normal-only experiments; v1 scientific source stays unchanged.

Every full/region/tile threshold is calibrated in its own operation/scale.
No labels or masks are accepted by this module. Scores are not probabilities.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

import cv2
import numpy as np

from app.core.patch_memory import (PatchMemory, WEIGHTS_SHA256, FEATURE_GRAPH_SHA256,
                                   coreset, digest, nearest_distances, preprocess)
from app.core.model import extract_regions
from app.core.quality import inspect_quality, foreground_bbox

VERSION = "reflex-resnet50-patch-memory-2"


@dataclass(frozen=True)
class PatchConfig:
    dimensions: int = 128
    patches_per_image: int = 96
    max_memory: int = 4096
    seed: int = 20261024
    scoring: str = "region"
    smoothing_sigma: float = 1.0
    pixel_quantile: float = .9975
    pose_augmentation: bool = False

    def __post_init__(self):
        if self.dimensions not in (128, 512) or self.patches_per_image < 1 or self.max_memory < 4:
            raise ValueError("Invalid patch memory dimensions or counts")
        if self.scoring not in ("max", "top4", "region") or self.smoothing_sigma not in (1., 4.):
            raise ValueError("Unsupported predeclared scoring or smoothing")
        if not .99 <= self.pixel_quantile < 1:
            raise ValueError("Invalid normal pixel quantile")


def valid_patch_centers(grid, box, side=256):
    y, x = np.indices(grid)
    bx, by, bw, bh = box
    return (((x + .5) * side / grid[1] >= bx) & ((x + .5) * side / grid[1] < bx + bw)
            & ((y + .5) * side / grid[0] >= by) & ((y + .5) * side / grid[0] < by + bh))


def balanced_indices(grid, valid, count, rng):
    """Spatial4x4 stratification, then fill shortages without replacement."""
    yy, xx = np.indices(grid)
    cell = np.minimum(3, yy * 4 // grid[0]) * 4 + np.minimum(3, xx * 4 // grid[1])
    groups = [np.flatnonzero((cell == k) & valid) for k in range(16)]
    nonempty = [g for g in groups if len(g)]
    target = min(int(count), int(valid.sum()))
    if target < 1:
        raise ValueError("No valid patch centers for this aspect ratio")
    selected = []
    for j in rng.permutation(len(nonempty)):
        group = nonempty[j]
        take = min(len(group), target // len(nonempty))
        selected.extend(rng.choice(group, take, replace=False).tolist())
    remaining = np.setdiff1d(np.flatnonzero(valid), selected)
    if len(selected) < target:
        selected.extend(rng.choice(remaining, target - len(selected), replace=False).tolist())
    return np.array(selected, dtype=np.int32)


def patch_scores(small, valid):
    values = small[valid]
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("No finite valid patch evidence")
    k = min(4, len(values))
    support = cv2.boxFilter(valid.astype(np.float32), -1, (3, 3), normalize=False,
                            borderType=cv2.BORDER_CONSTANT)
    total = cv2.boxFilter(np.where(valid, small, 0).astype(np.float32), -1, (3, 3),
                          normalize=False, borderType=cv2.BORDER_CONSTANT)
    local = total / np.maximum(support, 1)
    return {"max": float(values.max()),
            "top4": float(np.partition(values, -k)[-k:].mean()),
            "region": float(local[valid].max())}


def restore_map(small, box, shape, sigma=1.):
    square = cv2.resize(small, (256, 256), interpolation=cv2.INTER_LINEAR)
    square = cv2.GaussianBlur(square, (0, 0), sigma)
    x, y, w, h = box
    return cv2.resize(square[y:y+h, x:x+w], (shape[1], shape[0]), interpolation=cv2.INTER_LINEAR)


def grid_map(score):
    h, w = score.shape
    ratio = min(1., 256 / max(h, w))
    return cv2.resize(score, (max(1, round(w*ratio)), max(1, round(h*ratio))), interpolation=cv2.INTER_LINEAR)


def tile_boxes(shape):
    h, w = shape[:2]
    tw, th = max(8, round(w * .625)), max(8, round(h * .625))
    tw, th = min(w, tw), min(h, th)
    return [[x, y, x+tw, y+th] for y in (0, h-th) for x in (0, w-tw)]


def choose_tile(score_map, boxes):
    return int(np.argmax([np.mean(score_map[y1:y2, x1:x2]) for x1,y1,x2,y2 in boxes]))


def random_tile(image, seed):
    token = hashlib.sha256(np.ascontiguousarray(image).tobytes()).digest()
    return (int.from_bytes(token[:8], "little") ^ int(seed)) % 4


def _read(path):
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Cannot decode {path}")
    return image


def _thresholds(scores):
    return {key: {str(q): float(np.quantile(values, q, method="higher"))
                  for q in (.8, .85, .9, .95)} for key, values in scores.items()}


class PatchMemoryV2(PatchMemory):
    def __init__(self, weights, config=None):
        super().__init__(Path(weights))
        self.config = config or PatchConfig()
        self.detail_model = None

    def embed(self, image):
        features,grid,box,_=self._embed_measured(image)
        return features,grid,box

    def _embed_measured(self, image):
        """Optional float32 feature cache; never caches decisions or labels."""
        started=time.perf_counter()
        timings={"opencv_preprocess_ms":0.,"feature_extraction_ms":0.,"feature_aggregation_projection_ms":0.}
        cache = os.getenv("REFLEX_V2_FEATURE_CACHE")
        key = hashlib.sha256(FEATURE_GRAPH_SHA256.encode()+np.ascontiguousarray(image).tobytes()
                             +str(image.shape).encode()).hexdigest()
        path = Path(cache)/key[:2]/f"{key}.npz" if cache else None
        if path is not None and path.exists():
            with np.load(path,allow_pickle=False) as data:
                raw, grid, box = data["features"],tuple(data["grid"].tolist()),tuple(data["box"].tolist())
            if raw.dtype!=np.float32 or raw.shape!=(grid[0]*grid[1],1536) or not np.isfinite(raw).all():
                raise RuntimeError("Invalid cached feature artifact")
        else:
            blob,box=preprocess(image)
            timings["opencv_preprocess_ms"]=(time.perf_counter()-started)*1000
            forward_started=time.perf_counter()
            with self.lock:
                self.net.setInput(blob)
                layers=self.net.forward(self.layers)
            timings["feature_extraction_ms"]=(time.perf_counter()-forward_started)*1000
            aggregate_started=time.perf_counter()
            maps=[]
            for feature in layers:
                chw=feature[0]
                padded=np.pad(chw,((0,0),(1,1),(1,1)))
                pooled=sum(padded[:,dy:dy+chw.shape[1],dx:dx+chw.shape[2]] for dy in range(3) for dx in range(3))/9
                maps.append(pooled.transpose(1,2,0))
            h,w=maps[0].shape[:2]
            maps=[maps[0]]+[np.concatenate([cv2.resize(m[:,:,start:start+128],(w,h),interpolation=cv2.INTER_LINEAR)
                                            for start in range(0,m.shape[2],128)],axis=2) for m in maps[1:]]
            raw=np.ascontiguousarray(np.concatenate(maps,axis=2).reshape(h*w,-1),dtype=np.float32)
            grid=(h,w)
            timings["feature_aggregation_projection_ms"]=(time.perf_counter()-aggregate_started)*1000
            if path is not None:
                import shutil
                if shutil.disk_usage(path.parent.parent if path.parent.parent.exists() else Path(cache).parent).free < 12*1024**3:
                    project_start=time.perf_counter()
                    features=np.ascontiguousarray(raw@self.projection if self.projection is not None else raw,dtype=np.float32)
                    timings["feature_aggregation_projection_ms"]+=(time.perf_counter()-project_start)*1000
                    timings.update(feature_cache_hit=False,feature_pipeline_ms=(time.perf_counter()-started)*1000)
                    return features,grid,box,timings
                path.parent.mkdir(parents=True,exist_ok=True)
                temporary=path.with_name(f"{key}.{uuid.uuid4().hex}.npz")
                np.savez(temporary,features=raw,grid=np.array(grid),box=np.array(box))
                os.replace(temporary,path)
        project_start=time.perf_counter()
        features=raw@self.projection if self.projection is not None else raw
        timings["feature_aggregation_projection_ms"]+=(time.perf_counter()-project_start)*1000
        timings.update(feature_cache_hit=path is not None and timings["feature_extraction_ms"]==0,
                       feature_pipeline_ms=(time.perf_counter()-started)*1000)
        return np.ascontiguousarray(features,dtype=np.float32),grid,box,timings

    def _initialize_projection(self, raw_dimensions=1536):
        rng = np.random.default_rng(self.config.seed)
        draw = rng.choice([-1., 0., 1.], (raw_dimensions, self.config.dimensions), p=[1/6, 2/3, 1/6])
        self.projection = (draw * np.sqrt(3/self.config.dimensions)).astype(np.float32)

    def distances(self, image):
        features, grid, box, timings = self._embed_measured(image)
        started=time.perf_counter()
        valid = valid_patch_centers(grid, box)
        small = nearest_distances(features, self.memory).reshape(grid)
        timings["patch_distance_ms"]=(time.perf_counter()-started)*1000
        return small, valid, box, timings

    def predict(self, image, *, scoring=None, sigma=None):
        if self.memory is None:
            raise RuntimeError("Patch memory is not fitted")
        small, valid, box, timings = self.distances(image)
        started=time.perf_counter()
        scores = patch_scores(small, valid)
        method = scoring or self.config.scoring
        if method not in scores:
            raise ValueError("Unknown scoring method")
        restored=restore_map(small,box,image.shape[:2],sigma or self.config.smoothing_sigma)
        timings["score_map_reconstruction_ms"]=(time.perf_counter()-started)*1000
        return {"score": scores[method], "all_scores": scores,"stage_timings":timings,
                "score_map": restored,
                "raw_patch_map": small, "valid_patch_centers": valid, "letterbox": box}

    def _fit_memory(self, paths, *, tiles=False):
        self._initialize_projection()
        rng = np.random.default_rng(self.config.seed + 1)
        pool = []
        for index, path in enumerate(paths):
            image = _read(path)
            samples = [image]
            if self.config.pose_augmentation:
                h, w = image.shape[:2]
                samples.append(cv2.warpAffine(image, cv2.getRotationMatrix2D((w/2,h/2),7,1),
                                               (w,h), borderMode=cv2.BORDER_REFLECT_101))
            if tiles:
                samples = [image[y1:y2,x1:x2] for x1,y1,x2,y2 in tile_boxes(image.shape)]
            for sample in samples:
                features, grid, box = self.embed(sample)
                valid = valid_patch_centers(grid, box)
                ids = balanced_indices(grid, valid, self.config.patches_per_image, rng)
                pool.append(features[ids])
            if (index+1) % 100 == 0:
                print(json.dumps({"phase":"fit_tiles" if tiles else "fit", "done":index+1,"n":len(paths),
                                  "dimensions":self.config.dimensions,"seed":self.config.seed}), flush=True)
        pool = np.concatenate(pool)
        started = time.perf_counter()
        self.memory = coreset(pool, min(self.config.max_memory, len(pool)), np.random.default_rng(self.config.seed+2))
        return len(pool), time.perf_counter()-started

    def _check_membership(self, paths, calibration):
        if len(paths) < 4 or len(calibration) < 4:
            raise ValueError("Need disjoint fit and calibration normals")
        fit_h, cal_h = [digest(Path(p)) for p in paths], [digest(Path(p)) for p in calibration]
        if len(set(fit_h)) != len(fit_h) or len(set(cal_h)) != len(cal_h) or set(fit_h) & set(cal_h):
            raise ValueError("Fit/calibration must be unique and disjoint")
        return fit_h, cal_h

    def fit(self, paths, calibration, output, category, **unused):
        started = time.perf_counter()
        fit_h, cal_h = self._check_membership(paths, calibration)
        count, seconds = self._fit_memory(paths)
        scores = {k: [] for k in ("max", "top4", "region")}
        pixels = {str(sigma): [] for sigma in (1., 4.)}
        for path in calibration:
            image = _read(path)
            small, valid, box, _ = self.distances(image)
            values = patch_scores(small, valid)
            for key in scores:
                scores[key].append(values[key])
            for sigma in (1., 4.):
                pixels[str(sigma)].append(grid_map(restore_map(small, box, image.shape[:2], sigma)).ravel())
        thresholds = _thresholds(scores)
        pixel_thresholds = {sigma: {str(q):float(np.quantile(np.concatenate(values),q,method="higher"))
                                    for q in (.995,.9975,.999)} for sigma,values in pixels.items()}
        self.metadata = {"model_version":VERSION,"model_mode":"opencv_dnn_patch_memory","category":category,
                         "data_source":f"VisA:{category}","synthetic":False,"config":asdict(self.config),
                         "side":256,"layers":self.layers,"weights_sha256":WEIGHTS_SHA256,
                         "feature_graph_sha256":FEATURE_GRAPH_SHA256,"weights_license":"Apache-2.0",
                         "training_count":len(paths),"calibration_count":len(calibration),
                         "training_sha256":fit_h,"calibration_sha256":cal_h,
                         "sampled_patch_count":count,"memory_patch_count":len(self.memory),
                         "calibration_scores":scores,"score_thresholds":thresholds,
                         "pixel_thresholds":pixel_thresholds,"image_threshold":thresholds[self.config.scoring]["0.95"],
                         "pass_threshold":thresholds[self.config.scoring]["0.9"],"pass_quantile":.9,
                         "pixel_threshold":pixel_thresholds[str(self.config.smoothing_sigma)][str(self.config.pixel_quantile)],
                         "calibration_image_scores":scores[self.config.scoring],
                         "calibration_method":"Normal-only95thpercentile(higher), operation-specific patch score; lower PASS bound normal-development budget",
                         "pixel_threshold_method":"Normal-only pixel quantile(higher), scale/smoothing-specific; evaluation max-side256",
                         "coreset_seconds":seconds,"fit_and_calibration_seconds":time.perf_counter()-started,
                         "scale":"full","review_budget_on_development_normals":.10}
        self.save(output)
        return self.metadata

    def set_operation(self, scoring, *, sigma=1., pixel_quantile=.9975):
        cfg = asdict(self.config)
        cfg.update(scoring=scoring,smoothing_sigma=sigma,pixel_quantile=pixel_quantile)
        self.config = PatchConfig(**cfg)
        self.metadata = {**self.metadata,"config":asdict(self.config),
                         "image_threshold":self.metadata["score_thresholds"][scoring]["0.95"],
                         "pass_threshold":self.metadata["score_thresholds"][scoring]["0.9"],
                         "pixel_threshold":self.metadata["pixel_thresholds"][str(sigma)][str(pixel_quantile)],
                         "calibration_image_scores":self.metadata["calibration_scores"][scoring]}

    def calibrate_review(self, development_paths):
        hashes=[digest(Path(p)) for p in development_paths]
        if not hashes or len(set(hashes))!=len(hashes) or set(hashes)&set(self.metadata["training_sha256"]+self.metadata["calibration_sha256"]):
            raise ValueError("Development must be unique and disjoint from fit/calibration")
        rows = []
        for path in development_paths:
            image = _read(path)
            h,w=image.shape[:2]
            rotated=cv2.warpAffine(image,cv2.getRotationMatrix2D((w/2,h/2),7,1),(w,h),borderMode=cv2.BORDER_REFLECT_101)
            rows.append((self.predict(image)["all_scores"],self.predict(rotated)["all_scores"]))
        method=self.config.scoring
        upper=self.metadata["score_thresholds"][method]["0.95"]
        trials=[]
        for q in (.8,.85,.9,.95):
            lower=self.metadata["score_thresholds"][method][str(q)]
            rates=[sum(lower<r[v][method]<=upper for r in rows)/len(rows) for v in (0,1)]
            trials.append({"quantile":q,"threshold":lower,"review_rates_canonical_rotated":rates})
        picked=next(t for t in trials if max(t["review_rates_canonical_rotated"])<=.10+1e-12)
        self.metadata.update(pass_threshold=picked["threshold"],pass_quantile=picked["quantile"],
                             development_sha256=hashes,
                             review_development={"normal_count":len(rows),"selection":"lowest quantile with<=10% extra review in both normal capture variants","trials":trials})
        return rows

    def analyze(self, image):
        result=self.predict(image)
        quality_start=time.perf_counter()
        meta=self.metadata
        quality=inspect_quality(image)
        if meta.get("suitability"):
            from app.core.suitability_v2 import inspect_suitability
            suitability=inspect_suitability(image,meta["suitability"])
            quality={**quality,"suitability":suitability,"flags":list(dict.fromkeys(quality["flags"]+suitability.get("routing_flags",[])))}
        small=grid_map(result["score_map"])
        regions=extract_regions(small,meta["pixel_threshold"],(image.shape[1],image.shape[0]))
        result["stage_timings"]["quality_and_regions_ms"]=(time.perf_counter()-quality_start)*1000
        second=None
        if not quality["flags"] and meta["pass_threshold"]<result["score"]<=meta["image_threshold"] and self.detail_model is not None:
            boxes=tile_boxes(image.shape)
            index=choose_tile(result["score_map"],boxes)
            x1,y1,x2,y2=boxes[index]
            start=time.perf_counter()
            try:
                changed=self.detail_model.predict(image[y1:y2,x1:x2])
                error=None
            except (RuntimeError,ValueError,cv2.error):
                changed={"score":None}
                error="DETAIL_INFERENCE_FAILED"
            second={"source_bbox_xyxy":boxes[index],"tile_index":index,"crop_width_native_pixels":x2-x1,
                    "crop_height_native_pixels":y2-y1,"upscaled":max(x2-x1,y2-y1)<256,
                    "model_input_side":256,"additional_camera_view":False,
                    "crop_anomaly_score":changed["score"],
                    "calibrated_image_threshold":self.detail_model.metadata["detail_thresholds"]["chosen"],
                    "crop_score_exceeds_threshold":changed["score"] is not None and changed["score"]>self.detail_model.metadata["detail_thresholds"]["chosen"],
                    "tool_error":error,
                    "normal_bank_sha256":self.detail_model.metadata["normal_bank_sha256"],
                    "evidence_id":hashlib.sha256(image[y1:y2,x1:x2].tobytes()).hexdigest()[:16],
                    "elapsed_ms":(time.perf_counter()-start)*1000}
        return {**result,"small_score_map":small,"threshold":meta["image_threshold"],
                "pass_threshold":meta["pass_threshold"],"pixel_threshold":meta["pixel_threshold"],
                "score_margin":(result["score"]-meta["image_threshold"])/max(float(np.std(meta["calibration_image_scores"])),1e-6),
                "quality":quality,"foreground_bbox_xyxy":foreground_bbox(image),"regions":regions,
                "model_version":VERSION,"model_mode":"opencv_dnn_patch_memory","category":meta["category"],
                "normal_bank_sha256":meta["normal_bank_sha256"],"second_look":second}

    def save(self, output):
        output=Path(output)
        output.mkdir(parents=True,exist_ok=True)
        bank=output/"patch_bank.npz"
        np.savez_compressed(bank,projection=self.projection,memory=self.memory)
        self.metadata["normal_bank_sha256"]=digest(bank)
        (output/"metadata.json").write_text(json.dumps(self.metadata,indent=2),encoding="utf-8")

    @classmethod
    def load(cls,directory,weights):
        directory=Path(directory)
        meta=json.loads((directory/"metadata.json").read_text(encoding="utf-8"))
        if meta.get("model_version")!=VERSION or meta.get("weights_sha256")!=WEIGHTS_SHA256 or meta.get("feature_graph_sha256")!=FEATURE_GRAPH_SHA256:
            raise RuntimeError("Unsupported v2 manifest")
        if digest(directory/"patch_bank.npz")!=meta["normal_bank_sha256"]:
            raise RuntimeError("Patch memory SHA256 mismatch")
        model=cls(weights,PatchConfig(**meta["config"]))
        with np.load(directory/"patch_bank.npz",allow_pickle=False) as arrays:
            model.projection,model.memory=arrays["projection"],arrays["memory"]
        if model.projection.shape!=(1536,model.config.dimensions) or model.memory.ndim!=2 or model.memory.shape[1]!=model.config.dimensions or len(model.memory)<1:
            raise RuntimeError("Invalid v2 feature dimensions")
        if not np.isfinite(model.projection).all() or not np.isfinite(model.memory).all():
            raise RuntimeError("Nonfinite patch bank")
        if not all(np.isfinite(meta[k]) for k in ("image_threshold","pass_threshold","pixel_threshold")) or meta["pass_threshold"]>meta["image_threshold"]:
            raise RuntimeError("Invalid calibrated thresholds")
        model.metadata=meta
        if meta.get("detail_directory"):
            detail=(directory/meta["detail_directory"]).resolve()
            if not detail.is_relative_to(directory.resolve()):
                raise RuntimeError("Detail profile must remain inside parent directory")
            model.detail_model=cls.load(detail,weights)
        return model


def fit_detail(paths,calibration,full_model,output):
    model=PatchMemoryV2(full_model.weights,PatchConfig(patches_per_image=24,scoring="region"))
    fit_h,cal_h=model._check_membership(paths,calibration)
    started=time.perf_counter()
    count,coreset_seconds=model._fit_memory(paths,tiles=True)
    scores={k:[] for k in ("chosen","random","all4")}
    pixels=[]
    for path in calibration:
        image=_read(path)
        initial=full_model.predict(image)
        boxes=tile_boxes(image.shape)
        results=[model.predict(image[y1:y2,x1:x2]) for x1,y1,x2,y2 in boxes]
        values=[r["score"] for r in results]
        scores["chosen"].append(values[choose_tile(initial["score_map"],boxes)])
        scores["random"].append(values[random_tile(image,model.config.seed)])
        scores["all4"].append(max(values))
        pixels.extend(grid_map(r["score_map"]).ravel() for r in results)
    pixel=float(np.quantile(np.concatenate(pixels),.9975,method="higher"))
    chosen=float(np.quantile(scores["chosen"],.95,method="higher"))
    model.metadata={**full_model.metadata,"config":asdict(model.config),"scale":"detail62.5pct",
                    "training_sha256":fit_h,"calibration_sha256":cal_h,"sampled_patch_count":count,
                    "memory_patch_count":len(model.memory),"detail_calibration_scores":scores,
                    "detail_thresholds":{k:float(np.quantile(v,.95,method="higher")) for k,v in scores.items()},
                    "calibration_image_scores":scores["chosen"],"image_threshold":chosen,"pass_threshold":chosen,
                    "pixel_threshold":pixel,"coreset_seconds":coreset_seconds,
                    "fit_and_calibration_seconds":time.perf_counter()-started,
                    "calibration_method":"Scale-specific normal95thpercentile(higher), chosen/random/all4 calibrated separately",
                    "detail_source_full_config":asdict(full_model.config)}
    model.metadata.pop("detail_directory",None)
    model.metadata.pop("suitability",None)
    model.save(output)
    return model
