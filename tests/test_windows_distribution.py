"""Installed paths, shared preferences and reversible import at public seams."""
from contextlib import closing
import json
import io
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from ssdl import runtime_paths as runtime
from ssdl import data_migration as migration
from ssdl.ui_preferences import UIPreferences


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()

    def test_installed_resources_are_separate_and_data_scope_ignores_executable_location(self):
        with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, {'LOCALAPPDATA':str(self.root)}):
            with patch.dict(os.environ):
                os.environ.pop('SSDL_HOME', None)
                a = runtime.paths()
                with patch.object(sys, 'executable', str(self.root / 'other/app.exe')):
                    b = runtime.paths()
                self.assertEqual(a.home, b.home)
                self.assertNotEqual(a.resources, a.home)
                self.assertEqual(a.profile, a.home / 'cache/webview2')
                from ssdl.desktop_control import scope_key
                self.assertEqual(scope_key(a.home), scope_key(b.home))

    def test_source_defaults_and_explicit_home_validation(self):
        with patch.dict(os.environ):
            os.environ.pop('SSDL_HOME', None)
            self.assertEqual(runtime.paths().home, runtime.paths().resources)
            for value in ('', 'relative'):
                os.environ['SSDL_HOME'] = value
                with self.assertRaises(RuntimeError): runtime.paths()

    def test_frozen_commands_have_only_registered_roles_not_python_switches(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(self.root / 'gui.exe')):
            for module, role in runtime._ROLES.items():
                command = runtime.module_command(module, 'fixture')
                self.assertEqual(command, [str(self.root / 'ssdl-runtime.exe'), '--role', role, 'fixture'])
            with self.assertRaises(ValueError): runtime.module_command('arbitrary.module')

    def test_source_child_uses_reviewed_code_when_home_is_outside_checkout(self):
        env = {key:value for key,value in os.environ.items() if key not in {'PYTHONPATH','PYTHONHOME'}}
        env['SSDL_HOME'] = str(self.root)
        with patch.dict(os.environ, env, clear=True):
            command = runtime.module_command('ssdl.pixiv_auth_exchange')
        result = subprocess.run(command, cwd=self.root, env=env, input=b'{"grant":"invalid"}',
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), {'error':'pixiv_auth_failed'})

    def test_installed_home_cannot_be_inside_executable_resources(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(self.root/'app/gui.exe')):
            with patch.dict(os.environ, {'SSDL_HOME':str(self.root/'app/private data')}):
                with self.assertRaises(RuntimeError): runtime.paths()

    def test_runtime_pipe_json_is_utf8_even_with_a_legacy_windows_stream(self):
        from ssdl.runtime_entry import main
        raw=io.BytesIO();stream=io.TextIOWrapper(raw,encoding='cp950')
        with patch.object(runtime,'paths',return_value=SimpleNamespace(home=self.root)), \
             patch('ssdl.environment.inspect_environment',return_value={'detail':'中文資料夾'}), \
             patch.object(sys,'stdout',stream):
            self.assertEqual(main(['--role','diagnose']),0)
        stream.flush()
        self.assertEqual(json.loads(raw.getvalue().decode('utf-8')),{'detail':'中文資料夾'})

    @unittest.skipUnless(os.name == 'nt','Windows data-scope writer lease')
    def test_foreground_writer_lease_also_blocks_migration(self):
        from ssdl.data_access import writer_lease
        source=self._source('foreground');home=self._source('destination')
        errors=[]
        with writer_lease(source):
            def attempt():
                try:migration.migrate(source,home)
                except Exception as error:errors.append(error)
            thread=threading.Thread(target=attempt);thread.start();thread.join(10)
            self.assertFalse(thread.is_alive());self.assertIsInstance(errors[0],RuntimeError)

    @unittest.skipUnless(os.name == 'nt','Windows migration recovery')
    def test_interrupted_directory_swap_can_restore_prepared_backup(self):
        home=self._source('interrupted');before=(home/'data/state.json').read_bytes()
        identifier='a'*32;backup=home/'data-backups'/identifier;backup.mkdir(parents=True)
        (home/'data').replace(backup/'data')
        (backup/'migration.json').write_text(json.dumps({'schema':1,'id':identifier,'phase':'prepared','before_exists':True}))
        migration.rollback(identifier,home)
        self.assertEqual((home/'data/state.json').read_bytes(),before)

    def test_preferences_roundtrip_rejects_future_schema_and_preserves_original_on_write_error(self):
        store = UIPreferences(self.root / 'data/ui-preferences.json')
        self.assertIsNone(store.read())
        before = {'schema':1, 'language':'en', 'page_size':50}
        store.save(before)
        with patch.object(Path, 'replace', side_effect=PermissionError):
            with self.assertRaises(PermissionError): store.save({**before,'page_size':10})
        self.assertEqual(store.read(), before)
        for bad in ({**before,'schema':2},{**before,'page_size':True},{**before,'extra':1}):
            with self.assertRaises(ValueError): store.save(bad)

    def test_data_scope_serves_resources_and_real_preference_http_with_origin_refusal(self):
        import http.client
        from ssdl.app import create_app, Server
        from ssdl.runtime_paths import paths
        with create_app(self.root, resources=paths().resources) as app:
            with Server(('127.0.0.1',0),app.Handler) as server:
                app.PORT = server.server_port
                thread = threading.Thread(target=server.serve_forever);thread.start()
                def request(method,path,data=None,headers=None):
                    connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
                    connection.request(method,path,json.dumps(data) if data is not None else None, headers or {})
                    reply=connection.getresponse();value=reply.read();connection.close();return reply.status,value
                try:
                    self.assertEqual(request('GET','/')[0],200)
                    prefs={'schema':1,'language':'en','page_size':10}
                    self.assertEqual(request('POST','/api/ui-preferences',prefs)[0],200)
                    self.assertEqual(json.loads(request('GET','/api/ui-preferences')[1])['preferences'],prefs)
                    self.assertEqual(request('POST','/api/ui-preferences',prefs,{'Origin':'https://example.org'})[0],403)
                    self.assertEqual(request('POST','/api/ui-preferences',{**prefs,'page_size':15})[0],400)
                finally:
                    server.shutdown();thread.join()

    def _source(self, name):
        root = self.root / name; data = root / 'data'; data.mkdir(parents=True)
        (data/'state.json').write_text(json.dumps({'schema_version':2,'jobs':[], 'download_dir':str(root/'original media')}))
        with closing(sqlite3.connect(data/'media-manifest.sqlite3')) as db:
            db.execute('CREATE TABLE fixture(value TEXT)');db.execute("INSERT INTO fixture VALUES ('original')");db.commit()
        return root

    @unittest.skipUnless(os.name == 'nt','Windows migration uses native ownership locks')
    def test_import_and_rollback_preserve_source_databases_media_and_newer_target(self):
        source=self._source('old source 圖片');home=self._source('installed data')
        from ssdl.session_storage import SessionStorage
        from ssdl.x_auth import _dpapi
        # A valid encrypted session may exceed 16 KiB but remain below its store's bound.
        SessionStorage(windows_protect=_dpapi).save(source/'data/x-auth.bin', b'synthetic payload' * 1500)
        encrypted = (source/'data/x-auth.bin').read_bytes()
        original=(source/'data/state.json').read_bytes();before=(home/'data/state.json').read_bytes()
        (source/'original media').mkdir();(source/'original media/original.bin').write_bytes(b'original')
        result=migration.migrate(source,home)
        self.assertEqual((source/'data/state.json').read_bytes(),original)
        self.assertEqual((home/'data/state.json').read_bytes(),original)
        self.assertEqual((home/'data/x-auth.bin').read_bytes(), encrypted)
        with closing(sqlite3.connect(home/'data/media-manifest.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT value FROM fixture').fetchone(),('original',))
        (home/'data/newer.txt').write_text('new after import')
        migration.rollback(result['backup'],home)
        self.assertEqual((home/'data/state.json').read_bytes(),before)
        self.assertEqual((home/'data-backups'/result['backup']/'after-data/newer.txt').read_text(),'new after import')
        self.assertEqual((source/'original media/original.bin').read_bytes(),b'original')
        with self.assertRaises(ValueError): migration.rollback(result['backup'],home)

    @unittest.skipUnless(os.name == 'nt','Windows migration uses native ownership locks')
    def test_failed_import_restores_target_and_rejects_newer_or_changing_source(self):
        source=self._source('source');home=self._source('target')
        before=(home/'data/state.json').read_bytes()
        replace=Path.replace
        def fail_install(path,target):
            if path.name.startswith('.import-'): raise PermissionError('fixture')
            return replace(path,target)
        with patch.object(Path,'replace',fail_install),self.assertRaises(PermissionError): migration.migrate(source,home)
        self.assertEqual((home/'data/state.json').read_bytes(),before)
        (source/'data/state.json').write_text('{"schema_version":999,"jobs":[]}')
        with self.assertRaises(ValueError): migration.migrate(source,home)
        self.assertEqual((home/'data/state.json').read_bytes(),before)

    @unittest.skipUnless(os.name == 'nt','Windows migration uses native ownership locks')
    def test_running_data_scope_refuses_import_without_touching_target(self):
        source=self._source('source');home=self._source('target')
        from ssdl.desktop_service import Controls
        controls=Controls(source)
        mutex=controls.keep(controls.api.CreateMutexW(None,False,controls.prefix+'owner'))
        # Mutexes are recursive for the owning thread: another thread must probe.
        self.assertIn(controls.api.WaitForSingleObject(mutex,0),(0,0x80))
        errors=[]
        def attempt():
            try:migration.migrate(source,home)
            except Exception as error:errors.append(error)
        try:
            thread=threading.Thread(target=attempt);thread.start();thread.join(10)
            self.assertFalse(thread.is_alive());self.assertIsInstance(errors[0],RuntimeError)
        finally:
            controls.api.ReleaseMutex(mutex);controls.close()


if __name__=='__main__':unittest.main()
