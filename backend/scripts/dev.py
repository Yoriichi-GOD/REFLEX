"""OS-selected free loopback port, same-origin frontend/API; no other process killed."""
from pathlib import Path
import argparse,json,socket,sys,os
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=0);parser.add_argument('--real',action='store_true',help='Use the retained frozen candle/cashew demo profiles and pinned ONNX weights');args=parser.parse_args()
    if args.real:
        weights=ROOT/'demo/pretrained/resnet50-v1-12.onnx'
        if not weights.is_file():parser.error('Run python backend/scripts/prepare_public_weights.py first; real profiles require the pinned weights')
        os.environ.update(REFLEX_PROFILES_DIR=str(ROOT/'demo/profiles'),REFLEX_DEFAULT_PROFILE='candle',REFLEX_EVALUATION_DIR=str(ROOT/'demo/evaluations'),REFLEX_ONNX_WEIGHTS=str(weights))
    fixture_root=ROOT/'data/safety_fixtures'
    if not (fixture_root/'manifest.json').is_file():
        from reflex_safety.fixtures import generate
        generate(fixture_root)
    os.environ.setdefault('REFLEX_SAFETY_FIXTURES',str(fixture_root))
    import uvicorn
    sock=socket.socket();sock.bind(('127.0.0.1',args.port));sock.listen(128);port=sock.getsockname()[1]
    print(json.dumps({'inspection_studio':f'http://127.0.0.1:{port}/','safety_station':f'http://127.0.0.1:{port}/safety','same_origin_backend':f'http://127.0.0.1:{port}/api','port_selection':'OS-assigned;socket held through startup'}),flush=True)
    uvicorn.Server(uvicorn.Config('app.extension_main:app',host='127.0.0.1',port=port,log_level='info')).run(sockets=[sock])
if __name__=='__main__':main()
