"""Service-gate contracts; fake CLI results do not prove container execution."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_docker as gate
from tools import docker_service_acceptance as service
from tests.helpers.docker import FakeDocker, ServiceDocker


def compose_model(port=8765):
    return {"services": {
        "downloader": {"image": "fixture-image", "build": {"context": "."}, "read_only": True, "init": True,
                       "environment": {"SSDL_PORT": str(port), "SSDL_DOWNLOAD_DIR": "/downloads", "SSDL_CACHE_DIR": "/app/cache"},
                       "ports": [{"host_ip": "127.0.0.1", "target": port, "published": str(port)}],
                       "volumes": [{"type": "volume", "source": source, "target": target} for source, target in
                                   (("app-data", "/app/data"), ("cache", "/app/cache"), ("media", "/downloads"))]},
        "storage": {"network_mode": "none", "read_only": True, "entrypoint": ["python", "-u", "docker/storage.py"],
                    "volumes": [{"type": "bind", "source": "invented", "target": "/backups", "bind": {"create_host_path": False}}]}}}


class DockerServiceTests(unittest.TestCase):
    def fixtures(self, docker=None):
        temporary = tempfile.TemporaryDirectory(prefix="ssdl-service-contract-")
        self.addCleanup(temporary.cleanup)
        return service.Fixtures(docker or ServiceDocker(), "ssdl-runtime:fixture", "a" * 32,
                                gate.ROOT, Path(temporary.name))

    def test_compose_contract_rejects_wildcards_wrong_ports_and_host_path_creation(self):
        service.contract(compose_model(), 8765)
        for change in ("wildcard", "port", "mount", "read-only", "backup"):
            model = compose_model()
            if change == "wildcard": model["services"]["downloader"]["ports"][0]["host_ip"] = "0.0.0.0"
            if change == "port": model["services"]["downloader"]["ports"][0]["target"] = 8876
            if change == "mount": model["services"]["downloader"]["volumes"][0]["type"] = "bind"
            if change == "read-only": model["services"]["downloader"]["read_only"] = False
            if change == "backup": model["services"]["storage"]["volumes"][0]["bind"]["create_host_path"] = True
            with self.subTest(change=change), self.assertRaises(gate.GateError):
                service.contract(model, 8765)

    def test_compose_v2_omitted_false_bind_field_preserves_safe_contract(self):
        # Captured shape from official Compose 2.38.2: false is omitted in JSON.
        model = compose_model()
        del model["services"]["storage"]["volumes"][0]["bind"]["create_host_path"]
        service.contract(model, 8765)
        model["services"]["storage"]["volumes"][0]["bind"]["create_host_path"] = True
        with self.assertRaises(gate.GateError):
            service.contract(model, 8765)

    def test_fixture_projects_keep_three_external_volumes_and_matching_custom_port(self):
        fixtures = self.fixtures()
        group = fixtures.group("source")
        backups = fixtures.volume("backups")
        original = compose_model(19876)
        with patch.object(fixtures, "model", return_value=original):
            project = fixtures.project(group, backups, 19876)
        config = json.loads(project["path"].read_text())
        app = config["services"]["downloader"]
        self.assertNotIn("build", app)
        self.assertEqual(app["image"], "ssdl-runtime:fixture")
        self.assertEqual(app["ports"][0]["published"], "19876")
        self.assertEqual(app["environment"]["SSDL_PORT"], "19876")
        self.assertEqual(app["labels"]["ssdl.acceptance"], "a" * 32)
        self.assertTrue(all(item["external"] for item in config["volumes"].values()))
        self.assertEqual(config["volumes"]["app-data"]["name"], group["data"])
        self.assertEqual(original, compose_model(19876))

    def test_foreign_volume_label_is_rejected_before_mount_and_cleanup(self):
        fixtures = self.fixtures(ServiceDocker(receipt="b" * 32))
        with self.assertRaisesRegex(gate.GateError, "foreign_fixture_volume"):
            fixtures.volume("collision")
        self.assertEqual(fixtures.volumes, [])
        with self.assertRaisesRegex(gate.GateError, "foreign_fixture_mount"):
            fixtures.helper({"data": "another-installation"})
        self.assertFalse(any(args[0] == "run" for args, _ in fixtures.docker.calls))

    def test_helpers_use_only_receipt_owned_mounts_and_no_network(self):
        fixtures = self.fixtures()
        group, backup = fixtures.group("source"), fixtures.volume("backups")
        fixtures.helper(group, backup)
        arguments = next(args for args, _ in fixtures.docker.calls if args[0] == "run")
        self.assertEqual(arguments[arguments.index("--network") + 1], "none")
        self.assertIn("--read-only", arguments)
        self.assertIn("ssdl.acceptance=" + "a" * 32, arguments)
        self.assertNotIn("--privileged", arguments)
        self.assertNotIn("--user", arguments)

    def test_storage_receipts_reject_foreign_identity_and_wrong_exit(self):
        fixtures = self.fixtures()
        for response in ((0, '{"receipt":"foreign","result":{}}'), (1, '{"fixture_error":true}')):
            with patch.object(fixtures.docker, "run", return_value=response), self.assertRaises(gate.GateError):
                fixtures.probe_action("invented-helper", "verify")
        with patch.object(fixtures.docker, "run", return_value=(75, "")):
            self.assertIsNone(fixtures.probe_action("invented-helper", "interrupt-restore", "ssdl-fixture.tar", expected=75))

    def test_cleanup_never_removes_mismatched_resources(self):
        fixtures = self.fixtures(ServiceDocker(receipt="b" * 32))
        fixtures.volumes = ["invented-owned-name"]
        fixtures.networks = ["invented-network-name"]
        with self.assertRaisesRegex(gate.GateError, "service_cleanup_failed"):
            fixtures.cleanup()
        self.assertFalse(any(args[1:2] == ["rm"] for args, _ in fixtures.docker.calls))

    def test_compose_environment_excludes_ambient_installation_settings(self):
        with patch.dict("os.environ", {"SSDL_PORT": "1", "SSDL_X_KEY_FILE": "invented-private-key", "COMPOSE_FILE": "unrelated.yaml"}):
            fixtures = self.fixtures()
        self.assertFalse(any(key.startswith(("SSDL_", "COMPOSE_")) for key in fixtures.environment))
        fixtures.compose(fixtures.source, fixtures.prefix, ["config"])
        arguments, options = fixtures.docker.calls[-1]
        self.assertIn("--env-file", arguments)
        self.assertIn("-p", arguments)
        self.assertEqual(options["env"], fixtures.environment)
        self.assertNotIn("invented-private-key", json.dumps(arguments))

    def test_optional_service_failure_cannot_leave_successful_runtime_receipt(self):
        docker = FakeDocker()
        report = {"checks": [], "passed": False, "complete": False}
        def failed(*args):
            raise RuntimeError("private diagnostic must not escape")
        with patch("sys.stderr", new_callable=io.StringIO):
            result = gate.run_gate(docker, gate.ROOT, report, service_gate=failed)
        self.assertFalse(result["passed"])
        self.assertEqual(result["code"], "service_failed")
        self.assertNotIn("private diagnostic", json.dumps(result))

    def test_source_distribution_contains_service_helpers_but_runtime_does_not(self):
        from tools.package_source import source_files
        names = {path.relative_to(gate.ROOT).as_posix() for path in source_files(gate.ROOT)}
        self.assertTrue({"tools/docker_service_acceptance.py", "tools/docker_storage_probe.py", "tests/test_docker_service.py"} <= names)
        self.assertFalse(any(name.startswith("tools/") for name in gate.runtime_sources(gate.ROOT)))

    def test_remote_engine_is_rejected_before_creating_fixture_resources(self):
        docker = ServiceDocker()
        docker.prefix = ["docker", "--host", "tcp://remote.invalid:2375"]
        with self.assertRaisesRegex(gate.GateError, "local_engine_required"):
            service.run_checks(docker, "fixture", "a" * 32, gate.ROOT, {})
        self.assertEqual(docker.calls, [])


if __name__ == "__main__":
    unittest.main()
