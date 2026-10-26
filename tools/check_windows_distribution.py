"""Opt-in real frozen/installer acceptance. Never operate on production data."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ssdl.process_group import ProcessGroup


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--work-dir',type=Path)
    parser.add_argument('--gui',action='store_true',help='Also open an admitted native WebView2 window')
    parser.add_argument('--iscc',type=Path,help='Also compile and exercise isolated user installers')
    args=parser.parse_args(argv)
    if os.name!='nt':parser.error('Windows is required')
    result={'schema':1,'passed':False}
    try:
        with tempfile.TemporaryDirectory(prefix='ssdl-frozen-',dir=args.work_dir,ignore_cleanup_errors=True) as temporary:
            workspace=Path(temporary).resolve();token=uuid.uuid4().hex
            (workspace/'.ssdl-install-fixture').write_text(token,encoding='ascii')
            env={**os.environ,'SSDL_FROZEN_FIXTURE_TOKEN':token}
            with (workspace/'acceptance.log').open('wb') as log:
                process=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'tests/helpers/frozen_acceptance.py'),
                    str(workspace),str(args.bundle.resolve()),token, str(args.iscc.resolve()) if args.iscc else '-', 'gui' if args.gui else 'headless'],cwd=ROOT,env=env,stdin=subprocess.PIPE,
                    stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
                group=None
                try:
                    group=ProcessGroup(process)
                    process.stdin.write(b'run\n');process.stdin.flush()
                    code=process.wait(timeout=600)
                finally:
                    if group is not None:group.close()
                    elif process.poll() is None:process.kill()  # Admission never happened.
                    process.stdin.close();process.wait(timeout=15)
            if code:
                print((workspace/'acceptance.log').read_text(encoding='utf-8',errors='replace')[-5000:],file=sys.stderr)
                raise RuntimeError('Frozen acceptance failed')
            receipt=json.loads((workspace/'frozen-report.json').read_text())
            if receipt.get('passed') is not True:raise RuntimeError('Incomplete acceptance receipt')
            result.update(passed=True,phases=receipt['phases'])
        result['workspace_cleanup']='retained' if workspace.exists() else 'removed'
        return 0
    finally:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))


if __name__=='__main__':raise SystemExit(main())
