"""Cross-build the fixed LGPL Windows media tool with corresponding sources."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.build_windows import download


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cache',type=Path,default=ROOT/'.release-check/windows-vendor')
    args=parser.parse_args(argv)
    if args.output.exists():parser.error('Output must be a new directory')
    args.cache.mkdir(parents=True,exist_ok=True)
    inputs=json.loads((ROOT/'packaging/windows/inputs.json').read_text())
    with tempfile.TemporaryDirectory(prefix='ssdl-media-build-') as temporary:
        context=Path(temporary)
        shutil.copyfile(ROOT/'packaging/windows/ffmpeg.Dockerfile',context/'Dockerfile')
        shutil.copyfile(ROOT/'docker/debian.sources',context/'debian.sources')
        for key in ('ffmpeg-source','zlib-source'):
            item=inputs[key];shutil.copyfile(download(item,args.cache),context/item['filename'])
        subprocess.run(['docker','build','--progress','plain','--output','type=local,dest='+str(args.output.resolve()),str(context)],check=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
