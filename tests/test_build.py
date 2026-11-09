"""只调用构建脚本的无副作用路径检查，不构建、不删除。"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
SHELL = shutil.which("pwsh") or shutil.which("powershell")


@unittest.skipUnless(SHELL, "需要 PowerShell")
class BuildPathTests(unittest.TestCase):
    def validate(self, release, cache):
        return subprocess.run([SHELL, "-NoProfile", "-File", str(PROJECT / "build_windows.ps1"),
            "-OutputDirectory", str(release), "-WorkDirectory", str(cache), "-ValidatePathsOnly"],
            capture_output=True, timeout=15)

    def test_known_sibling_release_is_allowed_without_modification(self):
        result = self.validate(PROJECT.parent / "KancolleClock-Windows", PROJECT.parent.parent / "work" / "build-test")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_ancestor_and_overlapping_cache_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for release, cache in [(PROJECT, Path(folder)), (PROJECT.parent, Path(folder)),
                                    (PROJECT.parent / "KancolleClock-Windows", PROJECT / "cache"),
                                    (PROJECT.parent / "KancolleClock-Windows", PROJECT.parent / "KancolleClock-Windows" / "cache")]:
                with self.subTest(release=release, cache=cache):
                    self.assertNotEqual(self.validate(release, cache).returncode, 0)

    def test_unrelated_existing_directory_is_rejected_and_preserved(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as cache:
            sentinel = Path(folder) / "preserve.txt"
            sentinel.write_text("keep", encoding="utf-8")
            self.assertNotEqual(self.validate(folder, cache).returncode, 0)
            self.assertEqual(sentinel.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
