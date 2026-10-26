"""Opt-in, fixed GUI acceptance actions in an explicitly admitted disposable scope.

No eval/command channel is exposed. Ordinary launches never import this probe.
"""
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time


def install():
    from ssdl.runtime_paths import paths
    home=paths().home
    token=os.environ['SSDL_FROZEN_PROBE_TOKEN']
    receipt=home.parent/'.ssdl-install-fixture'
    if (not re.fullmatch('[a-f0-9]{32}',token) or not os.environ.get('SSDL_HOME')
            or receipt.is_symlink() or not secrets.compare_digest(receipt.read_text(encoding='ascii'),token)):
        raise RuntimeError('GUI acceptance admission refused')
    import webview
    original=webview.create_window
    def create(*args,**kwargs):
        window=original('D05 隔離打包驗收',*args[1:],**kwargs)
        api=kwargs['js_api']
        completed=threading.Event()
        def observe():
            if completed.is_set() or not api._trusted():return
            completed.set()
            result={'passed':False}
            try:
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    state=window.evaluate_js("({ready:!!lastResponse,language:I18n.language,page_size:state.pageSize,picker:!document.querySelector('#download-dir-pick').hidden})")
                    if state['ready'] and state['language']=='en' and state['page_size']==50 and state['picker']:break
                    time.sleep(.1)
                assert state['ready'] and state['language']=='en' and state['page_size']==50 and state['picker']
                description=api.describe()
                assert description['version']==1 and description['kind']=='pywebview' and description['capabilities']['pickDirectory']
                result.update(passed=True,ui=state,bridge=description,service=api._policy.service)
            except Exception as error:
                result['error']=type(error).__name__
            finally:
                (home.parent/'frozen-gui.json').write_text(json.dumps(result),encoding='utf-8')
                window.confirm_close=False
                window.destroy()
        window.events.loaded+=observe
        return window
    webview.create_window=create
