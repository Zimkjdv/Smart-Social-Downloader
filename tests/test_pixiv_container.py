"""Categorical receipt checks do not start Docker during test discovery."""
import json
import unittest

from tools.check_docker import GateError
from tools.docker_pixiv_acceptance import EXPECTED_TESTS, validate


class PixivContainerTests(unittest.TestCase):
    def test_probe_requires_exact_count_no_errors_and_matching_receipt(self):
        valid = dict(receipt="fixture", passed=True, tests=EXPECTED_TESTS, failures=0, errors=0, skipped=0)
        self.assertEqual(validate(json.dumps(valid), "fixture"), valid)
        for changes in ({"receipt": "other"}, {"passed": False}, {"tests": 0},
                        {"tests": True}, {"failures": 1}, {"errors": 1}, {"skipped": 1},
                        {"errors": False}, {"extra": "unapproved detail"}):
            with self.subTest(changes=changes), self.assertRaises(GateError):
                validate(json.dumps(dict(valid, **changes)), "fixture")
