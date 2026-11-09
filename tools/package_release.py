"""资源就绪后校验、整合外置音频，并生成源码/Windows 压缩包。"""
import argparse
from pathlib import Path
import shutil
import sys
import zipfile

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from clock_core import VoiceLibrary


def archive_tree(root, output, source=False):
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if not path.is_file():
                continue
            if source and (set(relative.parts) & {"kancolle", "__pycache__", ".git", ".venv", "build", "dist"}
                           or path.suffix in {".pyc", ".pyo", ".log", ".zip"}
                           or path.name in {"config.json", "clock_config.json"}):
                continue
            archive.write(path, Path(root.name) / relative)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    args = parser.parse_args()
    release = args.release.resolve()
    if release == SOURCE or release.is_relative_to(SOURCE):
        parser.error("Windows 成品必须位于源码目录之外")
    if not (release / "KancolleClock.exe").is_file():
        parser.error("先运行 build_windows.ps1 构建 Windows EXE")
    library = VoiceLibrary(SOURCE / "kancolle")
    count, covered, characters, broken = library.stats()
    if library.error or broken or not count:
        parser.error(f"资源未就绪：{library.error or f'{broken} 个无效条目，{count} 个可用文件'}")
    report = SOURCE / "RESOURCE_REPORT.md"
    if not report.is_file():
        parser.error("缺少资源整理报告 RESOURCE_REPORT.md")
    # 先通过整库校验，再复制；不移动、修改资源代理拥有的源码资源。
    for items in library.hourly.values():
        for _, filename, _, _ in items:
            source = Path(filename)
            output = release / source.relative_to(SOURCE)
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
    for name in ("audio_manifest.json", "RESOURCE_REPORT.md", "README.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(SOURCE / name, release / name)
    verified = VoiceLibrary(release / "kancolle")
    if verified.error or verified.broken or verified.stats() != library.stats():
        raise RuntimeError("Windows 外置资源复制后校验失败，未压缩")
    source_zip = SOURCE.parent / "KancolleClock-Source.zip"
    windows_zip = SOURCE.parent / "KancolleClock-Windows.zip"
    archive_tree(SOURCE, source_zip, source=True)
    archive_tree(release, windows_zip)
    print(f"资源验证：{count} 条 / {covered}/24 小时 / {characters} 个角色 / 0 个无效条目")
    print(f"源码包（不含音频）：{source_zip}")
    print(f"Windows 成品：{windows_zip}")


if __name__ == "__main__":
    main()
