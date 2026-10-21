"""Actual container session and HTTP-media acceptance using invented data only."""
from __future__ import annotations

import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import parse_qs, quote, urlparse

from .check_docker import decode_json, ordinary, require
from .docker_service_acceptance import Fixtures, available_port

STAGES = ("login_override_contract", "memory_pairing", "pairing_cancel_repair", "memory_restart",
          "private_key_generation", "encrypted_pairing", "encrypted_restart", "wrong_key_preservation",
          "missing_key_preservation", "key_recovery_disconnect", "browser_file_actions", "original_head_ranges",
          "media_path_rejection", "moved_file_retention", "concurrent_reader_recovery")


def login_contract(model):
    app = model["services"]["downloader"]
    mounted = app.get("secrets", [])
    # Compose versions normalize a short secret target to either basename or absolute path.
    require(app["environment"]["SSDL_X_KEY_FILE"] == "/run/secrets/x_session_key"
            and len(mounted) == 1 and mounted[0]["source"] == "x_session_key"
            and mounted[0]["target"] in {"x_session_key", "/run/secrets/x_session_key"}
            and all(not model["services"][name].get("secrets") for name in ("storage", "session-key")),
            "unsafe_login_override")


def raw_request(project, path, *, method="GET", data=None, headers=None, hold=False):
    connection = http.client.HTTPConnection("127.0.0.1", project["host_port"], timeout=15)
    fields = {"Host": f"127.0.0.1:{project['port']}"}
    fields.update(headers or {})
    body = None if data is None else json.dumps(data).encode()
    if data is not None:
        fields["Content-Type"] = "application/json"
        method = "POST"
    handed_off = False
    try:
        connection.request(method, path, body=body, headers=fields)
        response = connection.getresponse()
        if hold:
            handed_off = True
            return connection, response
        content = response.read(20 * 1024 * 1024 + 1)
        require(len(content) <= 20 * 1024 * 1024, "interaction_response_limit")
        return response.status, dict(response.getheaders()), content
    finally:
        if not handed_off:
            connection.close()


def json_request(project, path, **options):
    status, _, content = raw_request(project, path, **options)
    return status, decode_json(content)


def token(project):
    status, value = json_request(project, "/api/auth/x/connect", data={})
    require(status == 202, "pairing_not_started")
    parsed = urlparse(value["pairing_url"])
    require(parsed.scheme == "http" and parsed.netloc == f"127.0.0.1:{project['port']}"
            and parsed.path == "/chrome-connect" and not parsed.query, "unsafe_pairing_url")
    ticket = parse_qs(parsed.fragment)["token"][0]
    require(len(ticket) == 43, "invalid_pairing_ticket")
    return ticket


def pair(project, setup, ticket, expected=200):
    status, _ = json_request(project, "/api/auth/x/extension",
        data={"cookies": [{"domain": ".x.com", "name": "auth_token", "value": "ssdl-invented-session"}]},
        headers={"Origin": "chrome-extension://" + setup["extension_id"],
                 "X-SSDL-Extension": setup["extension_id"], "Authorization": "Bearer " + ticket})
    require(status == expected, "unexpected_pairing_result")


def status(project, connected, *, phase=None):
    code, value = json_request(project, "/api/summary")
    auth = value["x_auth"]
    require(code == 200 and auth["connected"] is connected and (phase is None or auth["phase"] == phase)
            and "ssdl-invented-session" not in json.dumps(value), "unexpected_session_state")


