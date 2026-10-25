# Third-party and supplied assets

REFLEX source code is MIT licensed. That grant does not relicense datasets, model weights, fonts, artwork or research reference material.

## VisA images and derived evidence

Real demo photographs, normal-patch memories and derived benchmark illustrations use VisA from Amazon Science:

Yang Zou, Jongheon Jeong, Latha Pemula, Dongqing Zhang and Onkar Dabeer. *SPot-the-Difference Self-Supervised Pre-training for Anomaly Detection and Segmentation*. ECCV 2022.

VisA is distributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See the [publisher repository](https://github.com/amazon-science/spot-diff). The six curated JPEGs are unmodified; generated heatmaps and overlays are identified as derived evidence. These curated examples are not an accuracy estimate. Retain attribution when redistributing them.

## ONNX model

The ResNet50-v1-12 model artifact comes from the ONNX model zoo, with Apache-2.0 terms upstream. Large weights are not tracked in this repository. The download helper verifies this SHA-256:

`3f03fdef724b22947eed826f1eef1dc5c34151bb4c37d634f1db89dfa2dd1526`

The feature graph is derived locally. See the [upstream model](https://github.com/onnx/models/tree/main/validated/vision/classification/resnet) and [model repository license](https://github.com/onnx/models/blob/main/LICENSE).

## Fonts

Inter, Space Grotesk and IBM Plex Mono have complete SIL Open Font License notices alongside the files in `frontend/assets-ui/fonts`. Retain those notices.

## Solar, space, logo and planet artwork

The project user supplied this artwork for the existing REFLEX identity and requested publication. No independent stock source, generation record or standalone open-image license has been established. Image pixels are excluded from the MIT source-code grant. Obtain permission from the rights holder for reuse beyond this project.

## Generated procedure fixtures

REFLEX software creates deterministic, nonphotographic drawings labeled **SYNTHETIC SOFTWARE TEST**. They are software fixtures, not physical industrial imagery. Their generator is source code covered by the project license.

## Assembly101

Assembly101 annotations and media have CC BY-NC 4.0 terms. Acquired annotations and gated videos are excluded from this public tree. See the [publisher's mistake-detection repository](https://github.com/assembly-101/assembly101-mistake-detection). No video benchmark was run.

## User-supplied sample kit

The supplied 96-image sample kit's README does not establish a redistribution license. Its bytes are excluded from public source. Supporting readers and tests remain separate from real benchmark results.

## Competition references

Private competition PDFs, templates and screenshots are reference inputs and are not republished wholesale as code. Authored slides and paper follow their reference visual direction while using actual REFLEX evidence and blank team fields.
