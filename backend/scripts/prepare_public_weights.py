"""Fetch only the pinned public ONNX weight artifact; no dataset or credentials."""
from pathlib import Path
import argparse,hashlib,sys,urllib.request
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
from app.core.patch_memory import WEIGHTS_URL,WEIGHTS_SHA256
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-only',action='store_true');args=p.parse_args()
    target=ROOT/'demo/pretrained/resnet50-v1-12.onnx'
    if target.exists():
        if hashlib.file_digest(target.open('rb'),'sha256').hexdigest()!=WEIGHTS_SHA256:raise SystemExit('Existing weights hash mismatch; preserve and inspect before replacing')
        print('Verified existing pinned ONNX weights');return
    if args.check_only:raise SystemExit('Weights absent; run without --check-only to download the public pinned artifact')
    target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_suffix('.download')
    if temp.exists():raise SystemExit('An earlier download remains; inspect it before retrying')
    with urllib.request.urlopen(WEIGHTS_URL,timeout=60) as r,temp.open('xb') as out:
        while chunk:=r.read(1024*1024):out.write(chunk)
    with temp.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=WEIGHTS_SHA256:raise SystemExit('Downloaded weights failed SHA256; incomplete artifact retained for diagnosis')
    temp.rename(target);print('Downloaded and verified pinned ONNX weights (Apache-2.0 upstream; see THIRD_PARTY_NOTICES.md)')
if __name__=='__main__':main()
