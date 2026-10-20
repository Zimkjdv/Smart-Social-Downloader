"""Disposable Compose storage/network acceptance; called by check_docker --service.

All volumes, containers, networks and image tags are generated and receipt-owned.
Only invented state/media is used; no existing Compose project is inspected.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import time

from .check_docker import GateError, clean_container, decode_json, ordinary, require

STAGES = ("compose_contract", "empty_volume_permissions", "default_port_readiness", "existing_volume_restart",
          "origin_policy", "health_failure_recovery", "writer_exclusion", "permission_rejection",
          "offline_backup", "checksum_rejection", "interrupted_restore", "archive_transport",
          "fresh_volume_restore", "retained_image_rollback")


def available_port(preferred=0):
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", preferred))
        except OSError:
            require(preferred != 0, "no_fixture_port")
            listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def response(port, target_port, path="/api/health", *, host=None, origin=None, data=None, cross_site=False):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    headers = {"Host": host or f"127.0.0.1:{target_port}"}
    if origin:
        headers["Origin"] = origin
    if cross_site:
        headers["Sec-Fetch-Site"] = "cross-site"
    body = None if data is None else json.dumps(data).encode()
    if body is not None:
        headers["Content-Type"] = "application/json"
    try:
        connection.request("GET" if body is None else "POST", path, body=body, headers=headers)
        result = connection.getresponse()
        content = result.read(256 * 1024 + 1)
        require(len(content) <= 256 * 1024, "oversized_fixture_response")
        return result.status, decode_json(content)
    finally:
        connection.close()


def contract(config, port):
    require(isinstance(config, dict), "invalid_compose_model")
    service = config["services"]["downloader"]
    require(service["read_only"] is True and service["init"] is True
            and service["environment"]["SSDL_PORT"] == str(port)
            and service["environment"]["SSDL_DOWNLOAD_DIR"] == "/downloads"
            and service["environment"]["SSDL_CACHE_DIR"] == "/app/cache", "changed_compose_contract")
    ports = service["ports"]
    require(len(ports) == 1 and ports[0]["host_ip"] == "127.0.0.1"
            and ports[0]["target"] == port and str(ports[0]["published"]) == str(port), "unsafe_port_publication")
    require({item["target"] for item in service["volumes"]} == {"/app/data", "/app/cache", "/downloads"}
            and all(item["type"] == "volume" for item in service["volumes"]), "changed_storage_mounts")
    maintenance = config["services"]["storage"]
    require(maintenance["network_mode"] == "none" and maintenance["read_only"] is True
            and maintenance["entrypoint"] == ["python", "-u", "docker/storage.py"], "unsafe_maintenance")
    backups = next(item for item in maintenance["volumes"] if item["target"] == "/backups")
    # Compose v2's JSON omits false fields; v5 includes the explicit false.
    bind = backups.get("bind", {})
    require(backups["type"] == "bind" and isinstance(bind, dict)
            and bind.get("create_host_path", False) is False, "unsafe_backup_bind")


class Fixtures:
    def __init__(self, docker, image, receipt, root, directory):
        self.docker, self.image, self.receipt, self.root, self.directory = docker, image, receipt, root, directory
        self.prefix = "ssdl-service-" + receipt
        self.volumes, self.networks, self.containers, self.images = [], [], [], []
        self.sequence = 0
        self.probe = (root / "tools/docker_storage_probe.py").read_bytes()
        self.environment = {key: value for key, value in os.environ.items()
                            if not key.startswith(("SSDL_", "COMPOSE_"))}
        self.source = directory / "compose.yaml"
        self.source.write_bytes((root / "compose.yaml").read_bytes())
        self.env_file = directory / "fixture.env"
        self.env_file.write_text("SSDL_PORT=8765\n", encoding="ascii")

    def compose(self, path, project, args, **kwargs):
        return self.docker.run(["compose", "--env-file", str(self.env_file), "-f", str(path), "-p", project, *args],
                               env=self.environment, **kwargs)

    def model(self, port):
        self.env_file.write_text(f"SSDL_PORT={port}\n", encoding="ascii")
        _, content = self.compose(self.source, self.prefix, ["--profile", "maintenance", "config", "--format", "json"])
        result = decode_json(content)
        contract(result, port)
        return result

    def volume(self, suffix):
        name = self.prefix + "-" + suffix
        self.docker.run(["volume", "create", "--label", "ssdl.acceptance=" + self.receipt, name])
        _, content = self.docker.run(["volume", "inspect", "--format", "{{json .Labels}}", name])
        require(decode_json(content).get("ssdl.acceptance") == self.receipt, "foreign_fixture_volume")
        self.volumes.append(name)
        return name

    def group(self, name):
        return {kind: self.volume(name + "-" + kind) for kind in ("data", "cache", "media")}

    def helper(self, volumes, backups=None, *, root=False):
        require(set(volumes.values()) <= set(self.volumes) and (not backups or backups in self.volumes), "foreign_fixture_mount")
        self.sequence += 1
        name = self.prefix + "-helper-" + str(self.sequence)
        self.containers.append(name)
        arguments = ["run", "-d", "--name", name, "--label", "ssdl.acceptance=" + self.receipt,
                     "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                     "--no-healthcheck", "--env", "SSDL_DOCKER_ACCEPTANCE=" + self.receipt]
        if root:
            # Root is used only to initialize/import the invented backup volume.
            arguments += ["--user", "0:0", "--cap-add", "CHOWN", "--cap-add", "FOWNER", "--cap-add", "DAC_OVERRIDE"]
        for kind, destination in (("data", "/app/data"), ("cache", "/app/cache"), ("media", "/downloads")):
            if kind in volumes:
                arguments += ["--mount", f"type=volume,source={volumes[kind]},target={destination}"]
        if backups:
            arguments += ["--mount", f"type=volume,source={backups},target=/backups"]
        arguments += ["--entrypoint", "python", self.image, "-c", "import time; time.sleep(900)"]
        self.docker.run(arguments)
        return name

    def probe_action(self, helper, action, *args, expected=0, root=False):
        arguments = ["exec", "-i"]
        if root:
            arguments += ["--user", "0:0"]
        code, content = self.docker.run([*arguments, helper, "python", "-", action, *args],
                                        data=self.probe, timeout=90, check=False)
        require(code == expected, "storage_fixture_failed")
        if expected:
            return None
        value = decode_json(content)
        require(isinstance(value, dict) and set(value) == {"receipt", "result"}
                and value["receipt"] == self.receipt and isinstance(value["result"], dict), "invalid_storage_receipt")
        return value["result"]

    def project(self, group, backups, port, *, published=None, suffix="source", image=None):
        require(set(group) == {"data", "cache", "media"} and set(group.values()) <= set(self.volumes)
                and backups in self.volumes, "foreign_fixture_mount")
        model = self.model(port)
        service = deepcopy(model["services"]["downloader"])
        service.pop("build", None)
        service.update(image=image or self.image, pull_policy="never", restart="no",
                       labels={"ssdl.acceptance": self.receipt},
                       healthcheck={"interval": "1s", "timeout": "5s", "start_period": "1s", "retries": 2})
        service["ports"][0]["published"] = str(published if published is not None else port)
        maintenance = deepcopy(model["services"]["storage"])
        maintenance.update(image=image or self.image, labels={"ssdl.acceptance": self.receipt})
        maintenance["volumes"] = [item for item in maintenance["volumes"] if item["target"] != "/backups"]
        maintenance["volumes"].append({"type": "volume", "source": "backups", "target": "/backups"})
        network = self.prefix + "-" + suffix + "-network"
        self.networks.append(network)
        project = self.prefix + "-" + suffix
        config = {"services": {"downloader": service, "storage": maintenance},
                  "volumes": {"app-data": {"external": True, "name": group["data"]},
                              "cache": {"external": True, "name": group["cache"]},
                              "media": {"external": True, "name": group["media"]},
                              "backups": {"external": True, "name": backups}},
                  "networks": {"default": {"name": network,
                                           "labels": {"ssdl.acceptance": self.receipt}}}}
        path = self.directory / (suffix + ".json")
        path.write_text(json.dumps(config), encoding="utf-8")
        return {"path": path, "name": project, "port": port}

    def state(self, container):
        _, content = self.docker.run(["container", "inspect", "--format", "{{json .}}", container])
        info = decode_json(content)
        require(info["Config"]["Labels"].get("ssdl.acceptance") == self.receipt, "foreign_fixture_container")
        return info

    def up(self, project, *, rejected=False):
        self.compose(project["path"], project["name"], ["up", "-d", "--no-build", "--pull", "never", "downloader"], timeout=90)
        _, container = self.compose(project["path"], project["name"], ["ps", "-a", "-q", "downloader"])
        require(re.fullmatch(r"[0-9a-f]{64}", container), "missing_fixture_container")
        self.containers.append(container)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            info = self.state(container)
            if rejected and not info["State"]["Running"]:
                require(info["State"]["ExitCode"] != 0, "invalid_startup_acceptance")
                return container
            require(rejected or info["State"]["Running"], "service_exited")
            if not rejected and info["State"].get("Health", {}).get("Status") == "healthy":
                bindings = info["NetworkSettings"]["Ports"][str(project["port"]) + "/tcp"]
                require(bindings and all(item["HostIp"] == "127.0.0.1" for item in bindings)
                        and len({item["HostPort"] for item in bindings}) == 1, "unsafe_fixture_binding")
                project.update(container=container, host_port=int(bindings[0]["HostPort"]))
                return container
            time.sleep(.25)
        raise GateError("service_readiness_timeout")

    def stop(self, project):
        container = project["container"]
        self.state(container)
        self.docker.run(["stop", "--time", "30", container], timeout=40)
        require(self.state(container)["State"]["ExitCode"] == 0, "unclean_fixture_shutdown")

    def maintenance(self, project, *args, expected=0):
        self.sequence += 1
        name = self.prefix + "-maintenance-" + str(self.sequence)
        self.containers.append(name)
        code, _ = self.compose(project["path"], project["name"], ["--profile", "maintenance", "run", "--rm", "--no-deps",
                               "--name", name, "storage", *args], timeout=90, check=False)
        require(code == expected, "unexpected_storage_exit")

    def request(self, project, path="/api/health", **kwargs):
        return response(project["host_port"], project["port"], path, **kwargs)

    def cleanup(self):
        failed = False
        for container in reversed(list(dict.fromkeys(self.containers))):
            try:
                clean_container(self.docker, container, self.receipt)
            except Exception:
                failed = True
        for kind, names in (("network", self.networks), ("volume", self.volumes)):
            for name in reversed(list(dict.fromkeys(names))):
                try:
                    code, content = self.docker.run([kind, "inspect", "--format", "{{json .Labels}}", name], check=False)
                    if code:
                        # Network may not have been created yet. Verify absence.
                        _, found = self.docker.run([kind, "ls", "--filter", "name=^" + name + "$", "--format", "{{.Name}}"])
                        require(not found, "resource_cleanup_failed")
                        continue
                    require(decode_json(content).get("ssdl.acceptance") == self.receipt, "foreign_fixture_resource")
                    self.docker.run([kind, "rm", name])
                except Exception:
                    failed = True
        for tag in self.images:
            self.docker.run(["image", "rm", tag], check=False)
        require(not failed, "service_cleanup_failed")


def run_checks(docker, image, receipt, root, report):
    selected_host = docker.prefix[docker.prefix.index("--host") + 1] if "--host" in docker.prefix else os.environ.get("DOCKER_HOST", "")
    require(not selected_host or selected_host.startswith(("npipe:", "unix:")), "local_engine_required")
    _, compose_version = docker.run(["compose", "version", "--short"])
    require(re.fullmatch(r"v?[0-9]+\.[0-9]+\.[0-9]+(?:[.+-][A-Za-z0-9.-]+)?", compose_version), "invalid_compose_version")
    report["compose_version"] = compose_version.removeprefix("v")
    report["service_checks"] = []
    for name in ("compose.yaml", "tools/docker_storage_probe.py", "tools/docker_service_acceptance.py"):
        ordinary(root / name, root)
    report["service_sources_sha256"] = hashlib.sha256(b"".join((root / name).read_bytes() for name in
        ("compose.yaml", "tools/docker_storage_probe.py", "tools/docker_service_acceptance.py"))).hexdigest()
    current = STAGES[0]
    def passed(stage):
        report["service_checks"].append(stage)
        print("Docker service acceptance: " + stage, file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory(prefix="ssdl-compose-") as directory:
        fixtures = Fixtures(docker, image, receipt, root, Path(directory))
        try:
            fixtures.model(8765)
            custom = available_port()
            fixtures.model(custom)
            _, health = docker.run(["image", "inspect", "--format", "{{json .Config.Healthcheck}}", image])
            health = decode_json(health)
            require(health["Test"] == ["CMD", "python", "docker/healthcheck.py"]
                    and health["Interval"] == 30_000_000_000 and health["Timeout"] == 5_000_000_000
                    and health["StartPeriod"] == 60_000_000_000 and health["Retries"] == 3, "changed_health_configuration")
            passed(current)
            current = STAGES[1]
            group = fixtures.group("source")
            backups = fixtures.volume("backups")
            root_helper = fixtures.helper({}, backups, root=True)
            fixtures.probe_action(root_helper, "init-backups")
            helper = fixtures.helper(group, backups)
            fixtures.probe_action(helper, "permissions")
            require(docker.run(["exec", helper, "python", "docker/healthcheck.py"], check=False)[0] == 1,
                    "unstarted_service_probe_passed")
            passed(current)
            current = STAGES[2]
            default_host = available_port(8765)
            project = fixtures.project(group, backups, 8765, published=default_host)
            fixtures.up(project)
            require(fixtures.request(project)[0] == 200, "default_health_failed")
            require(fixtures.docker.run(["exec", project["container"], "python", "docker/healthcheck.py"])[0] == 0, "health_probe_failed")
            report["default_port_publication"] = "8765" if default_host == 8765 else "isolated_ephemeral"
            fixtures.stop(project)
            fixtures.probe_action(helper, "seed")
            passed(current)
            current = STAGES[3]
            project = fixtures.project(group, backups, custom)
            fixtures.up(project)
            status, state = fixtures.request(project, "/api/summary")
            require(status == 200 and state["paused"] and state["counts"]["queued"] == 1
                    and state["counts"]["completed"] == 1 and state["hourly_job_limit"] == 73, "state_not_retained")
            fixtures.stop(project)
            fixtures.up(project)
            fixtures.probe_action(helper, "verify")
            passed(current)
            current = STAGES[4]
            require(fixtures.request(project, origin=f"http://localhost:{custom}")[0] == 200, "trusted_origin_rejected")
            for headers in ({"host": "untrusted.invalid"}, {"origin": "https://untrusted.invalid"}, {"cross_site": True},
                            {"origin": f"http://127.0.0.1:{custom + 1}"}):
                require(fixtures.request(project, **headers)[0] == 403, "untrusted_origin_allowed")
            require(fixtures.request(project, "/api/settings", data={"download_dir": "/tmp/outside"})[0] == 400,
                    "outside_download_root_allowed")
            passed(current)
            current = STAGES[5]
            fixtures.probe_action(helper, "deny-writes")
            fixtures.request(project, "/api/pause", data={"paused": True})
            status, state = fixtures.request(project)
            require(status == 503 and state["checks"]["persistence"] is False, "failed_save_not_unhealthy")
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and fixtures.state(project["container"])["State"]["Health"]["Status"] != "unhealthy":
                time.sleep(.25)
            info = fixtures.state(project["container"])
            require(info["State"]["Health"]["Status"] == "unhealthy" and info["State"]["Running"]
                    and info["RestartCount"] == 0, "health_failure_not_visible")
            fixtures.probe_action(helper, "allow-writes")
            fixtures.request(project, "/api/pause", data={"paused": True})
            require(fixtures.request(project)[0] == 200, "health_did_not_recover")
            passed(current)
            current = STAGES[6]
            fixtures.maintenance(project, "backup", expected=1)
            passed(current)
            current = STAGES[7]
            fixtures.stop(project)
            fixtures.probe_action(helper, "deny-writes")
            fixtures.up(project, rejected=True)
            fixtures.probe_action(helper, "allow-writes")
            fixtures.up(project)
            fixtures.stop(project)
            passed(current)
            current = STAGES[8]
            before = fixtures.probe_action(helper, "inventory")
            fixtures.maintenance(project, "backup")
            archive = fixtures.probe_action(helper, "archive-info")
            require(fixtures.probe_action(helper, "inventory") == before, "backup_changed_originals")
            passed(current)
            current = STAGES[9]
            corrupt = fixtures.probe_action(helper, "corrupt")["archive"]
            failed_group = fixtures.group("corrupt")
            failed_helper = fixtures.helper(failed_group, backups)
            failed_project = fixtures.project(failed_group, backups, custom, suffix="corrupt")
            fixtures.maintenance(failed_project, "restore", corrupt, expected=1)
            fixtures.probe_action(failed_helper, "empty")
            passed(current)
            current = STAGES[10]
            interrupted_group = fixtures.group("interrupted")
            interrupted_helper = fixtures.helper(interrupted_group, backups)
            fixtures.probe_action(interrupted_helper, "interrupt-restore", archive["archive"], expected=75)
            fixtures.probe_action(interrupted_helper, "interrupted")
            interrupted_project = fixtures.project(interrupted_group, backups, custom, suffix="interrupted")
            fixtures.up(interrupted_project, rejected=True)
            passed(current)
            current = STAGES[11]
            transferred = fixtures.volume("transferred-backups")
            transfer_root = fixtures.helper({}, transferred, root=True)
            fixtures.probe_action(transfer_root, "init-backups")
            for suffix in ("", ".sha256"):
                path = Path(directory) / (archive["archive"] + suffix)
                docker.run(["cp", helper + ":/backups/" + path.name, str(path)])
                require(path.stat().st_size <= 4 * 1024 * 1024, "archive_transport_limit")
                docker.run(["cp", str(path), transfer_root + ":/backups/" + path.name])
            fixtures.probe_action(transfer_root, "import-owned", archive["archive"])
            recovered_group = fixtures.group("recovery")
            recovered_helper = fixtures.helper(recovered_group, transferred)
            require(fixtures.probe_action(recovered_helper, "archive-info")["sha256"] == archive["sha256"], "archive_transport_changed")
            passed(current)
            current = STAGES[12]
            recovery = fixtures.project(recovered_group, transferred, custom, suffix="recovery")
            fixtures.maintenance(recovery, "restore", archive["archive"])
            require(fixtures.probe_action(recovered_helper, "inventory") == before, "restore_content_mismatch")
            fixtures.probe_action(recovered_helper, "verify")
            fixtures.probe_action(recovered_helper, "cache-empty")
            fixtures.maintenance(recovery, "restore", archive["archive"], expected=1)
            require(fixtures.probe_action(recovered_helper, "inventory") == before, "nonempty_restore_overwrote")
            fixtures.up(recovery)
            fixtures.stop(recovery)
            passed(current)
            current = STAGES[13]
            upgrade_tag = fixtures.prefix + ":synthetic-upgrade"
            fixtures.images.append(upgrade_tag)
            upgrade_file = Path(directory) / "Dockerfile.upgrade"
            upgrade_file.write_text(f"FROM {image}\nLABEL ssdl.acceptance.upgrade={receipt}\n", encoding="ascii")
            docker.run(["build", "--network", "none", "-f", str(upgrade_file), "-t", upgrade_tag, str(directory)], timeout=60)
            upgrade = fixtures.project(group, backups, custom, image=upgrade_tag)
            fixtures.up(upgrade)
            require(fixtures.state(upgrade["container"])["Image"] != report["image_id"], "upgrade_identity_unchanged")
            fixtures.probe_action(helper, "verify")
            fixtures.stop(upgrade)
            fixtures.up(recovery)
            require(fixtures.state(recovery["container"])["Image"] == report["image_id"], "wrong_rollback_image")
            fixtures.probe_action(recovered_helper, "verify")
            fixtures.stop(recovery)
            passed(current)
            require(report["service_checks"] == list(STAGES), "incomplete_service_acceptance")
        except Exception:
            report["service_error"] = current + "_failed"
            raise
        finally:
            fixtures.cleanup()
