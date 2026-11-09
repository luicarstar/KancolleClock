"""发布时保留本地实际安装依赖的许可证，不替项目选择许可证。"""
from importlib import metadata
from pathlib import Path
import shutil
import sys


def main():
    destination = Path(sys.argv[1])
    destination.mkdir(parents=True, exist_ok=True)
    for package in ("pygame", "pystray", "Pillow", "six", "PyInstaller"):
        distribution = metadata.distribution(package)
        target = destination / package
        target.mkdir(exist_ok=True)
        # 原始 METADATA 含多行说明；email.Message 重新序列化会错误判定为嵌入邮件头。
        (target / "metadata.txt").write_text(distribution.read_text("METADATA") or "", encoding="utf-8")
        for relative in distribution.files or []:
            if any(part.lower().startswith(("license", "copying", "notice", "lgpl", "gpl", "copyright"))
                   for part in relative.parts):
                source = Path(distribution.locate_file(relative))
                if source.is_file():
                    output = target / str(relative).replace("..", "parent")
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, output)
    print(f"Dependency notices: {destination}")


if __name__ == "__main__":
    main()
