"""验证 GUI 的播放边界；不创建窗口、不初始化 mixer、不播放声音。"""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from clock_core import VoiceLibrary

loader = SourceFileLoader("tested_clock_gui", str(Path(__file__).resolve().parents[1] / "clock_gui.pyw"))
spec = spec_from_loader(loader.name, loader)
gui = module_from_spec(spec)
loader.exec_module(gui)


class PlaybackBoundaryTests(unittest.TestCase):
    def app(self, library, character="全部角色"):
        app = object.__new__(gui.ClockGUI)
        app.lib = library
        app.loading = False
        app.character = SimpleNamespace(get=lambda: character)
        app.player = SimpleNamespace(play=Mock(return_value=True))
        app.add_log = Mock()
        return app

    def test_no_library_and_missing_hour_never_call_player(self):
        app = self.app(None)
        app.play(17)
        app.player.play.assert_not_called()
        app.add_log.assert_called_once()

    def test_selected_character_never_falls_back_to_available_other_character(self):
        library = object.__new__(VoiceLibrary)
        library.hourly = {17: [("瑞凤", "allowed.mp3", "", "时报")]}
        app = self.app(library, "金刚")
        app.play(17)
        app.player.play.assert_not_called()
        self.assertIn("保持静音", app.add_log.call_args.args[0])

    def test_correct_hour_uses_manifest_path_and_loading_blocks_playback(self):
        library = object.__new__(VoiceLibrary)
        library.hourly = {17: [("瑞凤", "瑞凤-1700.mp3", "", "时报")]}
        app = self.app(library, "瑞凤")
        app.play(17)
        app.player.play.assert_called_once_with("瑞凤-1700.mp3")
        app.player.play.reset_mock()
        app.loading = True
        app.play(17)
        app.player.play.assert_not_called()

    def test_cannot_hide_without_any_restore_mechanism(self):
        app = self.app(None)
        app.root = SimpleNamespace(state=lambda: "normal", withdraw=Mock())
        app.hotkey_ready = app.tray_ready = False
        app.toggle_hide()
        app.root.withdraw.assert_not_called()

    def test_hotkey_failure_reports_windows_error_and_does_not_claim_success(self):
        app = self.app(None)
        app.events = queue.Queue()
        app.hotkey_ready = False
        api = Mock()
        api.RegisterHotKey.return_value = 0
        with patch.object(gui.ctypes, "WinDLL", return_value=api), \
             patch.object(gui.ctypes, "get_last_error", return_value=1409):
            app.start_hotkey()
            app.hotkey_thread.join(timeout=1)
        self.assertFalse(app.hotkey_ready)
        self.assertEqual(app.hotkey_error_code, 1409)
        message = app.events.get_nowait()[1]
        self.assertIn("1409", message)
        self.assertIn("Ctrl+Alt+F10", message)
        self.assertNotIn("F8", message)
        api.UnregisterHotKey.assert_not_called()

    def test_hotkey_success_unregisters_when_message_pump_exits(self):
        app = self.app(None)
        app.events = queue.Queue()
        app.hotkey_ready = False
        api = Mock()
        api.RegisterHotKey.return_value = 1
        messages = iter((1, 0))
        def pump(message, *_):
            message._obj.message = 0x0312  # WM_HOTKEY keeps toggling the window.
            return next(messages)
        api.GetMessageW.side_effect = pump
        with patch.object(gui.ctypes, "WinDLL", return_value=api):
            app.start_hotkey()
            app.hotkey_thread.join(timeout=1)
        self.assertEqual(app.hotkey_error_code, 0)
        api.RegisterHotKey.assert_called_once_with(None, 1, 0x0003, 0x79)
        api.UnregisterHotKey.assert_called_once_with(None, 1)
        self.assertFalse(app.hotkey_ready)
        self.assertEqual(app.events.get_nowait(), ("toggle", None))

    def test_hide_reports_new_restore_shortcut_and_restore_still_works(self):
        app = self.app(None)
        app.root = Mock()
        app.root.state.return_value = "normal"
        app.hotkey_ready, app.tray_ready = True, False
        app.toggle_hide()
        app.root.withdraw.assert_called_once_with()
        message = app.add_log.call_args.args[0]
        self.assertIn("Ctrl+Alt+F10", message)
        self.assertNotIn("F8", message)
        app.root.state.return_value = "withdrawn"
        app.toggle_hide()
        app.root.deiconify.assert_called_once_with()
        app.root.focus_force.assert_called_once_with()
        app.player.play.assert_not_called()


if __name__ == "__main__":
    unittest.main()
