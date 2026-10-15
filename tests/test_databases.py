"""SQLite maintenance with disposable real databases, no personal state or network."""
from contextlib import closing
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from ssdl.app import create_app
from ssdl.database_maintenance import DatabaseMaintenance, DATABASES, MaintenanceError
from ssdl.http_server import BoundedHTTPServer
from ssdl.image_history import ImageHistory
from ssdl.media_manifest import MediaManifest
from ssdl.x_profiles import ProfileArchive


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ssdl-databases-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / "data"
        self.service = DatabaseMaintenance(self.data)
        self.addCleanup(self.service.shutdown)

    def run_operation(self, action):
        self.service.request(action)
        self.service._thread.join(15)
        self.assertFalse(self.service._thread.is_alive())
        return self.service.status()

    def seed(self):
        self.media = self.root / "SENTINEL_MEDIA"
        self.media.mkdir()
        (self.media / "one.jpg").write_bytes(b"synthetic-original")
        result = {"files": ["one.jpg"], "title": "synthetic", "quality": "orig"}
        for kind, args in ((ImageHistory, (self.data / DATABASES["images"][0], self.media)),
                           (MediaManifest, (self.data / DATABASES["media"][0], self.media)),
                           (ProfileArchive, (self.data / DATABASES["profiles"][0], self.media, "example"))):
            store = kind(*args)
            try:
                if kind is ProfileArchive:
                    store.record("1234567890", ["one.jpg"], 1)
                else:
                    store.record("https://example.org/SENTINEL_SOURCE", result)
            finally:
                store.close()
        for filename, _ in DATABASES.values():
            with closing(sqlite3.connect(self.data / filename)) as connection:
                connection.execute("CREATE TABLE extra (value TEXT)")
                connection.execute("INSERT INTO extra VALUES ('preserve-extra')")
                connection.execute("CREATE TABLE scratch (value BLOB)")
                connection.executemany("INSERT INTO scratch VALUES (zeroblob(65536))", [()] * 12)
                connection.execute("DELETE FROM scratch")
                connection.execute("CREATE INDEX extra_index ON extra(value)")
                connection.commit()

    def rows(self, directory):
        result = {}
        for filename, table in DATABASES.values():
            with closing(sqlite3.connect(directory / filename)) as connection:
                result[filename] = (connection.execute('SELECT * FROM "' + table + '"').fetchall(),
                    connection.execute("SELECT * FROM extra").fetchall(),
                    connection.execute("SELECT type,name,sql FROM sqlite_master ORDER BY name").fetchall())
        return result

    def test_passive_construction_and_missing_databases_create_no_files(self):
        self.assertIsNone(self.service._thread)
        self.assertFalse(self.data.exists())
        report = self.run_operation("refresh")
        self.assertEqual(len(report["entries"]), 3)
        self.assertTrue(all(row["status"] == "missing" for row in report["entries"]))
        self.assertFalse(self.data.exists())
        report = self.run_operation("compact")
        self.assertEqual(report["result_code"], "database_no_files")
        self.assertFalse(self.data.exists())

    def test_diagnostics_reports_capacity_without_disclosing_rows_or_paths(self):
        self.seed()
        report = self.run_operation("refresh")
        self.assertEqual(report["phase"], "complete")
        self.assertGreater(report["total_bytes"], 0)
        self.assertGreater(report["reclaimable_bytes"], 0)
        self.assertTrue(all(row["records"] == 1 for row in report["entries"]))
        output = json.dumps(report)
        for secret in (str(self.root), "SENTINEL_MEDIA", "SENTINEL_SOURCE", "one.jpg"):
            self.assertNotIn(secret, output)
        report["entries"].clear()
        self.assertEqual(len(self.service.status()["entries"]), 3)

    def test_compaction_backs_up_and_preserves_dedup_rows_schema_and_media(self):
        self.seed()
        before = self.rows(self.data)
        original = (self.media / "one.jpg").stat()
        report = self.run_operation("compact")
        self.assertEqual(report["phase"], "complete", report)
        self.assertTrue(report["backup_name"])
        self.assertGreater(report["backup_bytes"], report["total_bytes"])
        self.assertEqual(self.rows(self.data / "database-backups" / report["backup_name"]), before)
        self.assertEqual(self.rows(self.data), before)
        self.assertEqual(report["reclaimable_bytes"], 0)
        self.assertTrue(all(row["compacted"] for row in report["entries"]))
        self.assertEqual((self.media / "one.jpg").stat().st_mtime_ns, original.st_mtime_ns)
        self.assertEqual((self.media / "one.jpg").read_bytes(), b"synthetic-original")
        moved = self.media / "renamed.jpg"
        (self.media / "one.jpg").rename(moved)
        stores = [ImageHistory(self.data / DATABASES["images"][0], self.media),
                  MediaManifest(self.data / DATABASES["media"][0], self.media),
                  ProfileArchive(self.data / DATABASES["profiles"][0], self.media, "example")]
        try:
            self.assertIsNone(stores[0].lookup("https://example.org/SENTINEL_SOURCE"))
            self.assertIsNone(stores[1].lookup("https://example.org/SENTINEL_SOURCE"))
            self.assertIsNone(stores[2].lookup("1234567890", 1))
        finally:
            for store in stores: store.close()
        self.assertTrue(moved.is_file())

    def test_backup_includes_committed_wal_and_retains_earlier_backups(self):
        self.seed()
        path = self.data / DATABASES["media"][0]
        with closing(sqlite3.connect(path)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("INSERT INTO extra VALUES ('committed-wal')")
            writer.commit()
            self.assertGreater(path.with_name(path.name + "-wal").stat().st_size, 0)
            first = self.run_operation("backup")
            backup = self.data / "database-backups" / first["backup_name"]
            self.assertEqual(self.rows(backup), self.rows(self.data))
            second = self.run_operation("backup")
            self.assertNotEqual(first["backup_name"], second["backup_name"])
            self.assertTrue(backup.is_dir())
            self.assertEqual(len(list(backup.iterdir())), 3)

    def test_failed_backup_never_compacts_or_publishes_partial_set(self):
        self.seed()
        before = self.rows(self.data)
        with patch("ssdl.database_maintenance.os.fsync", side_effect=OSError("synthetic disk failure")), \
                patch.object(self.service, "_compact") as compact:
            report = self.run_operation("compact")
        self.assertEqual(report["error_code"], "database_io")
        compact.assert_not_called()
        self.assertFalse(list(self.service.backups.iterdir()))
        self.assertEqual(self.rows(self.data), before)
        self.assertEqual(self.run_operation("backup")["phase"], "complete")

    def test_corrupt_input_is_preserved_and_does_not_overwrite_good_backup(self):
        self.seed()
        first = self.run_operation("backup")
        backup = self.service.backups / first["backup_name"]
        before = self.rows(backup)
        bad = self.data / DATABASES["images"][0]
        bad.write_bytes(b"synthetic-corruption")
        with patch.object(self.service, "_compact") as compact:
            report = self.run_operation("compact")
        self.assertEqual(report["error_code"], "database_invalid")
        compact.assert_not_called()
        self.assertEqual(bad.read_bytes(), b"synthetic-corruption")
        self.assertEqual(self.rows(backup), before)

    def test_unknown_schema_can_be_backed_up_but_is_not_compacted(self):
        self.data.mkdir()
        with closing(sqlite3.connect(self.data / DATABASES["images"][0])) as connection:
            connection.execute("CREATE TABLE unknown (value TEXT)")
        self.assertEqual(self.run_operation("backup")["phase"], "complete")
        with patch.object(self.service, "_compact") as compact:
            self.assertEqual(self.run_operation("compact")["error_code"], "database_schema")
        compact.assert_not_called()

    def test_locked_database_is_retryable(self):
        self.seed()
        with closing(sqlite3.connect(self.data / DATABASES["images"][0])) as writer:
            writer.execute("BEGIN EXCLUSIVE")
            with patch("ssdl.database_maintenance.BUSY_MILLISECONDS", 25):
                self.assertEqual(self.run_operation("backup")["error_code"], "database_locked")
            writer.rollback()
        self.assertEqual(self.run_operation("backup")["phase"], "complete")

    def test_reparse_paths_and_sidecars_are_rejected_before_connection(self):
        self.seed()
        ordinary = self.service._ordinary
        def unsafe(path, **kwargs):
            if path.name == "image-history.sqlite3-wal":
                raise MaintenanceError("database_path_blocked")
            return ordinary(path, **kwargs)
        with patch.object(self.service, "_ordinary", side_effect=unsafe), patch.object(self.service, "_compact") as compact:
            report = self.run_operation("compact")
        self.assertEqual(report["error_code"], "database_path_blocked")
        compact.assert_not_called()
        # Exercise the Windows reparse attribute independent of link privileges.
        info = Mock(st_mode=0o100600, st_nlink=1, st_file_attributes=0x400)
        with patch.object(Path, "lstat", return_value=info), self.assertRaises(MaintenanceError):
            DatabaseMaintenance._ordinary(self.data / "synthetic.sqlite3")

    def test_deadline_and_shutdown_cancel_owned_work_and_block_new_requests(self):
        with patch("ssdl.database_maintenance.OPERATION_SECONDS", -1):
            self.assertEqual(self.run_operation("refresh")["error_code"], "database_timeout")
        began = threading.Event()
        def wait_for_stop(key):
            began.set()
            self.assertTrue(self.service._stop.wait(5))
            self.service._guard()
        with patch.object(self.service, "_inspect", side_effect=wait_for_stop):
            self.service.request("backup")
            self.assertTrue(began.wait(5))
            self.assertTrue(self.service.blocks_downloads())
            with self.assertRaises(MaintenanceError): self.service.request("refresh")
            self.service.shutdown()
        self.assertFalse(self.service._thread.is_alive())
        self.assertEqual(self.service.status()["phase"], "cancelled")
        with self.assertRaises(MaintenanceError): self.service.request("backup")

    def test_orphan_journal_is_preserved_and_not_treated_as_a_fresh_database(self):
        self.data.mkdir()
        orphan = self.data / "image-history.sqlite3-wal"
        orphan.write_bytes(b"synthetic-orphan-journal")
        report = self.run_operation("compact")
        self.assertEqual(report["error_code"], "database_invalid")
        self.assertEqual(orphan.read_bytes(), b"synthetic-orphan-journal")
        self.assertFalse((self.data / "image-history.sqlite3").exists())

    def test_partial_compaction_preserves_complete_backup_and_all_records(self):
        self.seed()
        before = self.rows(self.data)
        compact = self.service._compact
        def fail_one(item):
            if item["id"] == "media": raise OSError("synthetic compact error")
            return compact(item)
        with patch.object(self.service, "_compact", side_effect=fail_one):
            report = self.run_operation("compact")
        self.assertEqual(report["error_code"], "database_io")
        self.assertEqual(report["phase"], "partial")
        self.assertEqual(self.rows(self.data), before)
        self.assertEqual(self.rows(self.service.backups / report["backup_name"]), before)

    def test_compaction_wal_checkpoint_preserves_records_with_an_open_connection(self):
        self.seed()
        path = self.data / DATABASES["media"][0]
        with closing(sqlite3.connect(path)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            before = self.rows(self.data)
            report = self.run_operation("compact")
            self.assertEqual(report["phase"], "complete", report)
            self.assertEqual(self.rows(self.data), before)
            self.assertEqual(self.rows(self.service.backups / report["backup_name"]), before)

    def test_wal_reader_defers_truncation_without_failing_compaction(self):
        self.seed()
        path = self.data / DATABASES["media"][0]
        with closing(sqlite3.connect(path)) as writer, closing(sqlite3.connect(path)) as reader:
            writer.execute("PRAGMA journal_mode=WAL")
            reader.execute("BEGIN")
            reader.execute("SELECT * FROM extra").fetchall()
            with patch("ssdl.database_maintenance.BUSY_MILLISECONDS", 25):
                report = self.run_operation("compact")
            self.assertEqual(report["phase"], "complete", report)
            row = next(item for item in report["entries"] if item["id"] == "media")
            self.assertTrue(row["checkpoint_busy"])
            self.assertTrue(row["compacted"])
            reader.rollback()

    def test_unicode_space_and_uri_characters_in_root_are_supported(self):
        self.service.shutdown()
        self.data = self.root / "space 圖 & #" / "data"
        self.service = DatabaseMaintenance(self.data)
        self.addCleanup(self.service.shutdown)
        self.seed()
        self.assertEqual(self.run_operation("compact")["phase"], "complete")
        self.assertEqual(len(self.rows(self.data)), 3)


class DatabaseAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ssdl-database-api-")
        self.addCleanup(self.temp.cleanup)
        self.app = create_app(Path(self.temp.name))
        self.app.Handler.log_message = lambda *args: None
        self.addCleanup(self.app.close)
        self.server = BoundedHTTPServer(("127.0.0.1", 0), self.app.Handler)
        self.app.PORT = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(5)

    def request(self, data=None, *, origin=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            headers = {"Content-Type": "application/json"}
            if origin: headers["Origin"] = origin
            connection.request("GET" if data is None else "POST", "/api/databases", None if data is None else json.dumps(data), headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_read_and_write_follow_source_policy_and_validate_confirmation(self):
        self.assertEqual(self.request()[0], 200)
        for data in (None, {"action": "backup"}):
            self.assertEqual(self.request(data, origin="https://foreign.example")[0], 403)
        for data in ({}, {"action": []}, {"action": "delete"}, {"action": "backup", "path": "other.sqlite3"},
                     {"action": "compact", "confirmed": 1}, {"action": "compact", "confirmed": False}):
            self.assertEqual(self.request(data)[0], 400)
        self.assertIsNone(self.app.DATABASES._thread)

    def test_pause_active_guard_busy_and_closing_responses(self):
        self.assertEqual(self.request({"action": "backup"})[0], 409)
        self.app.state.paused = True
        self.app.state.active_id = "synthetic"
        self.assertEqual(self.request({"action": "backup"})[0], 409)
        self.app.state.active_id = None
        self.app.state.jobs["synthetic"] = {"status": "active"}
        self.assertEqual(self.request({"action": "compact", "confirmed": True})[0], 409)
        self.app.state.jobs.clear()
        status, report = self.request({"action": "backup"})
        self.assertEqual(status, 202)
        self.app.DATABASES._thread.join(5)
        self.assertEqual(self.request()[1]["result_code"], "database_no_files")
        self.app.close()
        self.assertEqual(self.request({"action": "refresh"})[0], 503)

    def test_scheduler_does_not_launch_while_maintenance_blocks_downloads(self):
        self.app.state.jobs["fixture"] = {"id": "fixture", "url": "https://example.org/synthetic", "status": "queued"}
        self.app.state.queue.append("fixture")
        def stop_wait(**kwargs): self.app.state.shutdown.set()
        with patch.object(self.app.DATABASES, "blocks_downloads", return_value=True), \
                patch.object(self.app.condition, "wait", side_effect=stop_wait), \
                patch.object(self.app, "run_job") as run:
            self.app._worker_loop()
        run.assert_not_called()
        self.assertEqual(self.app.state.jobs["fixture"]["status"], "queued")

    def test_busy_http_requests_are_rejected_without_starting_second_operation(self):
        began, release = threading.Event(), threading.Event()
        inspect = self.app.DATABASES._inspect
        def gated(key):
            began.set()
            if not release.wait(5): raise AssertionError("Maintenance gate not released")
            return inspect(key)
        try:
            with patch.object(self.app.DATABASES, "_inspect", side_effect=gated):
                self.assertEqual(self.request({"action": "refresh"})[0], 202)
                self.assertTrue(began.wait(5))
                code, report = self.request({"action": "refresh"})
                self.assertEqual(code, 409)
                self.assertEqual(report["error_code"], "database_busy")
                self.assertTrue(self.request()[1]["busy"])
                release.set()
                self.app.DATABASES._thread.join(5)
        finally:
            release.set()
