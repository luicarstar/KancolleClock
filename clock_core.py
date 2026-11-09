"""舰C报时核心；索引和配置可在无音频设备的环境导入。

Player 与配置原子保存沿用现有语音报时程序的合适实现。
"""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import re
import sys
import tempfile

DEFAULT_VOLUME = 0.7
ALL_CHARACTERS = "全部角色"
MP3_SIGS = (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa", b"\xff\xe3")


def application_dir():
    # PyInstaller _MEIPASS 是内部依赖目录，外置资源始终跟随 exe。
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def runtime_root():
    configured = os.environ.get("AGENT_CLOCK_HOME")
    if configured:
        path = Path(configured).expanduser()
        return (path if path.is_absolute() else application_dir() / path).resolve()
    return application_dir()


def config_path():
    if os.environ.get("KANCOLLE_CLOCK_CONFIG_DIR"):
        return Path(os.environ["KANCOLLE_CLOCK_CONFIG_DIR"]).expanduser().resolve() / "config.json"
    if os.environ.get("LOCALAPPDATA"):
        folder = Path(os.environ["LOCALAPPDATA"])
    elif os.name == "nt":
        folder = Path.home() / "AppData" / "Local"
    else:
        folder = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return folder / "KancolleClock" / "config.json"


def is_playable(path):
    try:
        if path.stat().st_size < 2000:
            return False
        with path.open("rb") as stream:
            head = stream.read(4)
        return head[:3] == b"ID3" or head[:2] in MP3_SIGS or head in (b"RIFF", b"OggS")
    except OSError:
        return False


def sha256_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class VoiceLibrary:
    """清单是唯一许可集合；无清单、无对应小时均保持静音。"""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.manifest_path = self.root.parent / "audio_manifest.json"
        self.hourly = {hour: [] for hour in range(24)}
        self.ships = set()
        self.broken = 0
        self.error = ""
        self.scan()

    def scan(self):
        self.hourly = {hour: [] for hour in range(24)}
        self.ships.clear()
        self.broken = 0
        self.error = ""
        try:
            with self.manifest_path.open(encoding="utf-8-sig") as stream:
                manifest = json.load(stream)
            if (not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int
                    or manifest["schema_version"] != 1 or not isinstance(manifest.get("files"), list)):
                raise ValueError("需要 schema_version: 1 和 files 数组")
        except (OSError, ValueError) as error:
            self.error = f"资源清单不可用：{error}。请放置 audio_manifest.json 和配套 kancolle 文件夹。"
            return
        seen = set()
        for entry in manifest["files"]:
            try:
                if not isinstance(entry, dict):
                    raise ValueError("记录必须为对象")
                relative, hour, character, digest = (entry.get(key) for key in
                                                      ("path", "hour", "character", "sha256"))
                if (not isinstance(relative, str) or "\\" in relative or ":" in relative
                        or any(part in ("", ".", "..") for part in relative.split("/"))):
                    raise ValueError("非法资源路径")
                parts = PurePosixPath(relative).parts
                if len(parts) < 2 or parts[0] != "kancolle":
                    raise ValueError("资源必须位于 kancolle")
                if type(hour) is not int or not 0 <= hour <= 23:
                    raise ValueError("非法小时")
                if not isinstance(character, str) or not character.strip() or character == ALL_CHARACTERS:
                    raise ValueError("非法角色")
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                    raise ValueError("缺少有效 SHA256")
                path = (self.root.parent / relative).resolve()
                if not path.is_relative_to(self.root) or path.suffix.lower() not in (".mp3", ".ogg", ".wav"):
                    raise ValueError("非法音频路径")
                if path in seen:
                    raise ValueError("重复资源记录")
                seen.add(path)
                self.ships.add(character)
                if not is_playable(path) or sha256_file(path).lower() != digest.lower():
                    raise ValueError("音频缺失、损坏或摘要不符")
                self.hourly[hour].append((character, str(path), "", "时报"))
            except (OSError, ValueError):
                self.broken += 1

    def pool(self, hour, character=ALL_CHARACTERS):
        return [item for item in self.hourly.get(hour, [])
                if character == ALL_CHARACTERS or item[0] == character]

    def missing_hours(self, character=ALL_CHARACTERS):
        return [hour for hour in range(24) if not self.pool(hour, character)]

    def pick(self, hour, character=ALL_CHARACTERS):
        pool = self.pool(hour, character)
        return random.choice(pool) if pool else None

    def stats(self):
        return sum(map(len, self.hourly.values())), 24 - len(self.missing_hours()), len(self.ships), self.broken


class HourScheduler:
    def __init__(self):
        self.last_slot = None

    def claim(self, now, enabled=True, ready=True):
        slot = now.strftime("%Y-%m-%d %H")
        if enabled and ready and now.minute == 0 and slot != self.last_slot:
            self.last_slot = slot
            return True
        return False


def load_config_file(path):
    try:
        with Path(path).open(encoding="utf-8-sig") as source:
            cfg = json.load(source)
        if not isinstance(cfg, dict):
            return {}
    except (OSError, ValueError):
        return {}
    try:
        volume = float(cfg.get("volume", DEFAULT_VOLUME))
        cfg["volume"] = max(0., min(1., volume)) if math.isfinite(volume) else DEFAULT_VOLUME
    except (TypeError, ValueError):
        cfg["volume"] = DEFAULT_VOLUME
    if not isinstance(cfg.get("enabled", True), bool):
        cfg["enabled"] = True
    if not isinstance(cfg.get("character", ALL_CHARACTERS), str):
        cfg["character"] = ALL_CHARACTERS
    return cfg


def save_config_file(path, cfg):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".clock-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(cfg, output, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


class Player:
    def __init__(self, volume=DEFAULT_VOLUME):
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        self.mixer = pygame.mixer
        self.error = ""
        try:
            self.mixer.init()
            self.ok = True
        except Exception as error:
            self.ok = False
            self.error = str(error)
        self.volume = volume

    def play(self, path):
        if not self.ok:
            return False
        try:
            self.mixer.music.load(path)
            self.mixer.music.set_volume(self.volume)
            self.mixer.music.play()
            return True
        except Exception as error:
            self.error = str(error)
            return False

    def stop(self):
        if self.ok:
            self.mixer.music.stop()

    def set_volume(self, value):
        self.volume = max(0., min(1., round(value, 2)))
        if self.ok:
            self.mixer.music.set_volume(self.volume)

    def close(self):
        if self.ok:
            self.stop()
            self.mixer.quit()
