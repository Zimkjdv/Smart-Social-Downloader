"""Offline regression for this repo's deliberately restricted Action syntax."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_workflows as policy
from tools.package_source import ROOT, source_files


class WorkflowPolicyTests(unittest.TestCase):
    def test_reviewed_actions_accept_full_sha_and_scalar_quotes(self):
        for action in sorted(policy.REVIEWED_ACTIONS):
            for quote in ("", "'", '"'):
                with self.subTest(action=action, quote=quote):
                    value = quote + action + "@" + "a" * 40 + quote
                    self.assertEqual(policy.check_text(f"  - uses: {value} # v7.0.1\n", "fixture.yml"), 1)

    def test_mutable_short_dynamic_docker_local_and_unreviewed_refs_fail(self):
        refs = ("actions/checkout@v7", "actions/checkout@main", "actions/checkout@abcdef1",
                "actions/checkout@${{ inputs.sha }}", "actions/checkout@" + "g" * 40,
                "unknown/action@" + "a" * 40, "./local-action", "docker://image:latest")
        for value in refs:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "fixture.yml:1:"):
                policy.check_text("- uses: " + value, "fixture.yml")

    def test_flow_multiline_and_alias_values_fail_closed(self):
        for line in ("- {uses: actions/checkout@v7}", "- uses: >\n    actions/checkout@v7",
                     "- uses: *action", "- uses: &action actions/checkout@v7"):
            with self.subTest(line=line), self.assertRaises(ValueError):
                policy.check_text(line, "fixture.yml")

    def test_comments_are_ignored_and_error_does_not_echo_ref(self):
        self.assertEqual(policy.check_text("# uses: action@main\nname: fixture\n", "fixture.yml"), 0)
        secret = "synthetic-private-value"
        with self.assertRaises(ValueError) as caught:
            policy.check_text("- uses: " + secret, "fixture.yml")
        self.assertNotIn(secret, str(caught.exception))

    def test_yaml_extensions_and_noncanonical_roots_are_checked(self):
        with tempfile.TemporaryDirectory(prefix="ssdl-workflows-") as temporary:
            root = Path(temporary).resolve()
            directory = root / ".github/workflows"
            directory.mkdir(parents=True)
            for extension in ("yml", "yaml"):
                (directory / ("fixture." + extension)).write_text(
                    "steps:\n  - uses: actions/checkout@" + "a" * 40, encoding="utf-8")
            self.assertEqual(policy.check_workflows(root / ".github" / ".."), (2, 2))

    def test_missing_workflows_and_cli_failures_are_reported(self):
        with tempfile.TemporaryDirectory(prefix="ssdl-workflows-") as temporary:
            with self.assertRaisesRegex(ValueError, "No workflow"):
                policy.check_workflows(Path(temporary))
        with patch.object(policy, "check_workflows", side_effect=ValueError("fixture error")), \
             patch("builtins.print") as output:
            self.assertEqual(policy.main(), 1)
        self.assertIn("fixture error", output.call_args.args[0])

    def test_current_workflows_and_update_configuration_are_shipped(self):
        self.assertEqual(policy.check_workflows(ROOT), (2, 15))
        selected = {path.relative_to(ROOT).as_posix() for path in source_files(ROOT)}
        self.assertTrue({".github/dependabot.yml", "tools/check_workflows.py",
                         "tests/test_workflow_policy.py"}.issubset(selected))
        workflow = (ROOT / ".github/workflows/checks.yml").read_text(encoding="utf-8")
        self.assertIn("run: python tools/check_workflows.py", workflow)
