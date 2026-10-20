"""Shared fake Docker CLI fixture; never evidence of real container acceptance."""
import json
import subprocess

from tools import check_docker as gate


VERSIONS = {"python": "3.12.15", "node": "22.23.3", "ffmpeg": "5.1.8-0+deb12u1",
            "yt-dlp": "2026.8.19", "gallery-dl": "1.32.16", "yt-dlp-ejs": "0.8.0",
            "imageio-ffmpeg": "0.6.0", "pycryptodomex": "3.24.1"}
DOCKERFILE = ("FROM node:22.23.3-bookworm-slim@sha256:" + "1" * 64 + " AS node_runtime\n"
              "FROM python:3.12.15-slim-bookworm@sha256:" + "2" * 64 + " AS runtime\n").encode()


class FakeDocker:
    def __init__(self, *, fail=None):
        self.fail = fail
        self.calls = []
        self.receipt = None

    def run(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if args[0] == "info":
            if self.fail == "engine":
                return 0, "Docker Desktop is unable to start"
            return 0, '{"OSType":"linux","ServerVersion":"29.8.2"}'
        if args[0] == "build":
            if self.fail == "build":
                raise subprocess.TimeoutExpired("fixture", 900)
            return 0, ""
        if args[:2] == ["image", "inspect"]:
            return 0, "sha256:" + "3" * 64
        if args[0] == "run":
            receipt = next(value.split("=", 1)[1] for value in args if value.startswith("SSDL_DOCKER_ACCEPTANCE="))
            self.receipt = receipt
            result = {"format_version": 1, "receipt": receipt, "passed": True,
                      "checks": list(gate.CHECKS), "versions": VERSIONS.copy()}
            if self.fail == "runtime":
                result.update(passed=False, checks=["isolation"], error_code="dependencies_failed", versions={})
                return 1, json.dumps(result)
            if self.fail == "timeout":
                raise subprocess.TimeoutExpired("fixture", 240)
            return 0, json.dumps(result)
        if args[:2] == ["container", "inspect"]:
            return 0, json.dumps({"ssdl.acceptance": "someone-else" if self.fail == "ownership" else self.receipt})
        return 0, ""
