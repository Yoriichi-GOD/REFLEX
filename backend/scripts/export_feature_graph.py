"""Expose exact pretrained residual-stage outputs without changing parameters."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import tempfile

import onnx
from app.core.patch_memory import WEIGHTS_SHA256, digest

OUTPUTS=["resnetv17_stage2_activation3","resnetv17_stage3_activation5"]


def main():
    parser=argparse.ArgumentParser();parser.add_argument("weights",type=Path)
    args=parser.parse_args();weights=args.weights.resolve()
    if digest(weights)!=WEIGHTS_SHA256:raise RuntimeError("Unverified pretrained weights")
    original=onnx.load(weights)
    model=onnx.load(weights)
    data=next(i for i in model.graph.input if i.name=="data")
    data.type.tensor_type.shape.dim[0].dim_value=1
    data.type.tensor_type.shape.dim[2].dim_value=256
    data.type.tensor_type.shape.dim[3].dim_value=256
    output=weights.with_suffix(".features.onnx")
    with tempfile.TemporaryDirectory(prefix="reflex-onnx-") as temp:
        source=Path(temp)/"resized.onnx";onnx.save(model,source)
        onnx.utils.extract_model(str(source),str(output),["data"],OUTPUTS)
    exported=onnx.load(output);onnx.checker.check_model(exported)
    original_parameters={p.name:p.SerializeToString() for p in original.graph.initializer}
    assert all(p.SerializeToString()==original_parameters[p.name] for p in exported.graph.initializer)
    original_nodes={n.name:n.SerializeToString() for n in original.graph.node}
    assert all(n.SerializeToString()==original_nodes[n.name] for n in exported.graph.node)
    result={"parent_sha256":WEIGHTS_SHA256,"feature_graph_sha256":digest(output),"bytes":output.stat().st_size,
            "outputs":OUTPUTS,"onnx_version":onnx.__version__,"unchanged_parameters":len(exported.graph.initializer),
            "unchanged_nodes":len(exported.graph.node),"only_changes":"input 1x3x256x256; expose stage2/3; prune unreachable classification graph"}
    output.with_suffix(".provenance.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result))


if __name__=="__main__":main()
