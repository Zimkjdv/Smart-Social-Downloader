"""Build an inspectable onedir bundle and per-user installer from reviewed sources."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.package_source import source_files, create_archive
from tools.check_installation import pinned_versions
from ssdl.version import __version__


def download(item, cache):
    target = cache / item['filename']
    if not target.exists():
        temporary = target.with_suffix(target.suffix + '.tmp')
        with urllib.request.urlopen(item['url'], timeout=60) as response, temporary.open('wb') as output:
            shutil.copyfileobj(response, output)
        temporary.replace(target)
    if hashlib.sha256(target.read_bytes()).hexdigest() != item['sha256']:
        raise ValueError('Build input checksum mismatch: ' + target.name)
    return target


def reviewed_source(destination):
    # A Git checkout may contain private/unreviewed files matching docs globs.
    if (ROOT / '.git').exists():
        names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
        for name in filter(None, names):
            p = ROOT / name
            if p.is_file():
                q = destination / name; q.parent.mkdir(parents=True, exist_ok=True); q.write_bytes(p.read_bytes())
        source_files(destination)
    else:
        for p in source_files(ROOT):
            q = destination / p.relative_to(ROOT);q.parent.mkdir(parents=True, exist_ok=True);q.write_bytes(p.read_bytes())


def verify_signature(path, publisher):
    script = "$ErrorActionPreference='Stop'; $s=Get-AuthenticodeSignature -LiteralPath $env:SSDL_BUILD_ASSET; if($s.Status -ne 'Valid' -or -not $s.SignerCertificate.Subject.Contains($env:SSDL_BUILD_PUBLISHER)) { exit 1 }"
    env={k:v for k,v in os.environ.items() if k.lower()!='psmodulepath'}
    env.update(SSDL_BUILD_ASSET=str(path),SSDL_BUILD_PUBLISHER=publisher)
    checked=subprocess.run(['powershell.exe','-NoProfile','-Command',script],capture_output=True,env=env)
    if checked.returncode:
        raise ValueError('Build tool publisher signature could not be verified')


def compiler(cache, item):
    installer = download(item, cache)
    verify_signature(installer,'CN=Pyrsys B.V.,')
    directory = cache / 'inno-6.7.3'
    if not (directory / 'ISCC.exe').is_file():
        subprocess.run([str(installer),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER',
            '/NOICONS','/DIR='+str(directory)],check=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    return directory / 'ISCC.exe'


def build(output, ffmpeg, cache, iscc=None):
    if os.name != 'nt' or sys.version_info[:2] != (3,12):
        raise RuntimeError('Build with Windows x64 / Python 3.12 and requirements-build.txt')
    output.mkdir(parents=True, exist_ok=False)
    stage = output / 'stage';source = stage / 'source'
    source.mkdir(parents=True)
    reviewed_source(source)
    from packaging.requirements import Requirement
    packages = {}
    for filename in ('requirements.lock.txt','requirements-desktop.txt','requirements-browser.txt'):
        for line in (source / filename).read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            requirement = Requirement(line)
            if requirement.marker and not requirement.marker.evaluate():
                continue
            pins = list(requirement.specifier)
            if len(pins) != 1 or pins[0].operator != '==':
                raise ValueError('Release dependencies must be pinned')
            packages[requirement.name] = pins[0].version
    for name, version in packages.items():
        if metadata.version(name) != version:
            raise RuntimeError('Build environment differs from reviewed pins: ' + name)
    subprocess.run([sys.executable,'-m','pip','check'],check=True)
    inputs=json.loads((source/'packaging/windows/inputs.json').read_text())
    cache.mkdir(parents=True,exist_ok=True)
    node=download(inputs['node'],cache)
    tools=stage/'tools-runtime';tools.mkdir()
    licenses=stage/'licenses';licenses.mkdir()
    sources=stage/'sources';sources.mkdir()
    with zipfile.ZipFile(node) as archive:
        prefix=inputs['node']['filename'].removesuffix('.zip')+'/'
        (tools/'node.exe').write_bytes(archive.read(prefix+'node.exe'))
        (licenses/'Node-LICENSE.txt').write_bytes(archive.read(prefix+'LICENSE'))
    zlib_archive=ffmpeg/'sources/zlib-1.3.2.tar.xz'
    if hashlib.sha256(zlib_archive.read_bytes()).hexdigest()!=inputs['zlib-source']['sha256']:
        raise ValueError('Zlib source checksum differs')
    bootstrapper=download(inputs['webview-bootstrapper'],cache)
    verify_signature(bootstrapper,'CN=Microsoft Corporation,')
    shutil.copyfile(bootstrapper,tools/bootstrapper.name)
    sdk=download(inputs['webview-sdk'],cache)
    with zipfile.ZipFile(sdk) as package:
        for name in ('LICENSE.txt','NOTICE.txt'):
            (licenses/('Microsoft-WebView2-'+name)).write_bytes(package.read(name))

    expected=inputs['ffmpeg-source']['sha256']
    archive=ffmpeg/'sources/ffmpeg-8.1.3.tar.xz'
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
        raise ValueError('FFmpeg corresponding-source checksum differs')
    shutil.copyfile(ffmpeg/'ffmpeg.exe',tools/'ffmpeg.exe')
    for folder,target in (('licenses',licenses),('sources',sources)):
        for p in (ffmpeg/folder).iterdir():
            if p.is_file():shutil.copyfile(p,target/p.name)
    license_text=subprocess.check_output([str(tools/'ffmpeg.exe'),'-L'],stderr=subprocess.STDOUT).decode(errors='replace')
    license_text = ' '.join(license_text.split())
    if 'GNU Lesser General Public License' not in license_text or 'GNU General Public License' in license_text:
        raise ValueError('FFmpeg must be the independently built LGPL binary')
    shutil.copyfile(source/'packaging/windows/ffmpeg.Dockerfile',sources/'ffmpeg.Dockerfile')
    shutil.copyfile(source/'docker/debian.sources',sources/'debian.sources')
    create_archive(source,sources/'application-source.zip')
    shutil.copyfile(download(inputs['proxy-tools-license'],cache),licenses/'proxy_tools-LICENSE.txt')
    for name in (*packages, 'pyinstaller'):
        dist=metadata.distribution(name)
        for member in dist.files or ():
            if any(word in str(member).lower() for word in ('license','copying','notice')):
                p=dist.locate_file(member)
                if p.is_file():
                    destination=licenses/name/str(member).replace('../','')
                    destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,destination)
        if name in {'gallery-dl','mutagen'}:
            with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{packages[name]}/json',timeout=30) as response:
                release=json.load(response)
            item=next(x for x in release['urls'] if x['packagetype']=='sdist')
            original=download({'url':item['url'],'filename':item['filename'],'sha256':item['digests']['sha256']},cache)
            shutil.copyfile(original,sources/original.name)
    shutil.copyfile(source/'LICENSE',licenses/'PROJECT-LICENSE.txt')
    shutil.copyfile(source/'THIRD_PARTY_NOTICES.md',licenses/'THIRD_PARTY_NOTICES.md')
    shutil.copyfile(Path(sys.base_prefix)/'LICENSE.txt',licenses/'CPython-LICENSE.txt')
    manifest={'schema':1,'application_source_sha256':hashlib.sha256((sources/'application-source.zip').read_bytes()).hexdigest(),'app_version':__version__,'python':sys.version.split()[0], 'packages':packages,'pyinstaller':metadata.version('pyinstaller'),
              'node':inputs['node'],'ffmpeg_source':inputs['ffmpeg-source'], 'format':'onedir-x64',
              'media_tools':{'node.exe':hashlib.sha256((tools/'node.exe').read_bytes()).hexdigest(),
                             'ffmpeg.exe':hashlib.sha256((tools/'ffmpeg.exe').read_bytes()).hexdigest()}}
    (stage/'bundle-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    env={**os.environ,'SSDL_BUILD_STAGE':str(stage)}
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--distpath',str(output/'dist'),
        '--workpath',str(output/'build'),str(source/'packaging/windows/app.spec')],cwd=source,env=env,check=True)
    bundle=output/'dist/SmartSocialDownloader'
    if any('imageio_ffmpeg/binaries' in str(p).replace('\\','/') and p.suffix=='.exe' for p in bundle.rglob('*')):
        raise ValueError('Unexpected wheel FFmpeg entered bundle')
    installer_compiler=Path(iscc) if iscc else compiler(cache,inputs['inno'])
    subprocess.run([str(installer_compiler),'/DBundleDir='+str(bundle),'/DBuildVersion='+__version__,
        '/O'+str(output/'installer'),str(source/'packaging/windows/setup.iss')],check=True)
    shutil.make_archive(str(output/'SmartSocialDownloader-windows-x64'),'zip',bundle.parent,bundle.name)
    products=[*output.glob('*.zip'),*(output/'installer').glob('*.exe')]
    (output/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in products))
    print(json.dumps({'passed':True,'bundle':str(bundle),'products':[str(p) for p in products]}))
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ffmpeg-dir',type=Path,required=True)
    parser.add_argument('--cache',type=Path,default=ROOT/'.release-check/windows-vendor')
    parser.add_argument('--iscc',type=Path)
    args=parser.parse_args(argv)
    return build(args.output.resolve(),args.ffmpeg_dir.resolve(),args.cache.resolve(),args.iscc)


if __name__=='__main__':raise SystemExit(main())
