"""Docker gate contracts. Fake commands are never container acceptance evidence."""
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from tools import check_docker as gate
from tests.helpers.docker import FakeDocker, VERSIONS, DOCKERFILE


class DockerGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ssdl-docker-contract-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in gate.ROOT_INPUTS:
            (self.root / name).write_bytes(DOCKERFILE if name == "Dockerfile" else b"public fixture\n")
        for folder, patterns in gate.INPUTS.items():
            (self.root / folder).mkdir()
            for pattern in patterns:
                path = self.root / folder / pattern.replace("*", "fixture")
                path.write_bytes(b"public fixture\n")
        (self.root / "tools").mkdir()
        (self.root / "tools/docker_runtime_probe.py").write_bytes(b"synthetic probe\n")

    def report(self):
        return {"schema": 1, "complete": False, "passed": False, "checks": []}

    def test_source_selection_never_traverses_private_trees(self):
        before = gate.runtime_sources(self.root)
        for name in ("data/state.json", "downloads/movie.mp4", ".venv/private", ".git/config",
                     ".secrets/x-session.key", "ssdl/data/private.py", "ssdl/nested/secret.py"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic private value")
        self.assertEqual(gate.runtime_sources(self.root), before)
        stage = self.root / "staged"
        stage.mkdir()
        gate.stage_sources(before, stage, "synthetic-marker")
        self.assertEqual((stage / "data/history.json").read_text(), "synthetic-marker")
        self.assertFalse((stage / "data/state.json").exists())
        audit = gate.audit_dockerfile(DOCKERFILE, before, gate.base_versions(DOCKERFILE)["python_image"])
        self.assertNotIn(b"synthetic-marker", audit)
        self.assertIn(b"AS ssdl_context_audit", audit)
        self.assertEqual(len(gate.fingerprint(before)), 64)
        self.assertNotEqual(gate.fingerprint(before), gate.fingerprint({**before, "app.py": b"changed"}))

    def test_private_content_and_reparse_source_paths_are_rejected(self):
        target = self.root / "app.py"
        target.write_bytes(b"# Netscape HTTP Cookie File\n")
        with self.assertRaisesRegex(gate.GateError, "private_source_content"):
            gate.runtime_sources(self.root)
        target.write_bytes(b"public\n")
        original = Path.lstat
        def metadata(path, *args, **kwargs):
            if path == self.root / "ssdl":
                from types import SimpleNamespace
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", metadata):
            with self.assertRaisesRegex(gate.GateError, "unsafe_source"):
                gate.runtime_sources(self.root)

    def test_context_audit_program_rejects_any_extra_file(self):
        files = gate.runtime_sources(self.root)
        context = self.root / "context"
        for name, contents in files.items():
            path = context / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        audit = gate.audit_dockerfile(DOCKERFILE, files, gate.base_versions(DOCKERFILE)["python_image"])
        instruction = next(line for line in audit.decode().splitlines() if line.startswith("RUN "))
        program = json.loads(instruction[4:])[2].replace("'/context'", repr(str(context)))
        exec(compile(program, "synthetic-context-audit", "exec"), {})
        (context / ".env").write_text("synthetic private fixture", encoding="ascii")
        with self.assertRaises(AssertionError):
            exec(compile(program, "synthetic-context-audit", "exec"), {})

    def test_mutable_base_or_unnamed_final_stage_is_rejected(self):
        self.assertEqual(gate.base_versions(DOCKERFILE)["python"], "3.12.15")
        for content in (DOCKERFILE.replace(b" AS runtime", b""), DOCKERFILE.replace(b"@sha256:", b"@other:")):
            with self.assertRaisesRegex(gate.GateError, "unreviewed_base"):
                gate.base_versions(content)

    def test_probe_receipt_requires_complete_order_identity_and_bounded_versions(self):
        receipt = "0" * 32
        valid = {"format_version": 1, "receipt": receipt, "passed": True,
                 "checks": list(gate.CHECKS), "versions": VERSIONS.copy()}
        self.assertTrue(gate.validate_probe(json.dumps(valid), receipt, VERSIONS)["passed"])
        mutations = ({"receipt": "1" * 32}, {"checks": list(reversed(gate.CHECKS))},
                     {"checks": list(gate.CHECKS[:-1])}, {"passed": 1}, {"format_version": True},
                     {"private": "do not export"}, {"versions": {**VERSIONS, "node": "22.1.0"}},
                     {"versions": {**VERSIONS, "ffmpeg": "https://private.example/secret"}})
        for mutation in mutations:
            with self.subTest(fields=list(mutation)), self.assertRaises(gate.GateError):
                gate.validate_probe(json.dumps({**valid, **mutation}), receipt, VERSIONS)

    def test_fake_engine_response_and_timeouts_fail_without_skips(self):
        for failure, expected in (("engine", "engine_failed"), ("build", "context_failed"),
                                  ("runtime", "runtime_failed"), ("timeout", "runtime_failed")):
            with self.subTest(failure=failure):
                docker = FakeDocker(fail=failure)
                report = gate.run_gate(docker, self.root, self.report())
                self.assertFalse(report["passed"])
                self.assertFalse(report["complete"])
                self.assertEqual(report["code"], expected)
                if failure == "runtime":
                    self.assertEqual(report["probe_error"], "dependencies_failed")

    def test_command_contract_uses_fresh_image_no_volumes_and_network_disabled(self):
        docker = FakeDocker()
        report = gate.run_gate(docker, self.root, self.report())
        self.assertTrue(report["passed"])
        self.assertEqual(report["checks"], ["context_allowlist", "image_build", *gate.CHECKS])
        arguments, options = next(call for call in docker.calls if call[0][0] == "run")
        self.assertEqual(arguments[arguments.index("--network") + 1], "none")
        self.assertIn("--read-only", arguments)
        self.assertNotIn("--mount", arguments)
        self.assertNotIn("--volume", arguments)
        self.assertEqual(options["data"], b"synthetic probe\n")
        self.assertEqual(options["timeout"], 240)
        builds = [args for args, _ in docker.calls if args[0] == "build"]
        self.assertEqual([args[args.index("--target") + 1] for args in builds], ["ssdl_context_audit", "runtime"])
        self.assertFalse(any("prune" in args for args, _ in docker.calls))

    def test_cleanup_refuses_foreign_container_and_removes_only_owned_name(self):
        docker = FakeDocker(fail="ownership")
        report = gate.run_gate(docker, self.root, self.report())
        self.assertEqual(report["code"], "cleanup_failed")
        self.assertFalse(report["passed"])
        self.assertFalse(any(args[:2] == ["container", "rm"] for args, _ in docker.calls))
        docker = FakeDocker(fail="timeout")
        gate.run_gate(docker, self.root, self.report())
        removed = [args[-1] for args, _ in docker.calls if args[:2] == ["container", "rm"]]
        self.assertEqual(removed, ["ssdl-acceptance-" + docker.receipt])

    def test_cli_replaces_stale_success_and_does_not_publish_raw_errors(self):
        target = self.root / "receipt.json"
        target.write_text('{"passed":true}', encoding="utf-8")
        def failed(docker, root, report):
            self.assertFalse(json.loads(target.read_text())["passed"])
            return {**report, "code": "engine_failed"}
        with patch.object(gate, "run_gate", side_effect=failed), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(gate.main(["--report", str(target)]), 1)
        self.assertFalse(json.loads(target.read_text())["passed"])
        self.assertIn("engine_failed", output.getvalue())
        with patch.object(gate, "run_gate", side_effect=KeyboardInterrupt), patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(gate.main(["--report", str(target)]), 130)
        self.assertFalse(json.loads(target.read_text())["complete"])
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_new_tools_ship_as_source_but_are_not_runtime_inputs(self):
        from tools.package_source import source_files
        selected = {path.relative_to(gate.ROOT).as_posix() for path in source_files(gate.ROOT)}
        self.assertTrue({"tools/check_docker.py", "tools/docker_runtime_probe.py", "tests/test_docker_gate.py"} <= selected)
        runtime = gate.runtime_sources(gate.ROOT)
        self.assertNotIn("tools/docker_runtime_probe.py", runtime)
        self.assertNotIn("tests/test_docker_gate.py", runtime)


if __name__ == "__main__":
    unittest.main()
