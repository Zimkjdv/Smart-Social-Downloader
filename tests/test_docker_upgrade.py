"""Upgrade-gate boundaries. Fake Docker results are not runtime evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_docker as gate
from tools import docker_upgrade_acceptance as upgrade
from tools.docker_service_acceptance import Fixtures
from tests.helpers.docker import ServiceDocker
from tests.test_docker_service import compose_model


class DockerUpgradeTests(unittest.TestCase):
    def test_version_is_a_bounded_literal_and_never_executes_source(self):
        self.assertEqual(upgrade.version({"ssdl/version.py": b'__version__ = "0.1.0-preview.2"'}), "0.1.0-preview.2")
        for source in (b'__version__ = str(1)', b'__version__ = True', b'__version__ = "https://private.invalid"',
                       b'__version__ = "1"\n__version__ = "2"', b'APP_NAME = "missing"'):
            with self.subTest(source=source), self.assertRaises((gate.GateError, ValueError)):
                upgrade.version({"ssdl/version.py": source})

    def test_retag_or_label_only_changes_cannot_count_as_application_upgrade(self):
        files = gate.runtime_sources(gate.ROOT)
        for name in ("Dockerfile", ".dockerignore", "LICENSE", "THIRD_PARTY_NOTICES.md"):
            self.assertEqual(upgrade.application_fingerprint(files),
                             upgrade.application_fingerprint({**files, name: files[name] + b"\nchanged\n"}))
        self.assertNotEqual(upgrade.application_fingerprint(files),
                            upgrade.application_fingerprint({**files, "app.py": b"different source\n"}))

    def test_identical_source_and_changed_candidate_fail_before_docker_resources(self):
        docker = ServiceDocker()
        for source_hash, error in ((gate.fingerprint(gate.runtime_sources(gate.ROOT)), "upgrade_source_unchanged"),
                                   ("0" * 64, "candidate_source_changed")):
            with self.assertRaisesRegex(gate.GateError, error):
                upgrade.run_checks(docker, "candidate", "a" * 32, gate.ROOT,
                                   {"source_sha256": source_hash}, baseline_root=gate.ROOT)
        self.assertEqual(docker.calls, [])

    def test_remote_engine_rejected_before_source_or_resource_operations(self):
        docker = ServiceDocker()
        docker.prefix = ["docker", "--host", "tcp://remote.invalid:2375"]
        with self.assertRaisesRegex(gate.GateError, "local_engine_required"):
            upgrade.run_checks(docker, "candidate", "a" * 32, gate.ROOT, {}, baseline_root=gate.ROOT)
        self.assertEqual(docker.calls, [])

    def test_encrypted_projects_keep_shared_key_readonly_and_rollback_volumes_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            fixtures = Fixtures(ServiceDocker(), "baseline", "a" * 32, gate.ROOT, Path(directory))
            original, recovered = fixtures.group("original"), fixtures.group("recovered")
            backups, keys = fixtures.volume("backups"), fixtures.volume("keys")
            with patch.object(fixtures, "model", return_value=compose_model(19876)):
                old = upgrade.encrypted_project(fixtures, original, backups, keys, 19876, "candidate", "candidate")
                new = upgrade.encrypted_project(fixtures, recovered, backups, keys, 19876, "rollback", "baseline")
            old_model, new_model = (json.loads(project["path"].read_text()) for project in (old, new))
            self.assertNotEqual(old_model["volumes"]["app-data"], new_model["volumes"]["app-data"])
            self.assertNotEqual(old_model["volumes"]["media"], new_model["volumes"]["media"])
            self.assertEqual(old_model["volumes"]["session-keys"], new_model["volumes"]["session-keys"])
            self.assertEqual(new_model["services"]["downloader"]["image"], "baseline")
            self.assertTrue(new_model["services"]["downloader"]["volumes"][-1]["read_only"])
            with self.assertRaisesRegex(gate.GateError, "foreign_fixture_mount"):
                upgrade.encrypted_project(fixtures, original, backups, "foreign", 19876, "unsafe", "candidate")

    def test_fixture_rejects_foreign_receipt_wrong_exit_and_unexpected_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            fixtures = Fixtures(ServiceDocker(), "baseline", "a" * 32, gate.ROOT, Path(directory))
            for code, value in ((0, {"receipt": "foreign", "result": {}}),
                                (1, {"receipt": fixtures.receipt, "result": {}}),
                                (0, {"receipt": fixtures.receipt, "result": {}, "extra": "unexpected"})):
                with patch.object(fixtures.docker, "run", return_value=(code, json.dumps(value))), self.assertRaises(gate.GateError):
                    upgrade.action(fixtures, b"fixture", "container", "session-info")

    def test_new_tool_is_shipped_only_in_source_archive(self):
        from tools.package_source import source_files
        names = {path.relative_to(gate.ROOT).as_posix() for path in source_files(gate.ROOT)}
        self.assertIn("tools/docker_upgrade_acceptance.py", names)
        self.assertNotIn("tools/docker_upgrade_acceptance.py", gate.runtime_sources(gate.ROOT))
