import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

import clock_core as core


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entries = []

    def add(self, filename, hour, character="瑞凤"):
        path = self.root / "kancolle" / character / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ID3" + b"\0" * 2100)
        self.entries.append(dict(path=path.relative_to(self.root).as_posix(),
                                 hour=hour, character=character,
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        return path

    def library(self):
        (self.root / "audio_manifest.json").write_text(json.dumps(
            dict(schema_version=1, files=self.entries)), encoding="utf-8")
        return core.VoiceLibrary(self.root / "kancolle")

    def test_manifest_recognizes_0_23_and_zuihou_17_without_label(self):
        for hour in (0, 23, 17):
            self.add(f"瑞凤-{hour:02d}00.mp3", hour)
        lib = self.library()
        self.assertEqual([len(lib.hourly[h]) for h in (0, 23, 17)], [1, 1, 1])
        self.assertEqual(lib.missing_hours(), [h for h in range(24) if h not in (0, 23, 17)])

    def test_unlisted_battle_and_numbered_files_are_never_used(self):
        path = self.add("战斗-1700.mp3", 17)
        self.entries.clear()
        lib = self.library()
        self.assertTrue(path.exists())
        self.assertEqual(lib.pool(17), [])

    def test_missing_manifest_does_not_scan_or_fallback(self):
        self.add("瑞凤-1700.mp3", 17)
        lib = core.VoiceLibrary(self.root / "kancolle")
        self.assertIn("清单", lib.error)
        self.assertEqual(lib.pool(17), [])

    def test_missing_audio_and_bad_digest_are_skipped(self):
        missing = self.add("missing.mp3", 0)
        bad = self.add("bad.mp3", 23)
        missing.unlink()
        bad.write_bytes(b"ID3" + b"x" * 2100)
        lib = self.library()
        self.assertEqual(lib.pool(0), [])
        self.assertEqual(lib.pool(23), [])
        self.assertEqual(lib.broken, 2)
        self.assertIn("瑞凤", lib.ships)

    def test_character_filter_never_uses_another_hour_or_character(self):
        self.add("a.mp3", 17, "瑞凤")
        self.add("b.mp3", 23, "金刚")
        lib = self.library()
        self.assertEqual(len(lib.pool(17, "瑞凤")), 1)
        self.assertEqual(lib.pool(17, "金刚"), [])
        self.assertEqual(lib.missing_hours("金刚"), list(range(23)))

    def test_rejects_traversal_absolute_other_resource_and_invalid_hour(self):
        self.add("ok.mp3", 17)
        valid = self.entries.pop()
        for path, hour in [("kancolle/../outside.mp3", 17),
                           ("C:/outside.mp3", 17), ("blhx/a.mp3", 17),
                           (valid["path"], 24), (valid["path"], True),
                           ("kancolle\\瑞凤\\ok.mp3", 17)]:
            self.entries.append(dict(valid, path=path, hour=hour))
        lib = self.library()
        self.assertEqual(lib.pool(17), [])
        self.assertEqual(lib.broken, 6)

    def test_invalid_schema_or_malformed_files_does_not_fallback(self):
        for doc in ({"schema_version": 2, "files": []},
                    {"schema_version": 1, "files": {}}, []):
            (self.root / "audio_manifest.json").write_text(json.dumps(doc), encoding="utf-8")
            lib = core.VoiceLibrary(self.root / "kancolle")
            self.assertTrue(lib.error)
            self.assertEqual(lib.pool(0), [])

    def test_library_independent_of_working_directory(self):
        self.add("a.mp3", 0)
        self.library()
        previous = Path.cwd()
        try:
            os.chdir(self.root.parent)
            self.assertEqual(len(core.VoiceLibrary(self.root / "kancolle").pool(0)), 1)
        finally:
            os.chdir(previous)


class RuntimeTests(unittest.TestCase):
    def test_frozen_resources_are_next_to_exe_not_meipass(self):
        with patch.object(core.sys, "frozen", True, create=True), \
             patch.object(core.sys, "executable", str(Path("release") / "KancolleClock.exe")):
            self.assertEqual(core.application_dir(), Path("release").resolve())

    def test_source_runtime_and_legacy_environment_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(core.runtime_root(), Path(core.__file__).resolve().parent)
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {"AGENT_CLOCK_HOME": folder}):
            self.assertEqual(core.runtime_root(), Path(folder).resolve())

    def test_user_config_atomic_roundtrip_and_tolerant_loading(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {"LOCALAPPDATA": folder}, clear=True):
            path = core.config_path()
            self.assertEqual(path, Path(folder) / "KancolleClock" / "config.json")
            core.save_config_file(path, dict(volume=0.3, enabled=False, character="瑞凤"))
            self.assertEqual(core.load_config_file(path)["character"], "瑞凤")
            path.write_text('{"volume":"bad", "enabled":"bad"}', encoding="utf-8")
            cfg = core.load_config_file(path)
            self.assertEqual(cfg["volume"], 0.7)
            self.assertIs(cfg["enabled"], True)
            path.write_text("broken", encoding="utf-8")
            self.assertEqual(core.load_config_file(path), {})
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_schedule_one_chime_per_hour_no_late_catchup_and_midnight(self):
        schedule = core.HourScheduler()
        t = datetime(2026, 11, 9, 23, 0, 5)
        self.assertFalse(schedule.claim(t, enabled=False))
        self.assertFalse(schedule.claim(t, ready=False))
        self.assertTrue(schedule.claim(t))
        self.assertFalse(schedule.claim(t.replace(second=50)))
        self.assertFalse(schedule.claim(t.replace(minute=1)))
        self.assertTrue(schedule.claim(datetime(2026, 11, 10, 0, 0)))


if __name__ == "__main__":
    unittest.main()
