"""Host-mount contracts; fake CLI checks are not real host acceptance evidence."""
from copy import deepcopy
import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tests.helpers.docker import ServiceDocker
from tools import check_docker as gate
from tools import docker_host_acceptance as host
from tools.docker_service_acceptance import Fixtures


def model(keys, backups):
    return {'services': {
        'downloader': {'environment': {'SSDL_X_KEY_FILE': '/run/secrets/x_session_key'},
                       'secrets': [{'source': 'x_session_key', 'target': 'x_session_key'}]},
        'session-key': {'network_mode': 'none', 'read_only': True, 'volumes': [
            {'type': 'bind', 'source': str(keys), 'target': '/keys', 'bind': {'create_host_path': False}}]},
        'storage': {'network_mode': 'none', 'read_only': True, 'volumes': [
            {'type': 'bind', 'source': str(backups), 'target': '/backups', 'bind': {}}]}},
        'secrets': {'x_session_key': {'file': str(keys / 'x-session.key')}}}


class HostDockerTests(unittest.TestCase):
    def test_owner_rights_alias_is_private_but_everyone_is_rejected(self):
        if host.os.name != 'nt':
            self.assertIn("$actual.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -eq $user.Value", host.ACL_SCRIPT)
            return
        with tempfile.TemporaryDirectory(prefix='ssdl-owner-acl-') as directory:
            root = Path(directory)
            native = Path(host.os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0'
            script = r'''
$acl=[System.Security.AccessControl.DirectorySecurity]::new()
# This case exercises the current-owner alias, so establish that owner explicitly.
$acl.SetOwner([System.Security.Principal.WindowsIdentity]::GetCurrent().User)
$acl.SetAccessRuleProtection($true,$false)
$ids=@('S-1-3-4','S-1-5-18','S-1-5-32-544')
if($env:SSDL_TEST_WORLD -eq '1'){$ids+='S-1-1-0'}
foreach($id in $ids){
 $sid=[System.Security.Principal.SecurityIdentifier]::new($id)
 $acl.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
}
[System.IO.Directory]::SetAccessControl($env:SSDL_TEST_PATH,$acl)
'''
            for world in ('0', '1'):
                result = host.subprocess.run([str(native / 'powershell.exe'), '-NoProfile', '-NonInteractive', '-Command', script],
                    env=dict(host.os.environ, SSDL_TEST_PATH=str(root), SSDL_TEST_WORLD=world,
                             PSModulePath=str(native / 'Modules')), capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, 'Synthetic ACL setup failed')
                if world == '0':
                    host.host_acl(root, root=True)
                else:
                    with self.assertRaisesRegex(gate.GateError, 'private_host_acl_failed'):
                        host.host_acl(root, root=True)

    def test_host_flag_includes_all_three_optional_gates(self):
        from tools import docker_service_acceptance, docker_interaction_acceptance
        calls = Mock()
        with tempfile.TemporaryDirectory() as directory:
            def run(docker, root, report, *, service_gate):
                service_gate(docker, 'fixture', 'a' * 32, root, report)
                return dict(report, passed=True, complete=True)
            with patch.object(docker_service_acceptance, 'run_checks', calls.service), \
                 patch.object(docker_interaction_acceptance, 'run_checks', calls.interaction), \
                 patch.object(host, 'run_checks', calls.host), patch.object(gate, 'run_gate', side_effect=run), \
                 patch('sys.stdout', new_callable=io.StringIO):
                self.assertEqual(gate.main(['--host-storage', '--docker', 'fixture-docker', '--report',
                                            str(Path(directory) / 'receipt.json')]), 0)
        self.assertEqual([item[0] for item in calls.mock_calls], ['service', 'interaction', 'host'])

    def test_private_directory_permissions_on_current_host(self):
        with tempfile.TemporaryDirectory(prefix='ssdl-host-acl-') as directory:
            root = Path(directory)
            if host.os.name == 'nt':
                host.host_acl(root, create=True, root=True)
                child = root / 'private-child'
                child.mkdir()
                media = child / 'invented.txt'
                media.write_text('invented')
                host.host_acl(root, root=True)
                host.host_acl(child)
                host.host_acl(media)
            else:
                self.assertEqual(root.stat().st_mode & 0o777, 0o700)
                self.assertEqual(root.stat().st_uid, host.os.getuid())

    def fixtures(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        fixtures = Fixtures(ServiceDocker(), 'fixture-image', 'a' * 32, gate.ROOT, Path(temporary))
        self.enterContext(patch.object(host, 'host_acl'))
        return fixtures, host.HostFixtures(fixtures)

    def test_contract_retains_actual_host_paths_and_rejects_unsafe_changes(self):
        keys, backups = Path('/fixture/keys'), Path('/fixture/backups')
        original = model(keys, backups)
        host.bind_contract(original, keys, backups)
        for change in ('auto-create', 'volume', 'wrong-source', 'network', 'secret'):
            value = deepcopy(original)
            if change == 'auto-create': value['services']['storage']['volumes'][0]['bind']['create_host_path'] = True
            if change == 'volume': value['services']['storage']['volumes'][0]['type'] = 'volume'
            if change == 'wrong-source': value['services']['storage']['volumes'][0]['source'] = '/different'
            if change == 'network': value['services']['session-key']['network_mode'] = 'host'
            if change == 'secret': value['secrets']['x_session_key']['file'] = '/different/key'
            with self.subTest(change=change), self.assertRaises(gate.GateError):
                host.bind_contract(value, keys, backups)

    def test_paths_reject_traversal_absolute_names_and_mount_separator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.assertEqual(host.host_path(root, 'private-keys'), root / 'private-keys')
            for name in ('../other', '/absolute', 'a,b', '', 'nested/path'):
                with self.subTest(name=name), self.assertRaises(gate.GateError):
                    host.host_path(root, name)

    def test_helper_refuses_foreign_volumes_before_running_docker(self):
        fixtures, fixture = self.fixtures()
        before = list(fixtures.docker.calls)
        with self.assertRaisesRegex(gate.GateError, 'foreign_fixture_mount'):
            fixture.start_helper({'data': 'unrelated', 'cache': 'another', 'media': 'foreign'})
        self.assertEqual(fixtures.docker.calls, before)
        self.assertIsNone(fixture.helper)

    def test_actual_bind_and_file_secret_are_retained_in_fixture_project(self):
        fixtures, fixture = self.fixtures()
        group = fixtures.group('host')
        project = {'path': fixtures.directory / 'project.json', 'name': fixtures.prefix + '-source', 'port': 8876}
        project['path'].write_text(json.dumps({'services': {'downloader': {'environment': {}, 'volumes': []}}, 'volumes': {}}))
        original = model(fixture.keys, fixture.backups)
        with patch.object(fixtures, 'project', return_value=project), patch.object(fixture, 'model', return_value=original):
            fixture.project(group, 8876, 'source')
        config = json.loads(project['path'].read_text())
        self.assertEqual(config['services']['storage']['volumes'][0]['source'], str(fixture.backups))
        self.assertEqual(config['secrets']['x_session_key']['file'], str(fixture.keys / 'x-session.key'))
        self.assertNotIn('/run/secrets', {mount.get('target') for mount in config['services']['downloader']['volumes']})
        self.assertIn(config['services']['downloader']['container_name'], fixtures.containers)

    def test_acl_errors_are_redacted_and_path_is_passed_as_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private path'
            with patch.object(host.subprocess, 'run') as run:
                run.return_value.returncode = 1
                with self.assertRaisesRegex(gate.GateError, '^private_host_acl_failed$'):
                    host.host_acl(path, create=True, root=True)
                args, options = run.call_args
                self.assertNotIn(str(path), ' '.join(args[0]))
                self.assertEqual(options['env']['SSDL_ACCEPTANCE_ACL_PATH'], str(path))
                self.assertEqual(options['env']['SSDL_ACCEPTANCE_ACL_SET'], '1')
                self.assertEqual(options['env']['PSModulePath'], str(Path(host.os.environ.get('SystemRoot', 'C:/Windows')) /
                                                                    'System32/WindowsPowerShell/v1.0/Modules'))

    def test_probe_receipt_cannot_be_reused_from_another_fixture(self):
        fixtures, fixture = self.fixtures()
        with patch.object(fixtures, 'state'), patch.object(fixtures.docker, 'run',
                return_value=(0, json.dumps({'receipt': 'b' * 32, 'result': {}}))):
            with self.assertRaisesRegex(gate.GateError, 'invalid_host_receipt'):
                fixture.action('key-info', container='invented')

    def test_distribution_includes_host_tools_but_runtime_excludes_them(self):
        from tools.package_source import source_files
        names = {path.relative_to(gate.ROOT).as_posix() for path in source_files(gate.ROOT)}
        self.assertTrue({'tools/docker_host_acceptance.py', 'tools/docker_host_probe.py', 'tests/test_docker_host.py'} <= names)
        self.assertFalse(any('host_acceptance' in name or 'host_probe' in name for name in gate.runtime_sources(gate.ROOT)))


if __name__ == '__main__':
    unittest.main()
