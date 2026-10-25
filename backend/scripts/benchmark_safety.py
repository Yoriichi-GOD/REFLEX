"""Run the separate generated-video software suite, never a real industrial benchmark."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    from reflex_safety.fixtures import generate
    from reflex_safety.benchmark import run
    fixtures=ROOT/'data/safety_fixtures';generate(fixtures)
    result=run(fixtures,args.output,split='test')
    print('SYNTHETIC SOFTWARE TEST — real procedural video benchmark NOT RUN')
    print(f"Saved {result['prediction_rows']} measured policy rows from {result['n_unique_clips']} generated clips to {args.output}")
if __name__=='__main__':main()
