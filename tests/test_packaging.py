from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = spec_from_file_location("package_release", Path(__file__).resolve().parents[1] / "tools" / "package_release.py")
packaging = module_from_spec(spec)
spec.loader.exec_module(packaging)


class PackagingTests(unittest.TestCase):
    def test_source_archive_excludes_audio_cache_and_local_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "KancolleClock"
            for name in ("README.md", "clock_core.py", "audio_manifest.json", "config.json",
                         "kancolle/瑞凤/瑞凤-1700.mp3", "__pycache__/clock_core.pyc"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture", encoding="utf-8")
            output = Path(folder) / "source.zip"
            packaging.archive_tree(root, output, source=True)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), {"KancolleClock/README.md",
                    "KancolleClock/clock_core.py", "KancolleClock/audio_manifest.json"})
                self.assertIsNone(archive.testzip())


if __name__ == "__main__":
    unittest.main()