def run_checks(docker, image, receipt, root, report):
    sources = ("compose.login.yaml", "docker/session_key.py", "tools/docker_interaction_acceptance.py",
               "tools/docker_interaction_probe.py")
    for name in sources:
        ordinary(root / name, root)
    report["interaction_sources_sha256"] = hashlib.sha256(b"".join((root / name).read_bytes() for name in sources)).hexdigest()
    report["interaction_checks"] = []
    current = STAGES[0]
    def passed():
        report["interaction_checks"].append(current)
        print("Docker interaction acceptance: " + current, file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory(prefix="ssdl-interaction-") as directory:
        fixtures = Fixtures(docker, image, receipt, root, Path(directory))
        probe = (root / "tools/docker_interaction_probe.py").read_bytes()
        def action(container, name, *, root_user=False, encrypted=False):
            args = ["exec", "-i", "--user", "0:0" if root_user else "10001:10001"]
            if encrypted:
                args += ["--env", "SSDL_X_KEY_FILE=/run/secrets/x_session_key"]
            code, content = docker.run([*args, container, "python", "-", name], data=probe, check=False, timeout=60)
            require(code == 0, "interaction_fixture_failed")
            result = decode_json(content)
            require(set(result) == {"receipt", "result"} and result["receipt"] == receipt
                    and isinstance(result["result"], dict), "invalid_interaction_receipt")
            return result["result"]
        try:
            override = Path(directory) / "compose.login.yaml"
            override.write_bytes((root / "compose.login.yaml").read_bytes())
            _, model = fixtures.compose(fixtures.source, fixtures.prefix,
                ["-f", str(override), "--profile", "maintenance", "config", "--format", "json"])
            model = decode_json(model)
            login_contract(model)
            passed()
            current = STAGES[1]
            group, backups = fixtures.group("interaction"), fixtures.volume("unused-backups")
            helper = fixtures.helper(group)
            media = action(helper, "seed-media")
            project = fixtures.project(group, backups, available_port(), suffix="interaction")
            fixtures.up(project)
            code, setup = json_request(project, "/api/auth/x/setup")
            require(code == 200 and setup["storage_mode"] == "memory" and not setup["persistent"]
                    and setup["host_browser"] and not setup["extension_dir"], "wrong_memory_mode")
            ticket = token(project)
            pair(project, setup, "x" * 43, expected=400)
            pair(project, setup, ticket)
            pair(project, setup, ticket, expected=400)
            status(project, True)
            require(action(helper, "session-info") == {"exists": False}, "memory_session_written")
            passed()
            current = STAGES[2]
            cancelled = token(project)
            require(json_request(project, "/api/auth/x/disconnect", data={})[0] == 200, "disconnect_failed")
            pair(project, setup, cancelled, expected=400)
            old, new = token(project), token(project)
            pair(project, setup, old, expected=400)
            pair(project, setup, new)
            passed()
            current = STAGES[3]
            fixtures.stop(project)
            fixtures.up(project)
            status(project, False)
            require(action(helper, "session-info") == {"exists": False}, "memory_session_retained")
            fixtures.stop(project)
            passed()
            current = STAGES[4]
            keys = fixtures.volume("session-keys")
            key_helper = fixtures.helper({}, root=True, keys=keys)
            action(key_helper, "init-keys", root_user=True)
            command = ["exec", "--user", "10001:10001", key_helper, "python", "docker/session_key.py"]
            docker.run(command)
            require(docker.run(command, check=False)[0] == 1, "existing_key_overwritten")
            action(key_helper, "key-info")
            config = json.loads(project["path"].read_text())
            config["volumes"]["session-keys"] = {"external": True, "name": keys}
            app = config["services"]["downloader"]
            app["environment"]["SSDL_DOCKER_ACCEPTANCE"] = receipt
            app["environment"]["SSDL_X_KEY_FILE"] = "/run/secrets/x_session_key"
            app["volumes"].append({"type": "volume", "source": "session-keys", "target": "/run/secrets", "read_only": True})
            project["path"].write_text(json.dumps(config), encoding="utf-8")
            passed()
            current = STAGES[5]
            fixtures.up(project)
            require(all(not mount["RW"] for mount in fixtures.state(project["container"])["Mounts"]
                        if mount["Destination"] == "/run/secrets"), "writable_runtime_key")
            code, encrypted_setup = json_request(project, "/api/auth/x/setup")
            require(code == 200 and encrypted_setup["storage_mode"] == "aes-gcm" and encrypted_setup["persistent"], "wrong_cipher_mode")
            pair(project, setup, token(project))
            status(project, True)
            encrypted = action(helper, "session-info")
            require(encrypted["exists"], "ciphertext_not_saved")
            action(project["container"], "cipher-contract", encrypted=True)
            passed()
            current = STAGES[6]
            fixtures.stop(project)
            fixtures.up(project)
            status(project, True)
            require(action(helper, "session-info") == encrypted, "restart_changed_ciphertext")
            passed()
            for stage, key_action in ((STAGES[7], "wrong-key"), (STAGES[8], "missing-key")):
                current = stage
                fixtures.stop(project)
                action(key_helper, key_action)
                fixtures.up(project)
                status(project, False, phase="expired")
                require(fixtures.request(project)[0] == 200 and action(helper, "session-info") == encrypted,
                        "failed_key_damaged_session")
                if key_action == "missing-key":
                    require(json_request(project, "/api/auth/x/connect", data={})[0] == 400, "missing_key_pairing_allowed")
                passed()
            current = STAGES[9]
            fixtures.stop(project)
            action(key_helper, "recover-key")
            fixtures.up(project)
            status(project, True)
            require(json_request(project, "/api/auth/x/disconnect", data={})[0] == 200, "encrypted_disconnect_failed")
            require(action(helper, "session-info") == {"exists": False}, "disconnect_retained_ciphertext")
            fixtures.stop(project)
            fixtures.up(project)
            status(project, False)
            passed()
            current = STAGES[10]
            code, listing = json_request(project, "/api/jobs/fixture-media/files?offset=0&limit=2")
            require(code == 200 and listing["total"] == len(media["files"]) and len(listing["files"]) == 2, "file_pagination_failed")
            selection = {"file_index": 0, "filename": media["files"][0]}
            code, opened = json_request(project, "/api/jobs/fixture-media/open-file", data=selection)
            require(code == 200 and opened["browser"] and opened["opened"], "browser_open_failed")
            path = opened["url"]
            require(json_request(project, "/api/jobs/fixture-media/open-folder", data=selection)[0] == 400,
                    "container_launched_folder")
            passed()
            current = STAGES[11]
            code, headers, content = raw_request(project, path)
            require(code == 200 and hashlib.sha256(content).hexdigest() == media["png_sha256"]
                    and headers["Content-Type"] == "image/png" and headers["X-Content-Type-Options"] == "nosniff"
                    and headers["Cache-Control"] == "no-store" and "sandbox" in headers["Content-Security-Policy"], "original_bytes_changed")
            code, headers, body = raw_request(project, path, method="HEAD")
            require(code == 200 and not body and int(headers["Content-Length"]) == len(content), "head_failed")
            for requested, expected in (("bytes=1-4", content[1:5]), ("bytes=-3", content[-3:]), ("bytes=4-", content[4:])):
                code, headers, body = raw_request(project, path, headers={"Range": requested})
                require(code == 206 and body == expected and headers["Content-Range"].endswith("/" + str(len(content))), "range_failed")
            for requested in ("bytes=99999-", "bytes=0-1,4-5", "bytes=-0"):
                require(raw_request(project, path, headers={"Range": requested})[0] == 416, "invalid_range_allowed")
            require(raw_request(project, path, headers={"Range": "bytes=1-4", "If-Range": "unknown"})[0] == 200, "if_range_failed")
            video = "/api/jobs/fixture-media/content?file_index=1&filename=" + quote(media["files"][1], safe="")
            code, headers, body = raw_request(project, video)
            require(code == 200 and headers["Content-Type"] == "video/mp4"
                    and hashlib.sha256(body).hexdigest() == media["video_sha256"], "video_bytes_changed")
            passed()
            current = STAGES[12]
            for bad, expected in ((path.replace("file_index=0", "file_index=4").replace(quote(media["files"][0], safe=""), quote(media["files"][4], safe="")), 404),
                                  (path.replace("file_index=0", "file_index=1"), 409),
                                  (path.replace(quote(media["files"][0], safe=""), "..%2Fapp%2FLICENSE"), 409)):
                require(raw_request(project, bad)[0] == expected, "unsafe_selection_allowed")
            require(raw_request(project, path, headers={"Origin": "https://untrusted.invalid"})[0] == 403, "cross_origin_media_allowed")
            passed()
            current = STAGES[13]
            action(helper, "move-media")
            moved = "/api/jobs/fixture-media/content?file_index=3&filename=" + quote(media["files"][3], safe="")
            require(raw_request(project, moved)[0] == 404, "moved_file_served")
            code, details = json_request(project, "/api/jobs/fixture-media/details")
            require(code == 200 and details["status"] == "completed" and fixtures.request(project)[0] == 200, "missing_file_changed_job")
            passed()
            current = STAGES[14]
            slow = "/api/jobs/fixture-media/content?file_index=2&filename=" + quote(media["files"][2], safe="")
            held = []
            try:
                for _ in range(4):
                    connection, response = raw_request(project, slow, hold=True)
                    held.append((connection, response))
                    require(response.status == 200, "reader_slot_unavailable")
                require(raw_request(project, path)[0] == 503, "reader_limit_missing")
                require(fixtures.request(project)[0] == 200, "readers_blocked_health")
            finally:
                for connection, response in held:
                    response.close()
                    connection.close()
            deadline = time.monotonic() + 20
            while raw_request(project, path)[0] == 503 and time.monotonic() < deadline:
                time.sleep(.1)
            require(raw_request(project, path)[0] == 200, "reader_slots_leaked")
            passed()
            fixtures.stop(project)
            require(report["interaction_checks"] == list(STAGES), "incomplete_interaction_acceptance")
        except Exception:
            report["interaction_error"] = current + "_failed"
            raise
        finally:
            fixtures.cleanup()
