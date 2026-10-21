"""Actual local host binds and file-backed Compose secrets, using invented data."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

from .check_docker import decode_json, ordinary, require
from .docker_service_acceptance import Fixtures, available_port
from .docker_interaction_acceptance import json_request, login_contract, pair, status, token

STAGES = ('private_host_directories', 'host_bind_contract', 'missing_bind_behavior', 'host_key_generation',
          'file_secret_restart', 'host_backup_integrity', 'host_restore_login', 'missing_secret_rejection')

ACL_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
$path = $env:SSDL_ACCEPTANCE_ACL_PATH
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$allowed = @($user.Value, 'S-1-5-18', 'S-1-5-32-544')
if ($env:SSDL_ACCEPTANCE_ACL_SET -eq '1') {
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sidText in $allowed) {
        $sid = [System.Security.Principal.SecurityIdentifier]::new($sidText)
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new($sid,
            'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    [System.IO.Directory]::SetAccessControl($path, $acl)
}
$section = [System.Security.AccessControl.AccessControlSections]::Access -bor [System.Security.AccessControl.AccessControlSections]::Owner
if ([System.IO.Directory]::Exists($path)) {
    $actual = [System.IO.Directory]::GetAccessControl($path, $section)
} else {
    $actual = [System.IO.File]::GetAccessControl($path, $section)
}
if ($env:SSDL_ACCEPTANCE_ACL_ROOT -eq '1' -and -not $actual.AreAccessRulesProtected) { throw 'ACL inheritance' }
$rules = @($actual.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
if ($rules.Count -lt 1) { throw 'Empty ACL' }
$currentUser = $false
foreach ($rule in $rules) {
    $ownerAlias = $rule.IdentityReference.Value -eq 'S-1-3-4' -and
        $actual.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -eq $user.Value
    if (($rule.IdentityReference.Value -notin $allowed -and -not $ownerAlias) -or $rule.AccessControlType -ne 'Allow' -or
        ($rule.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::FullControl) -ne
            [System.Security.AccessControl.FileSystemRights]::FullControl) { throw 'Unexpected ACL' }
    if ($rule.IdentityReference.Value -eq $user.Value -or $ownerAlias) { $currentUser = $true }
}
if (-not $currentUser) { throw 'Missing owner access' }
'''


def host_acl(path, *, create=False, root=False):
    environment = dict(os.environ, SSDL_ACCEPTANCE_ACL_PATH=str(path),
                       SSDL_ACCEPTANCE_ACL_SET='1' if create else '0', SSDL_ACCEPTANCE_ACL_ROOT='1' if root else '0')
    # A pwsh parent may export its incompatible PS7 module path to Windows PS5.
    native = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0'
    environment['PSModulePath'] = str(native / 'Modules')
    result = subprocess.run([str(native / 'powershell.exe'), '-NoProfile', '-NonInteractive', '-Command', ACL_SCRIPT],
                            env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    require(result.returncode == 0, 'private_host_acl_failed')


def host_path(root, name):
    require(re.fullmatch(r'[a-z][a-z-]*', name), 'invalid_fixture_path')
    path = root / name
    require(path.resolve().parent == root and not path.is_symlink() and ',' not in str(path), 'unsafe_fixture_bind')
    return path


def bind_contract(model, keys, backups):
    login_contract(model)
    services = model['services']
    for name, target, source in (('storage', '/backups', backups), ('session-key', '/keys', keys)):
        service = services[name]
        selected = [item for item in service['volumes'] if item['target'] == target]
        require(service['network_mode'] == 'none' and service['read_only'] is True and len(selected) == 1,
                'unsafe_host_maintenance')
        mount = selected[0]
        require(mount['type'] == 'bind' and Path(mount['source']) == source
                and mount.get('bind', {}).get('create_host_path', False) is False, 'changed_host_bind')
    require(Path(model['secrets']['x_session_key']['file']) == keys / 'x-session.key', 'changed_host_secret')


class HostFixtures:
    """Own host permissions and actual Compose mounts behind one fixture interface."""
    def __init__(self, fixtures):
        self.fixtures = fixtures
        self.root = fixtures.directory.resolve()
        self.keys, self.backups = host_path(self.root, 'private-keys'), host_path(self.root, 'private-backups')
        self.probe = (fixtures.root / 'tools/docker_host_probe.py').read_bytes()
        self.helper = None
        if os.name == 'nt':
            host_acl(self.root, create=True, root=True)
        else:
            info = self.root.stat()
            require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700, 'unsafe_host_directory')
        for path in (self.keys, self.backups):
            path.mkdir(mode=0o700)
            (path / '.ssdl-acceptance').write_text(fixtures.receipt)
        fixtures.environment.update(SSDL_X_KEY_DIR=self.keys.as_posix(), SSDL_BACKUP_DIR=self.backups.as_posix())
        self.override = self.root / 'compose.login.yaml'
        self.override.write_bytes((fixtures.root / 'compose.login.yaml').read_bytes())

    def model(self, port):
        self.fixtures.model(port)
        _, result = self.fixtures.compose(self.fixtures.source, self.fixtures.prefix,
            ['-f', str(self.override), '--profile', 'maintenance', 'config', '--format', 'json'])
        value = decode_json(result)
        bind_contract(value, self.keys, self.backups)
        return value

    def project(self, group, port, suffix):
        # Reuse the service fixture's ownership/network logic; retain real host mounts.
        unused = self.fixtures.volume(suffix + '-unused')
        project = self.fixtures.project(group, unused, port, suffix=suffix)
        config = json.loads(project['path'].read_text())
        actual = self.model(port)
        for name in ('storage', 'session-key'):
            service = actual['services'][name]
            service.update(image=self.fixtures.image, labels={'ssdl.acceptance': self.fixtures.receipt})
            config['services'][name] = service
        config['secrets'] = actual['secrets']
        app = config['services']['downloader']
        app['environment']['SSDL_X_KEY_FILE'] = '/run/secrets/x_session_key'
        app['environment']['SSDL_DOCKER_ACCEPTANCE'] = self.fixtures.receipt
        app['secrets'] = actual['services']['downloader']['secrets']
        app['container_name'] = project['name'] + '-app'
        self.fixtures.containers.append(app['container_name'])
        project['path'].write_text(json.dumps(config), encoding='utf-8')
        return project

    def start_helper(self, group):
        fixtures = self.fixtures
        require(set(group) == {'data', 'cache', 'media'} and set(group.values()) <= set(fixtures.volumes),
                'foreign_fixture_mount')
        self.helper = fixtures.prefix + '-host-helper'
        fixtures.containers.append(self.helper)
        args = ['run', '-d', '--name', self.helper, '--label', 'ssdl.acceptance=' + fixtures.receipt,
                '--env', 'SSDL_DOCKER_ACCEPTANCE=' + fixtures.receipt,
                '--env', 'SSDL_HOST_POSIX=' + ('0' if os.name == 'nt' else '1'),
                '--user', '0:0', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                '--cap-add', 'CHOWN', '--cap-add', 'FOWNER', '--cap-add', 'DAC_OVERRIDE',
                '--security-opt', 'no-new-privileges:true', '--no-healthcheck']
        for source, destination in ((str(self.keys), '/keys'), (str(self.backups), '/backups'),
                                    (group['data'], '/app/data'), (group['media'], '/downloads')):
            kind = 'bind' if destination in {'/keys', '/backups'} else 'volume'
            args += ['--mount', f'type={kind},source={source},target={destination}']
        fixtures.docker.run([*args, '--entrypoint', 'python', fixtures.image, '-c', 'import time; time.sleep(900)'])

    def action(self, name, *values, root=False, container=None):
        target = container or self.helper
        self.fixtures.state(target)
        code, content = self.fixtures.docker.run(['exec', '-i', '--user', '0:0' if root else '10001:10001',
            target, 'python', '-', name, *values], data=self.probe, check=False, timeout=60)
        require(code == 0, 'host_fixture_failed')
        result = decode_json(content)
        require(set(result) == {'receipt', 'result'} and result['receipt'] == self.fixtures.receipt
                and isinstance(result['result'], dict), 'invalid_host_receipt')
        return result['result']

    def maintenance(self, project, service, *args, expected=0):
        fixtures = self.fixtures
        fixtures.sequence += 1
        name = fixtures.prefix + '-host-maintenance-' + str(fixtures.sequence)
        fixtures.containers.append(name)
        code, _ = fixtures.compose(project['path'], project['name'], ['--profile', 'maintenance', 'run', '--rm',
            '--no-deps', '--name', name, service, *args], timeout=90, check=False)
        require(expected is None or code == expected, 'unexpected_host_maintenance_exit')
        return code

    def verify_acl(self):
        if os.name == 'nt':
            host_acl(self.root, root=True)
            for directory in (self.keys, self.backups):
                host_acl(directory)
                for path in directory.iterdir():
                    require(path.is_file() and not path.is_symlink(), 'unsafe_host_file')
                    host_acl(path)

    def return_owner(self):
        if self.helper is not None:
            uid, gid = (10001, 10001) if os.name == 'nt' else (os.getuid(), os.getgid())
            self.action('return-owner', str(uid), str(gid), root=True)


def run_checks(docker, image, receipt, root, report):
    sources = ('compose.yaml', 'compose.login.yaml', 'tools/docker_host_acceptance.py', 'tools/docker_host_probe.py')
    for name in sources:
        ordinary(root / name, root)
    report['host_sources_sha256'] = hashlib.sha256(b''.join((root / name).read_bytes() for name in sources)).hexdigest()
    report['host_checks'] = []
    report['host_permissions'] = 'windows_acl' if os.name == 'nt' else 'posix_uid_10001'
    current = STAGES[0]
    def passed():
        report['host_checks'].append(current)
        print('Docker host acceptance: ' + current, file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory(prefix='ssdl-host bind-') as directory:
        fixtures = Fixtures(docker, image, receipt, root, Path(directory))
        host = None
        try:
            host = HostFixtures(fixtures)
            passed()
            current = STAGES[1]
            group = fixtures.group('host')
            port = available_port()
            project = host.project(group, port, 'host')
            host.start_helper(group)
            host.action('initialize', root=True)
            passed()
            current = STAGES[2]
            missing = host_path(host.root, 'missing-keys')
            config = json.loads(project['path'].read_text())
            config['services']['session-key']['volumes'][0]['source'] = str(missing)
            rejected = dict(project, path=host.root / 'missing-bind.json')
            rejected['path'].write_text(json.dumps(config), encoding='utf-8')
            code = host.maintenance(rejected, 'session-key', expected=None)
            if code == 0:
                require(os.name == 'nt' and missing.is_dir() and (missing / 'x-session.key').stat().st_size == 32,
                        'unexpected_missing_bind_behavior')
                host_acl(missing)
                host_acl(missing / 'x-session.key')
                report['host_missing_bind'] = 'desktop_created_private_directory'
            else:
                require(not missing.exists(), 'missing_bind_created')
                report['host_missing_bind'] = 'rejected'
            passed()
            current = STAGES[3]
            host.maintenance(project, 'session-key')
            key = host.action('key-info')
            host.maintenance(project, 'session-key', expected=1)
            require(host.action('key-info') == key, 'host_key_overwritten')
            host.verify_acl()
            passed()
            current = STAGES[4]
            helper = fixtures.helper(group)
            fixtures.probe_action(helper, 'seed')
            fixtures.up(project)
            code, setup = json_request(project, '/api/auth/x/setup')
            require(code == 200 and setup['persistent'] and setup['storage_mode'] == 'aes-gcm', 'host_secret_mode_failed')
            mounts = fixtures.state(project['container'])['Mounts']
            require(any(item['Type'] == 'bind' and item['Destination'] == '/run/secrets/x_session_key'
                        and item['RW'] is False for item in mounts), 'file_secret_not_readonly_bind')
            host.action('secret-readonly', container=project['container'])
            pair(project, setup, token(project))
            fixtures.stop(project)
            fixtures.up(project)
            status(project, True)
            fixtures.stop(project)
            passed()
            current = STAGES[5]
            before = fixtures.probe_action(helper, 'inventory')
            host.maintenance(project, 'storage', 'backup')
            archive = host.action('archive')
            require(fixtures.probe_action(helper, 'inventory') == before and host.action('key-info') == key,
                    'host_backup_changed_originals')
            host.verify_acl()
            passed()
            current = STAGES[6]
            restored = fixtures.group('host-recovery')
            recovery_helper = fixtures.helper(restored)
            recovery = host.project(restored, available_port(), 'host-recovery')
            host.maintenance(recovery, 'storage', 'restore', archive['archive'])
            require(fixtures.probe_action(recovery_helper, 'inventory') == before, 'host_restore_mismatch')
            fixtures.probe_action(recovery_helper, 'verify')
            fixtures.probe_action(recovery_helper, 'cache-empty')
            fixtures.up(recovery)
            status(recovery, True)
            fixtures.stop(recovery)
            passed()
            current = STAGES[7]
            saved_session = host.action('session-hash')
            config = json.loads(project['path'].read_text())
            absent = host.keys / 'absent.key'
            config['secrets']['x_session_key']['file'] = str(absent)
            rejected = dict(project, path=host.root / 'missing-secret.json')
            rejected['path'].write_text(json.dumps(config), encoding='utf-8')
            code, _ = fixtures.compose(rejected['path'], rejected['name'],
                ['up', '-d', '--force-recreate', '--no-build', '--pull', 'never', 'downloader'], check=False, timeout=60)
            missing_key = host.action('missing-key')
            if code == 0:
                require(os.name == 'nt' and missing_key == {'kind': 'directory'}, 'unexpected_missing_secret_behavior')
                fixtures.up(rejected)
                status(rejected, False)
                require(json_request(rejected, '/api/auth/x/connect', data={})[0] == 400,
                        'invalid_secret_pairing_allowed')
                fixtures.stop(rejected)
                report['host_missing_secret'] = 'desktop_directory_key_rejected'
            else:
                require(missing_key == {'kind': 'absent'}, 'missing_secret_created')
                report['host_missing_secret'] = 'compose_rejected'
            require(host.action('key-info') == key and host.action('session-hash') == saved_session,
                    'missing_secret_changed_originals')
            fixtures.probe_action(helper, 'verify')
            passed()
            require(report['host_checks'] == list(STAGES), 'incomplete_host_acceptance')
        except Exception:
            report['host_error'] = current + '_failed'
            raise
        finally:
            try:
                if host is not None:
                    host.return_owner()
            finally:
                fixtures.cleanup()
