"""OpenCV 5 DNN nearest-normal patches. Adaptation, not official PatchCore.

No test labels/masks are accepted by fitting or prediction. A full image is
letterboxed rather than center-cropped, keeping border defects observable.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading

import cv2
import numpy as np

from app.core.model import extract_regions
from app.core.quality import inspect_quality, foreground_bbox

VERSION = "reflex-resnet50-patch-memory-1"
WEIGHTS_SHA256 = "3f03fdef724b22947eed826f1eef1dc5c34151bb4c37d634f1db89dfa2dd1526"
FEATURE_GRAPH_SHA256 = "13f53653570d3ad98231c463d4ee4ec202306ba3614166f52f10d31e472cb5e6"
FEATURE_LAYERS = ["resnetv17_stage2_activation3", "resnetv17_stage3_activation5"]
WEIGHTS_URL = "https://media.githubusercontent.com/media/onnx/models/main/validated/vision/classification/resnet/model/resnet50-v1-12.onnx"
SEED = 20261023


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def preprocess(image: np.ndarray, side: int = 256) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise ValueError("Expected a decoded uint8 BGR image")
    h, w = image.shape[:2]
    if min(h, w) < 1:
        raise ValueError("Empty image")
    ratio = side / max(h, w)
    nw, nh = max(1, round(w * ratio)), max(1, round(h * ratio))
    x, y = (side - nw) // 2, (side - nh) // 2
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_AREA if ratio < 1 else cv2.INTER_LINEAR)
    padded = cv2.copyMakeBorder(resized, y, side - nh - y, x, side - nw - x, cv2.BORDER_REPLICATE)
    rgb = padded[:, :, ::-1].astype(np.float32) / 255
    rgb = (rgb - np.array([.485, .456, .406], np.float32)) / np.array([.229, .224, .225], np.float32)
    return np.ascontiguousarray(rgb.transpose(2, 0, 1)[None]), (x, y, nw, nh)


def unletterbox(score: np.ndarray, box: tuple[int, int, int, int], shape: tuple[int, int], side: int = 256) -> np.ndarray:
    square = cv2.resize(score, (side, side), interpolation=cv2.INTER_LINEAR)
    square = cv2.GaussianBlur(square, (0, 0), 4)
    x, y, w, h = box
    return cv2.resize(square[y:y+h, x:x+w], (shape[1], shape[0]), interpolation=cv2.INTER_LINEAR)


def nearest_distances(query: np.ndarray, memory: np.ndarray) -> np.ndarray:
    if query.ndim != 2 or memory.ndim != 2 or query.shape[1] != memory.shape[1] or not len(memory):
        raise ValueError("Nonempty memory and queries must have equal feature dimensions")
    distances, _ = cv2.batchDistance(np.ascontiguousarray(query, dtype=np.float32),
                                    np.ascontiguousarray(memory, dtype=np.float32), cv2.CV_32F,
                                    normType=cv2.NORM_L2, K=1)
    return distances[:, 0]


def coreset(features: np.ndarray, count: int, rng: np.random.Generator) -> np.ndarray:
    """Greedy farthest-point sampling in a seeded 16D projection of the pool."""
    if len(features) <= count:
        return features.copy()
    projection = rng.normal(0, 1 / 4, (features.shape[1], 16)).astype(np.float32)
    reduced = features @ projection
    nearest = np.full(len(features), np.inf, np.float32)
    selected = np.empty(count, np.int32)
    current = int(rng.integers(len(features)))
    for index in range(count):
        selected[index] = current
        delta = reduced - reduced[current]
        np.minimum(nearest, np.einsum("ij,ij->i", delta, delta), out=nearest)
        nearest[selected[:index+1]] = -1
        current = int(np.argmax(nearest))
    return features[selected].copy()


class PatchMemory:
    def __init__(self, weights: Path, *, side: int = 256):
        if digest(weights) != WEIGHTS_SHA256:
            raise RuntimeError("Pretrained ResNet weight SHA256 mismatch")
        self.weights = weights
        self.side = side
        feature_graph = weights.with_suffix(".features.onnx")
        if digest(feature_graph) != FEATURE_GRAPH_SHA256:
            raise RuntimeError("Verified pretrained feature graph is missing or altered")
        if side != 256:
            raise ValueError("The verified feature graph requires side=256")
        self.net = cv2.dnn.readNetFromONNX(str(feature_graph))
        self.lock = threading.Lock()
        self.layers = FEATURE_LAYERS.copy()
        self.projection: np.ndarray | None = None
        self.memory: np.ndarray | None = None
        self.metadata: dict = {}

    def embed(self, image: np.ndarray) -> tuple[np.ndarray, tuple[int, int], tuple[int, int, int, int]]:
        blob, box = preprocess(image, self.side)
        with self.lock:
            self.net.setInput(blob)
            layers = self.net.forward(self.layers)
        maps = []
        for feature in layers:
            chw = feature[0]
            padded = np.pad(chw, ((0,0),(1,1),(1,1)))
            pooled = sum(padded[:,dy:dy+chw.shape[1],dx:dx+chw.shape[2]] for dy in range(3) for dx in range(3)) / 9
            maps.append(pooled.transpose(1, 2, 0))
        h, w = maps[0].shape[:2]
        maps = [maps[0]] + [np.concatenate([cv2.resize(m[:,:,start:start+128], (w,h), interpolation=cv2.INTER_LINEAR)
                                           for start in range(0,m.shape[2],128)],axis=2) for m in maps[1:]]
        features = np.concatenate(maps, axis=2).reshape(h*w, -1)
        if self.projection is not None:
            features = features @ self.projection
        return np.ascontiguousarray(features, dtype=np.float32), (h, w), box

    def predict(self, image: np.ndarray) -> dict:
        if self.memory is None:
            raise RuntimeError("Patch memory is not fitted")
        features, grid, box = self.embed(image)
        small = nearest_distances(features, self.memory).reshape(grid)
        # Exclude pure padding patch centers from the image max score.
        x, y, bw, bh = box
        yy, xx = np.indices(grid)
        valid = ((xx + .5) * self.side / grid[1] >= x) & ((xx + .5) * self.side / grid[1] < x+bw)
        valid &= ((yy + .5) * self.side / grid[0] >= y) & ((yy + .5) * self.side / grid[0] < y+bh)
        full = unletterbox(small, box, image.shape[:2], self.side)
        return {"score": float(np.max(small[valid])), "score_map": full}

    def analyze(self, image: np.ndarray) -> dict:
        result = self.predict(image)
        meta = self.metadata
        # Small map follows source coordinates, with padding removed.
        small = cv2.resize(result["score_map"], (120, 90), interpolation=cv2.INTER_AREA)
        threshold = float(meta["image_threshold"])
        return {**result, "small_score_map": small, "threshold": threshold,
                "pixel_threshold": float(meta["pixel_threshold"]),
                "score_margin": (result["score"]-threshold) / max(float(np.std(meta["calibration_image_scores"])), 1e-6),
                "quality": inspect_quality(image), "foreground_bbox_xyxy": foreground_bbox(image),
                "regions": extract_regions(small, meta["pixel_threshold"], (image.shape[1], image.shape[0])),
                "model_version": VERSION, "model_mode": "opencv_dnn_patch_memory",
                "normal_bank_sha256": meta["normal_bank_sha256"], "category": meta["category"]}

    def fit(self, paths: list[Path], calibration: list[Path], output: Path, category: str,
            *, max_memory: int = 4096, patches_per_image: int = 24) -> dict:
        if len(paths) < 4 or len(calibration) < 4:
            raise ValueError("Need at least four fit and calibration normals")
        fit_hashes, cal_hashes = [digest(p) for p in paths], [digest(p) for p in calibration]
        if set(fit_hashes) & set(cal_hashes):
            raise ValueError("Fit and calibration must be disjoint")
        rng = np.random.default_rng(SEED)
        samples = []
        for i, path in enumerate(paths):
            features, _, _ = self.embed(_read(path))
            if self.projection is None:
                # Achlioptas sparse projection: train-independent, deterministic.
                draw = rng.choice([-1., 0., 1.], (features.shape[1], 128), p=[1/6, 2/3, 1/6])
                self.projection = (draw * np.sqrt(3/128)).astype(np.float32)
                features = features @ self.projection
            ids = rng.choice(len(features), min(patches_per_image, len(features)), replace=False)
            samples.append(features[ids])
            if (i+1) % 50 == 0:
                print(json.dumps({"phase":"fit", "category":category, "done":i+1, "total":len(paths)}), flush=True)
        pool = np.concatenate(samples)
        self.memory = coreset(pool, min(max_memory, len(pool)), rng)
        scores, pixels = [], []
        for i, path in enumerate(calibration):
            result = self.predict(_read(path))
            scores.append(result["score"])
            # Same aspect-preserving max-side256 scoring grid as evaluation.
            h, w = result["score_map"].shape
            ratio = 256 / max(h,w)
            pixels.append(cv2.resize(result["score_map"], (round(w*ratio), round(h*ratio))).ravel())
        output.mkdir(parents=True, exist_ok=True)
        bank = output / "patch_bank.npz"
        np.savez_compressed(bank, projection=self.projection, memory=self.memory)
        self.metadata = {
            "model_version":VERSION,"model_mode":"opencv_dnn_patch_memory", "category":category,
            "data_source":f"VisA:{category}","synthetic":False,"side":self.side,"layers":self.layers,
            "weights_sha256":WEIGHTS_SHA256,"feature_graph_sha256":FEATURE_GRAPH_SHA256,"weights_url":WEIGHTS_URL,"weights_license":"Apache-2.0",
            "training_count":len(paths),"calibration_count":len(calibration),"seed":SEED,
            "training_sha256":fit_hashes,"calibration_sha256":cal_hashes,
            "memory_patch_count":len(self.memory),"sampled_patch_count":len(pool),"patches_per_fit_image":patches_per_image,
            "image_threshold":float(np.quantile(scores,.95,method="higher")),
            "pixel_threshold":float(np.quantile(np.concatenate(pixels),.995,method="higher")),
            "calibration_image_scores":scores,"normal_bank_sha256":digest(bank),
            "calibration_method":"95th percentile (higher) of normal calibration image max-patch distances",
            "pixel_threshold_method":"99.5th percentile (higher) of normal calibration full-map pixels at max-side256",
            "adaptation":"ResNet50 stage2/3 local mean +128D projection +projected greedy coreset; exact L2 nearest patch; not official PatchCore",
        }
        (output/"metadata.json").write_text(json.dumps(self.metadata,indent=2),encoding="utf-8")
        return self.metadata

    @classmethod
    def load(cls, directory: Path, weights: Path) -> "PatchMemory":
        meta = json.loads((directory/"metadata.json").read_text(encoding="utf-8"))
        if meta["model_version"] != VERSION or meta["weights_sha256"] != WEIGHTS_SHA256:
            raise RuntimeError("Unsupported patch model manifest")
        if digest(directory/"patch_bank.npz") != meta["normal_bank_sha256"]:
            raise RuntimeError("Patch memory SHA256 mismatch")
        model = cls(weights, side=meta["side"])
        model.layers = meta["layers"]
        with np.load(directory/"patch_bank.npz",allow_pickle=False) as arrays:
            model.projection, model.memory = arrays["projection"], arrays["memory"]
        model.metadata = meta
        return model


def _read(path: Path) -> np.ndarray:
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Cannot decode {path.name}")
    return image
