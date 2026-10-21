"""Interaction gate contracts; the real container receipt is separate evidence."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_docker as gate
from tools import docker_interaction_acceptance as interaction
from tools.docker_service_acceptance import Fixtures
from tests.helpers.docker import ServiceDocker


class DockerInteractionTests(unittest.TestCase):
    def test_secret_contract_accepts_both_compose_target_shapes_and_rejects_exposure(self):
        model = {"services": {"downloader": {"environment": {"SSDL_X_KEY_FILE": "/run/secrets/x_session_key"},
                 "secrets": [{"source": "x_session_key", "target": "x_session_key"}]}, "storage": {}, "session-key": {}}}
        interaction.login_contract(model)
        model["services"]["downloader"]["secrets"][0]["target"] = "/run/secrets/x_session_key"
        interaction.login_contract(model)
        model["services"]["storage"]["secrets"] = ["x_session_key"]
        with self.assertRaises(gate.GateError):
            interaction.login_contract(model)
        model["services"]["storage"] = {}
        model["services"]["downloader"]["secrets"][0]["target"] = "/downloads/key"
        with self.assertRaises(gate.GateError):
            interaction.login_contract(model)

    def test_interaction_sources_ship_in_source_archive_only(self):
        from tools.package_source import source_files
        names = {path.relative_to(gate.ROOT).as_posix() for path in source_files(gate.ROOT)}
        self.assertTrue({"tools/docker_interaction_acceptance.py", "tools/docker_interaction_probe.py",
                         "tests/test_docker_interaction.py"} <= names)
        self.assertFalse(any("interaction" in path for path in gate.runtime_sources(gate.ROOT)))

    def test_key_helpers_reject_foreign_mounts_and_keep_network_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixtures(ServiceDocker(), "fixture", "a" * 32, gate.ROOT, Path(directory))
            with self.assertRaisesRegex(gate.GateError, "foreign_fixture_mount"):
                fixture.helper({}, keys="unrelated")
            keys = fixture.volume("keys")
            fixture.helper({}, keys=keys, root=True)
            args = fixture.docker.calls[-1][0]
            self.assertIn("type=volume,source=" + keys + ",target=/keys", args)
            self.assertEqual(args[args.index("--network") + 1], "none")
            self.assertNotIn("--privileged", args)

    def test_pairing_url_requires_exact_loopback_destination_and_fragment(self):
        project = {"port": 8876}
        for url in ("http://127.0.0.1:8876/chrome-connect?token=private",
                    "https://untrusted.invalid/chrome-connect#token=" + "a" * 43,
                    "http://127.0.0.1:8765/chrome-connect#token=" + "a" * 43):
            with patch.object(interaction, "json_request", return_value=(202, {"pairing_url": url})), self.assertRaises(gate.GateError):
                interaction.token(project)
        url = "http://127.0.0.1:8876/chrome-connect#token=" + "a" * 43 + "&connect=1"
        with patch.object(interaction, "json_request", return_value=(202, {"pairing_url": url})):
            self.assertEqual(interaction.token(project), "a" * 43)

    def test_summary_must_not_expose_cookie_value(self):
        value = {"x_auth": {"connected": True, "phase": "connected"}, "unexpected": "ssdl-invented-session"}
        with patch.object(interaction, "json_request", return_value=(200, value)), self.assertRaisesRegex(gate.GateError, "unexpected_session_state"):
            interaction.status({}, True)

    def test_interaction_stage_failure_keeps_categorical_receipt_and_cleans_resources(self):
        docker = ServiceDocker()
        report = {}
        with patch.object(interaction.Fixtures, "cleanup") as cleanup:
            with self.assertRaises((gate.GateError, ValueError)):
                interaction.run_checks(docker, "fixture", "a" * 32, gate.ROOT, report)
        cleanup.assert_called_once()
        self.assertEqual(report["interaction_checks"], [])
        self.assertEqual(report["interaction_error"], "login_override_contract_failed")


if __name__ == "__main__":
    unittest.main()
