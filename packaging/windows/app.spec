# PyInstaller onedir: one GUI and one console/pipe runtime, sharing dependencies.
import json
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata

stage = Path(os.environ['SSDL_BUILD_STAGE'])
source = stage / 'source'
manifest = json.loads((stage / 'bundle-manifest.json').read_text(encoding='utf-8'))
datas = [(str(source / 'static'), 'static'), (str(source / 'chrome-extension'), 'chrome-extension'),
         (str(stage / 'tools-runtime'), 'tools-runtime'),
         (str(stage / 'licenses'), 'licenses'), (str(stage / 'sources'), 'sources'),
         (str(stage / 'bundle-manifest.json'), '.')]
hidden = collect_submodules('ssdl') + collect_submodules('desktop')
for module in ('yt_dlp', 'gallery_dl', 'mutagen', 'websockets', 'yt_dlp_ejs'):
    hidden += collect_submodules(module)
    datas += collect_data_files(module, include_py_files=True)
for module in ('certifi', 'playwright', 'webview'):
    datas += collect_data_files(module)
for distribution in manifest['packages']:
    datas += copy_metadata(distribution)
hidden += ['webview.platforms.winforms', 'clr', 'clr_loader', 'pythonnet', 'brotli', 'Cryptodome']
a = Analysis([str(source / 'desktop/frozen_entry.py')], pathex=[str(source)], binaries=[], datas=datas,
    hiddenimports=hidden, hookspath=[], runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'tkinter', 'gi', 'wx', 'tests'])
# The wheel's unrelated GPL FFmpeg must never enter this independently built bundle.
a.datas = [item for item in a.datas if not item[0].replace('\\', '/').startswith('imageio_ffmpeg/binaries/')]
a.binaries = [item for item in a.binaries if not item[0].replace('\\', '/').startswith('imageio_ffmpeg/binaries/')]
pyz = PYZ(a.pure)
gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name='SmartSocialDownloader', console=False,
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False)
runtime = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ssdl-runtime', console=True,
              debug=False, bootloader_ignore_signals=False, strip=False, upx=False)
coll = COLLECT(gui, runtime, a.binaries, a.datas, strip=False, upx=False, name='SmartSocialDownloader')
