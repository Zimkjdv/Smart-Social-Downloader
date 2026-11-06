"""Build two trusted source snapshots and exercise upgrade and backup rollback.

All state, media, SQLite rows and encrypted sessions are invented. Source changes
with the same application version are reported separately from version changes.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from .check_docker import (decode_json, fingerprint, ordinary, require, run_gate,
                           runtime_sources, stage_sources)
from .docker_interaction_acceptance import json_request, pair, status, token
from .docker_service_acceptance import Fixtures, available_port

STAGES = ("distinct_source_images", "baseline_state_login", "pre_upgrade_backup", "candidate_upgrade",
          "candidate_restart", "candidate_writes", "matching_image_restore", "rollback_restart_retention")


def version(files):
    tree = ast.parse(files["ssdl/version.py"])
    values = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)]
    require(len(values) == 1 and isinstance(values[0], str)
            and re.fullmatch(r"[A-Za-z0-9.+_-]{1,100}", values[0]), "invalid_upgrade_version")
    return values[0]


def application_fingerprint(files):
    # A new image label/tag or license edit alone is not an application upgrade.
    return fingerprint({name: content for name, content in files.items()
                        if name not in {"Dockerfile", ".dockerignore", "LICENSE", "THIRD_PARTY_NOTICES.md"}})


def action(fixtures, probe, container, name, *, root=False):
    code, content = fixtures.docker.run(["exec", "-i", "--user", "0:0" if root else "10001:10001",
                                        container, "python", "-", name], data=probe, timeout=60, check=False)
    require(code == 0, "upgrade_fixture_failed")
    value = decode_json(content)
    require(isinstance(value, dict) and set(value) == {"receipt", "result"}
            and value["receipt"] == fixtures.receipt and isinstance(value["result"], dict), "invalid_upgrade_receipt")
    return value["result"]


def encrypted_project(fixtures, group, backups, keys, port, suffix, image):
    require(keys in fixtures.volumes, "foreign_fixture_mount")
    project = fixtures.project(group, backups, port, suffix=suffix, image=image)
    model = json.loads(project["path"].read_text())
    model["volumes"]["session-keys"] = {"external": True, "name": keys}
    app = model["services"]["downloader"]
    app["environment"]["SSDL_DOCKER_ACCEPTANCE"] = fixtures.receipt
    app["environment"]["SSDL_X_KEY_FILE"] = "/run/secrets/x_session_key"
    app["volumes"].append({"type": "volume", "source": "session-keys", "target": "/run/secrets", "read_only": True})
    project["path"].write_text(json.dumps(model), encoding="utf-8")
    return project


def verify_running(fixtures, project, helper, session_probe, encrypted, limit=73):
    require(fixtures.request(project)[0] == 200, "upgrade_health_failed")
    code, summary = json_request(project, "/api/summary")
    require(code == 200 and summary["paused"] is True and summary["counts"]["completed"] == 1
            and summary["counts"]["queued"] == 1 and summary["hourly_job_limit"] == limit,
            "upgrade_state_changed")
    code, setup = json_request(project, "/api/auth/x/setup")
    require(code == 200 and setup["storage_mode"] == "aes-gcm" and setup["persistent"], "upgrade_storage_mode_changed")
    status(project, True)
    require(action(fixtures, session_probe, helper, "session-info") == encrypted, "upgrade_session_changed")
    fixtures.probe_action(helper, "verify-databases")
    mounts = fixtures.state(project["container"])["Mounts"]
    key_mounts = [mount for mount in mounts if mount["Destination"] == "/run/secrets"]
    require(len(key_mounts) == 1 and not key_mounts[0]["RW"], "upgrade_key_writable")


def compare_images(docker, candidate_image, baseline_image, receipt, root, report):
    require(report["upgrade_baseline"]["image_id"] != report["image_id"], "upgrade_image_unchanged")
    session_probe = (root / "tools/docker_interaction_probe.py").read_bytes()
    current = STAGES[0]

    def passed():
        report["upgrade_checks"].append(current)
        print("Docker upgrade acceptance: " + current, file=sys.stderr, flush=True)

    with tempfile.TemporaryDirectory(prefix="ssdl-upgrade-compose-") as directory:
        # The baseline creates all original volume ownership and data.
        fixtures = Fixtures(docker, baseline_image, receipt, root, Path(directory))
        try:
            passed()
            current = STAGES[1]
            group, backups, keys = fixtures.group("upgrade"), fixtures.volume("backups"), fixtures.volume("keys")
            backup_helper = fixtures.helper({}, backups, root=True)
            fixtures.probe_action(backup_helper, "init-backups")
            key_helper = fixtures.helper({}, keys=keys, root=True)
            action(fixtures, session_probe, key_helper, "init-keys", root=True)
            docker.run(["exec", "--user", "10001:10001", key_helper, "python", "docker/session_key.py"])
            action(fixtures, session_probe, key_helper, "key-info")
            helper = fixtures.helper(group, backups)
            fixtures.probe_action(helper, "seed")
            port = available_port()
            baseline = encrypted_project(fixtures, group, backups, keys, port, "baseline", baseline_image)
            fixtures.up(baseline)
            code, setup = json_request(baseline, "/api/auth/x/setup")
            require(code == 200, "baseline_setup_failed")
            pair(baseline, setup, token(baseline))
            encrypted = action(fixtures, session_probe, helper, "session-info")
            require(encrypted.get("exists") is True, "baseline_session_not_saved")
            verify_running(fixtures, baseline, helper, session_probe, encrypted)
            fixtures.stop(baseline)
            passed()

            current = STAGES[2]
            before = fixtures.probe_action(helper, "inventory")
            fixtures.maintenance(baseline, "backup")
            archive = fixtures.probe_action(helper, "archive-info")
            require(fixtures.probe_action(helper, "inventory") == before, "upgrade_backup_changed_originals")
            passed()

            current = STAGES[3]
            candidate = encrypted_project(fixtures, group, backups, keys, port, "candidate", candidate_image)
            fixtures.up(candidate)
            require(fixtures.state(candidate["container"])["Image"] == report["image_id"], "wrong_upgrade_image")
            # Execute record lookups using the candidate's modules against the old SQLite files.
            verify_running(fixtures, candidate, candidate["container"], session_probe, encrypted)
            fixtures.probe_action(helper, "verify")
            passed()

            current = STAGES[4]
            fixtures.stop(candidate)
            fixtures.up(candidate)
            verify_running(fixtures, candidate, candidate["container"], session_probe, encrypted)
            fixtures.probe_action(helper, "verify")
            passed()

            current = STAGES[5]
            require(json_request(candidate, "/api/settings", data={"download_dir": "/downloads", "hourly_job_limit": 74})[0] == 200,
                    "candidate_write_failed")
            fixtures.stop(candidate)
            fixtures.up(candidate)
            verify_running(fixtures, candidate, candidate["container"], session_probe, encrypted, limit=74)
            fixtures.stop(candidate)
            candidate_inventory = fixtures.probe_action(helper, "inventory")
            require(candidate_inventory != before, "candidate_changes_not_persisted")
            passed()

            current = STAGES[6]
            recovered = fixtures.group("rollback")
            recovered_helper = fixtures.helper(recovered, backups)
            rollback = encrypted_project(fixtures, recovered, backups, keys, port, "rollback", baseline_image)
            fixtures.maintenance(rollback, "restore", archive["archive"])
            require(fixtures.probe_action(recovered_helper, "inventory") == before, "upgrade_restore_changed_bytes")
            fixtures.probe_action(recovered_helper, "verify")
            fixtures.up(rollback)
            require(fixtures.state(rollback["container"])["Image"] == report["upgrade_baseline"]["image_id"],
                    "wrong_rollback_image")
            verify_running(fixtures, rollback, recovered_helper, session_probe, encrypted)
            passed()

            current = STAGES[7]
            fixtures.stop(rollback)
            fixtures.up(rollback)
            verify_running(fixtures, rollback, recovered_helper, session_probe, encrypted)
            fixtures.stop(rollback)
            require(fixtures.probe_action(helper, "inventory") == candidate_inventory, "rollback_modified_upgraded_volumes")
            require(fixtures.probe_action(helper, "archive-info") == archive, "upgrade_backup_changed")
            passed()
            require(report["upgrade_checks"] == list(STAGES), "incomplete_upgrade_acceptance")
        except Exception:
            report["upgrade_error"] = current + "_failed"
            raise
        finally:
            fixtures.cleanup()


def run_checks(docker, image, receipt, root, report, *, baseline_root):
    selected_host = docker.prefix[docker.prefix.index("--host") + 1] if "--host" in docker.prefix else None
    # Match the service gate's local-only contract, including DOCKER_HOST.
    require(not (selected_host or os.environ.get("DOCKER_HOST", ""))
            or (selected_host or os.environ["DOCKER_HOST"]).startswith(("npipe:", "unix:")), "local_engine_required")
    report["upgrade_checks"] = []
    report["upgrade_error"] = "source_selection_failed"
    sources = ("tools/docker_upgrade_acceptance.py",
               "tools/docker_service_acceptance.py", "tools/docker_storage_probe.py",
               "tools/docker_interaction_acceptance.py", "tools/docker_interaction_probe.py", "compose.yaml")
    for name in sources:
        ordinary(root / name, root)
    report["upgrade_sources_sha256"] = fingerprint({name: (root / name).read_bytes() for name in sources})
    baseline_files, candidate_files = runtime_sources(baseline_root), runtime_sources(root)
    require(fingerprint(candidate_files) == report["source_sha256"], "candidate_source_changed")
    require(application_fingerprint(baseline_files) != application_fingerprint(candidate_files), "upgrade_source_unchanged")
    old_version, new_version = version(baseline_files), version(candidate_files)
    report["upgrade_versions"] = {"baseline": old_version, "candidate": new_version,
                                  "version_changed": old_version != new_version}
    baseline_report = {"schema": 1, "passed": False, "complete": False, "checks": []}
    report["upgrade_baseline"] = baseline_report
    with tempfile.TemporaryDirectory(prefix="ssdl-upgrade-source-") as directory:
        snapshot = Path(directory)
        stage_sources(baseline_files, snapshot, "synthetic-upgrade-canary")
        (snapshot / "tools").mkdir()
        # Use the currently reviewed runtime probe rather than executing an old host tool.
        (snapshot / "tools/docker_runtime_probe.py").write_bytes((root / "tools/docker_runtime_probe.py").read_bytes())
        def baseline_gate(engine, baseline_image, baseline_receipt, _root, _report):
            compare_images(engine, image, baseline_image, baseline_receipt, root, report)
        report["upgrade_error"] = "baseline_runtime_or_cleanup_failed"
        run_gate(docker, snapshot, baseline_report, service_gate=baseline_gate)
    require(baseline_report["passed"] is True and baseline_report["complete"] is True,
            "upgrade_baseline_failed")
    report.pop("upgrade_error", None)
