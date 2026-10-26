"""Receipt-gated parent of all executable acceptance processes, before admission."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def main(workspace, bundle, token, iscc=None, gui=False):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from tests.helpers.install_runner import verify_receipt
    verify_receipt(workspace,token)
    if os.environ.get('SSDL_FROZEN_FIXTURE_TOKEN') != token or sys.stdin.readline().strip() != 'run':
        raise ValueError('Frozen acceptance admission refused')
    from tools.check_desktop import free_port
    from tools.check_installation import request, assert_port_closed
    from ssdl.persistence import StateStore
    from ssdl.ipc import write_message, read_message
    from ssdl.session_storage import SessionStorage
    from ssdl.x_auth import _dpapi
    home=workspace/'user data 圖片';media=workspace/'original media 圖片';media.mkdir()
    (media/'original.bin').write_bytes(b'original media remains unchanged')
    home.mkdir();(home/'data').mkdir()
    StateStore(home/'data/state.json').save({'schema_version':2,'paused':True,'download_dir':str(media),
        'jobs':[{'id':'retained','url':'https://example.org/fixture','status':'completed', 'created_at':1,
                 'platform':'Web','files':['original.bin'],'output_dir':str(media)}]})
    storage=SessionStorage(windows_protect=_dpapi)
    storage.save(home/'data/x-auth.bin',json.dumps({'cookies':{'auth_token':'synthetic-not-a-real-login'},'expires_at':time.time()+3600}).encode())
    storage.save(home/'data/pixiv-session.bin',json.dumps({'service':'pixiv','refresh_token':'synthetic-not-a-real-refresh-token'}).encode())
    port=free_port()
    env={k:v for k,v in os.environ.items() if k not in {'PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'} and not k.startswith('SSDL_')}
    env.update(SSDL_HOME=str(home),SSDL_PORT=str(port),SSDL_NONINTERACTIVE='1',
               PATH=str(Path(os.environ['SystemRoot'])/'System32'))
    result={'passed':False,'external_python_node_removed_from_path':True,'phases':[]}
    def command(executable,role,*args,expect=0,input=None):
        response=subprocess.run([str(executable),'--role',role,*args],cwd=workspace,env=env,
            input=input,capture_output=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
        if response.returncode!=expect:
            raise RuntimeError('Bundled role failed: '+role+' '+response.stderr.decode('utf-8',errors='replace')[-2000:])
        return json.loads(response.stdout)
    runtime=bundle/'ssdl-runtime.exe'
    service=None
    try:
        import hashlib
        manifest=json.loads((bundle/'_internal/bundle-manifest.json').read_text())
        assert hashlib.sha256((bundle/'_internal/sources/application-source.zip').read_bytes()).hexdigest()==manifest['application_source_sha256']
        assert list((bundle/'_internal/licenses/pyinstaller').rglob('COPYING.txt'))
        assert 'Armin Ronacher' in (bundle/'_internal/licenses/proxy_tools-LICENSE.txt').read_text()
        import base64
        png=media/'fixture.png';png.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII='))
        transcoded=workspace/'preview.jpg'
        subprocess.run([str(bundle/'_internal/tools-runtime/ffmpeg.exe'),'-v','error','-i',str(png),'-frames:v','1','-c:v','mjpeg',str(transcoded)],env=env,capture_output=True,check=True,timeout=20)
        assert transcoded.read_bytes().startswith(b'\xff\xd8')
        protocols=subprocess.check_output([str(bundle/'_internal/tools-runtime/ffmpeg.exe'),'-protocols'],env=env,stderr=subprocess.DEVNULL)
        assert b'https' in protocols
        result['phases'].append('bundled-png-thumbnail-codec-and-https-protocol')
        report=command(runtime,'diagnose')
        assert report['ready'] and all(x['status']=='ok' for x in report['checks'] if x['required'])
        result['phases'].append('bundled-tools-and-metadata-without-python-node-path')
        # Exercise real framed worker IPC and fixed-endpoint exchange rejection without network.
        worker=subprocess.Popen([str(runtime),'--role','worker'],cwd=workspace,env=env,stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        write_message(worker.stdin,{'url':'invalid','output_dir':str(media), 'image_history_file':str(home/'data/image-history.sqlite3'),
                                   'manifest_file':str(home/'data/media-manifest.sqlite3')})
        messages=[]
        while (value:=read_message(worker.stdout)) is not None: messages.append(value)
        worker.stdin.close();worker.stdout.close();assert worker.wait(timeout=10)==0
        assert any(value.get('type')=='error' for value in messages)
        assert command(runtime,'pixiv-exchange',expect=1,input=b'{"grant":"invalid"}')=={'error':'pixiv_auth_failed'}
        result['phases'].append('real-frozen-worker-and-pixiv-rejection-pipes')
        if gui:
            from ssdl.ui_preferences import UIPreferences
            UIPreferences(home/'data/ui-preferences.json').save({'schema':1,'language':'en','page_size':50})
            response=subprocess.run([str(bundle/'SmartSocialDownloader.exe')],cwd=workspace,
                env={**env,'SSDL_FROZEN_PROBE_TOKEN':token},capture_output=True,timeout=100,
                creationflags=subprocess.CREATE_NO_WINDOW)
            assert response.returncode==0
            receipt=json.loads((workspace/'frozen-gui.json').read_text())
            assert receipt['passed'] is True and receipt['service']['ownership']=='started'
            service=receipt['service']
            assert command(runtime,'control','status')['result']['instance']==service['instance']
            result['phases'].append('actual-frozen-webview2-ui-bridge-preferences-close-keeps-backend')
        else:
            service=command(runtime,'control','ensure')['result']
            assert service['ownership']=='started'
        same=command(runtime,'control','ensure')['result'];assert same['instance']==service['instance'] and same['ownership']=='attached'
        state=request(port,'/api/state');assert state['x_auth']['connected'] and state['pixiv_auth']['connected']
        assert state['total_jobs']==1 and state['paused']
        import urllib.request
        with urllib.request.urlopen(service['origin']+'/',timeout=5) as response: assert b'preferences.js' in response.read()
        request(port,'/api/ui-preferences',{'schema':1,'language':'en','page_size':50})
        result['phases'].append('frozen-http-ui-and-synthetic-dpapi-restored')
        # Another installation directory must attach to the same data-scope owner.
        other=workspace/'different installation';shutil.copytree(bundle,other)
        attached=command(other/'ssdl-runtime.exe','control','ensure')['result'];assert attached['instance']==service['instance']
        refused=command(other/'ssdl-runtime.exe','control','stop-owned',expect=1,input=json.dumps(attached).encode());assert refused['ok'] is False
        result['phases'].append('different-install-location-shares-owner-and-refuses-attached-stop')
        command(runtime,'control','stop-owned',input=json.dumps(service).encode());service=None;assert_port_closed(port)
        restarted=command(other/'ssdl-runtime.exe','control','ensure')['result'];service=restarted
        assert restarted['ownership']=='started'
        assert request(port,'/api/ui-preferences')['preferences']=={'schema':1,'language':'en','page_size':50}
        state=request(port,'/api/state');assert state['x_auth']['connected'] and state['pixiv_auth']['connected'] and state['total_jobs']==1
        command(other/'ssdl-runtime.exe','control','stop-owned',input=json.dumps(restarted).encode());service=None
        assert_port_closed(port)
        assert (media/'original.bin').read_bytes()==b'original media remains unchanged'
        assert not (bundle/'data').exists() and not (bundle/'_internal/data').exists()
        result['phases'].append('graceful-stop-and-new-location-restart-preserves-state-login-preferences-media')
        if iscc:
            installer_sources=Path(__file__).resolve().parents[2]/'packaging/windows/setup.iss'
            installers=[]
            for version in ('0.1.0','0.1.1'):
                directory=workspace/('installer-'+version)
                subprocess.run([str(iscc),'/DBundleDir='+str(bundle),'/DBuildVersion='+version,
                    '/DProductId=SSDL.Acceptance.'+token,'/O'+str(directory),str(installer_sources)],
                    check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=120)
                installers.append(next(directory.glob('*.exe')))
            installed=workspace/'installed application'
            def install(path,success=True):
                value=subprocess.run([str(path),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS',
                    '/DIR='+str(installed),'/LOG='+str(workspace/'install.log')],env=env,timeout=120,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                assert (value.returncode==0)==success
            install(installers[0])
            executable=installed/'ssdl-runtime.exe'
            service=command(executable,'control','ensure')['result']
            install(installers[1],False)  # Never close/kill an active application's files.
            command(executable,'control','stop-owned',input=json.dumps(service).encode());service=None
            for path in (installers[1],installers[0]):
                install(path)
                service=command(executable,'control','ensure')['result']
                assert request(port,'/api/ui-preferences')['preferences']['language']=='en'
                state=request(port,'/api/state');assert state['x_auth']['connected'] and state['pixiv_auth']['connected'] and state['total_jobs']==1
                command(executable,'control','stop-owned',input=json.dumps(service).encode());service=None
            uninstaller=installed/'unins000.exe'
            assert uninstaller.resolve().is_relative_to(workspace)
            subprocess.run([str(uninstaller),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],env=env,
                check=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
            assert not executable.exists()
            assert (home/'data/state.json').is_file() and (home/'data/x-auth.bin').is_file() and (home/'data/pixiv-session.bin').is_file()
            assert (media/'original.bin').read_bytes()==b'original media remains unchanged'
            result['phases'].append('actual-user-installer-update-rollback-active-refusal-and-uninstall-preserve-data')
        result.update(passed=True,home=str(home),port=port)
    finally:
        if service is not None:
            command(runtime,'control','stop-owned',input=json.dumps(service).encode())
        (workspace/'frozen-report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return 0


if __name__=='__main__':raise SystemExit(main(Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3],Path(sys.argv[4]) if len(sys.argv)>4 and sys.argv[4]!='-' else None, len(sys.argv)>5 and sys.argv[5]=='gui'))
