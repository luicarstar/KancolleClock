# -*- coding: utf-8 -*-
import os, sys, json, random, threading, queue, traceback
import argparse
import tempfile
import ctypes
from ctypes import wintypes
from pathlib import Path
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox
from clock_core import (VoiceLibrary, Player, HourScheduler, load_config_file,
                        save_config_file, runtime_root, config_path, application_dir)

BASE = runtime_root()
HOTKEY_LABEL = 'Ctrl+Alt+F10'
HOTKEY_MODIFIERS = 0x0002 | 0x0001  # MOD_CONTROL | MOD_ALT
HOTKEY_VK = 0x79  # VK_F10

class ClockGUI:
    def __init__(self, root, smoke=False):
        self.root = root
        self.smoke = smoke
        self.config = config_path()
        self.closed = False
        self.tray = None
        self.tray_ready = False
        self.hotkey_ready = False
        self.hotkey_thread_id = None
        self.hotkey_error_code = None
        self.scheduler = HourScheduler()
        root.title("舰C整点报时")
        root.geometry("840x640")
        root.minsize(720, 560)
        self.events = queue.Queue()
        self.lib = None
        self.loading = False
        self.cfg = load_config_file(self.config)
        self.enabled = tk.BooleanVar(value=False if smoke else self.cfg.get("enabled", True))
        self.volume = tk.DoubleVar(value=self.cfg.get("volume", .7) * 100)
        self.character = tk.StringVar(value=self.cfg.get("character", "全部角色"))
        self.hour = tk.StringVar(value=f"{datetime.now().hour:02d}")
        self.player = Player(self.volume.get()/100)
        style = ttk.Style()
        style.theme_use("vista" if "vista" in style.theme_names() else "clam")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 21, "bold"))
        style.configure("Clock.TLabel", font=("Consolas", 28))
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="舰C整点报时", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text=f"只播放清单中对应小时的舰C时报；缺失小时保持静音。{HOTKEY_LABEL} 或托盘可恢复隐藏窗口；关闭窗口即退出。" ).pack(anchor="w", pady=(5,16))
        self.time_label = ttk.Label(frame, style="Clock.TLabel")
        self.time_label.pack(anchor="w")
        self.next_label = ttk.Label(frame)
        self.next_label.pack(anchor="w", pady=(0,14))
        bar = ttk.Frame(frame); bar.pack(fill="x")
        ttk.Checkbutton(bar, text="开启整点报时", variable=self.enabled, command=self.save).pack(side="left")
        ttk.Label(bar, text="音量").pack(side="left", padx=(24,8))
        ttk.Scale(bar, from_=0, to=100, variable=self.volume, command=self.volume_changed).pack(side="left", fill="x", expand=True)
        self.vol_label = ttk.Label(bar, width=6); self.vol_label.pack(side="left", padx=8)
        ttk.Label(frame, text="角色筛选（自动报时和试听均生效）").pack(anchor="w", pady=(20,6))
        self.characters = ttk.Combobox(frame, textvariable=self.character, state="readonly", values=["全部角色"])
        self.characters.pack(fill="x")
        self.characters.bind("<<ComboboxSelected>>", lambda e:self.character_changed())
        buttons = ttk.Frame(frame);buttons.pack(fill="x", pady=14)
        ttk.Button(buttons, text="试听当前小时", command=lambda:self.play(datetime.now().hour)).pack(side="left")
        ttk.Combobox(buttons, textvariable=self.hour, values=[f"{h:02d}" for h in range(24)], width=4, state="readonly").pack(side="left", padx=(14,4))
        ttk.Button(buttons, text="点试听", command=lambda:self.play(int(self.hour.get()))).pack(side="left")
        ttk.Button(buttons, text="停止播放", command=self.player.stop).pack(side="left", padx=8)
        self.scan_button = ttk.Button(buttons, text="重新扫描", command=self.scan);self.scan_button.pack(side="right")
        self.stats = ttk.Label(frame, text="正在扫描语音库……", wraplength=760)
        self.stats.pack(anchor="w", pady=(0,8))
        self.log = tk.Text(frame, height=9, wrap="word", state="disabled", font=("Microsoft YaHei UI",10))
        self.log.pack(fill="both", expand=True)
        bottom=ttk.Frame(frame);bottom.pack(fill="x",pady=(12,0))
        ttk.Button(bottom,text="打开语音文件夹",command=self.open_audio_folder).pack(side="left")
        ttk.Button(bottom,text="隐藏到托盘",command=self.toggle_hide).pack(side="left",padx=8)
        ttk.Button(bottom,text="退出",command=self.close).pack(side="right")
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.volume_changed()
        self.scan()
        self.tick()
        self.start_hotkey()
        self.start_tray()

    def save(self):
        self.cfg.update(volume=round(self.volume.get()/100,2), enabled=self.enabled.get(), character=self.character.get())
        try:
            if not self.smoke: save_config_file(self.config,self.cfg)
        except OSError as error:
            self.add_log(f"配置保存失败：{error}")
        self._enabled = self.enabled.get()
        self._volume = self.volume.get()

    def volume_changed(self, value=None):
        self.player.set_volume(self.volume.get()/100)
        self.vol_label.configure(text=f"{self.volume.get():.0f}%")
        if hasattr(self,'save_job'): self.root.after_cancel(self.save_job)
        self.save_job=self.root.after(300,self.save)

    def add_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end",f"[{datetime.now():%H:%M:%S}] {text}\n")
        self.log.see("end");self.log.configure(state="disabled")

    def scan(self):
        if self.loading:return
        self.loading=True;self.scan_button.configure(state="disabled")
        self.stats.configure(text="正在读取清单并校验舰C音频，较大资源库可能需要几十秒……")
        def work():
            try:
                self.events.put(('library',VoiceLibrary(BASE / 'kancolle')))
            except Exception:
                self.events.put(('error',traceback.format_exc()))
        threading.Thread(target=work,daemon=True).start()

    def character_changed(self):
        self.save()
        self.update_stats()

    def update_stats(self):
        if self.lib is None: return
        if self.lib.error:
            self.stats.configure(text=self.lib.error)
            return
        n,c,s,b = self.lib.stats()
        missing = self.lib.missing_hours(self.character.get())
        hours = '、'.join(f'{h:02d}' for h in missing) if missing else '无'
        self.stats.configure(text=f'{s} 个清单角色 · 可用时报 {n} 条 · 总覆盖 {c}/24 小时 · 跳过无效/缺失条目 {b} 个\n当前筛选缺失小时：{hours}；缺失时跳过，保持静音。')

    def pool(self,h):
        return self.lib.pool(h,self.character.get()) if self.lib else []

    def open_audio_folder(self):
        folder = BASE / 'kancolle'
        if folder.is_dir():
            try: os.startfile(folder)
            except OSError as error: self.add_log(f'打开文件夹失败：{error}')
        else:
            self.add_log(f'尚未放置音频文件夹：{folder}')

    def play(self,h):
        if self.loading:
            self.add_log("语音库扫描中，请稍候。")
            return
        pool=self.pool(h)
        if not pool:
            self.add_log(f"{h:02d}:00 · {self.character.get()} 无可用对应小时时报，已跳过（保持静音）。")
            return
        ship,path,text,section=random.choice(pool)
        if self.player.play(path):
            self.add_log(f"{h:02d}:00 · 时报 · {ship}\n{text or Path(path).name}")
        else:
            self.add_log(f"播放失败：{path}")
            messagebox.showerror("播放失败","无法播放所选语音，请检查音频设备或重新扫描。")

    def tick(self):
        now=datetime.now()
        self.time_label.configure(text=now.strftime('%H:%M:%S'))
        nxt=now.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)
        mins,secs=divmod(int((nxt-now).total_seconds()),60)
        self.next_label.configure(text=f"下次报时 {nxt:%H:%M} · 还有 {mins} 分 {secs} 秒" if self.enabled.get() else "整点报时已暂停，仍可手动试听")
        while not self.events.empty():
            kind,value=self.events.get()
            if kind=='toggle':
                self.toggle_hide();continue
            if kind=='action':
                self.tray_action(value)
                if self.closed:return
                continue
            if kind=='log':
                self.add_log(value);continue
            self.loading=False;self.scan_button.configure(state="normal")
            if kind=='library':
                self.lib=value
                choices=['全部角色']+sorted(value.ships)
                self.characters.configure(values=choices)
                if self.character.get() not in choices:self.character.set('全部角色')
                self.update_stats()
                self.add_log(value.error or ('语音清单校验完成。' if self.player.ok else '音频设备初始化失败，请检查输出设备后重启。'))
            else:
                self.stats.configure(text='扫描失败');self.add_log(value)
        if self.scheduler.claim(now, enabled=self.enabled.get(), ready=not self.loading and self.lib is not None):
            self.play(now.hour)
        if not self.closed: self.tick_job=self.root.after(500,self.tick)

    def toggle_hide(self):
        if self.root.state()=='withdrawn':
            self.root.deiconify();self.root.lift();self.root.focus_force()
            self.add_log('窗口已恢复显示。')
        else:
            if not (self.hotkey_ready or self.tray_ready):
                self.add_log('托盘和全局热键尚未就绪，窗口保持显示。');return
            self.root.withdraw()
            self.add_log(f'窗口已隐藏，整点报时继续；按 {HOTKEY_LABEL} 恢复显示。')

    def start_hotkey(self):
        if os.name != 'nt': return
        def work():
            user32=ctypes.WinDLL('user32',use_last_error=True)
            msg=wintypes.MSG()
            user32.PeekMessageW(ctypes.byref(msg),None,0,0,0)
            self.hotkey_thread_id=ctypes.windll.kernel32.GetCurrentThreadId()
            ctypes.set_last_error(0)
            if not user32.RegisterHotKey(None,1,HOTKEY_MODIFIERS,HOTKEY_VK):
                self.hotkey_error_code=ctypes.get_last_error()
                reason='热键已被其他程序占用' if self.hotkey_error_code==1409 else ctypes.FormatError(self.hotkey_error_code).strip()
                self.events.put(('log',f'{HOTKEY_LABEL} 注册失败（Windows {self.hotkey_error_code}：{reason}）；可使用托盘恢复窗口。'))
                return
            self.hotkey_error_code=0
            self.hotkey_ready=True
            try:
                while user32.GetMessageW(ctypes.byref(msg),None,0,0)>0:
                    if msg.message==0x0312: self.events.put(('toggle',None))
            finally:
                self.hotkey_ready=False
                user32.UnregisterHotKey(None,1)
        self.hotkey_thread=threading.Thread(target=work,daemon=True)
        self.hotkey_thread.start()

    def start_tray(self):
        self._enabled=self.enabled.get()
        self._volume=self.volume.get()
        def work():
            try:
                import pystray
                from pystray import MenuItem as Item, Menu
                from PIL import Image, ImageDraw
                image=Image.new('RGB',(64,64),(28,38,66))
                draw=ImageDraw.Draw(image)
                draw.ellipse([8,8,56,56],outline=(235,240,255),width=3)
                draw.line([32,32,32,17],fill=(235,240,255),width=3)
                draw.line([32,32,45,39],fill=(255,196,92),width=3)
                def action(name):
                    return lambda icon,item:self.events.put(('action',name))
                hours=Menu(*[Item(f'{h:02d}:00',action(('hour',h))) for h in range(24)])
                menu=Menu(
                    Item('显示/隐藏窗口',action('toggle'),default=True),
                    Item('开启整点报时',action('enabled'),checked=lambda item:self._enabled),
                    Menu.SEPARATOR,
                    Item('试听当前小时',action('play')),
                    Item('试听指定小时',hours),
                    Item('停止播放',action('stop')),
                    Item('音量 +10%',action(('volume',10))),
                    Item('音量 -10%',action(('volume',-10))),
                    Item('重新扫描',action('scan')),
                    Menu.SEPARATOR,
                    Item('退出',action('quit')))
                self.tray=pystray.Icon('KancolleClock',image,'舰C整点报时',menu)
                def setup(icon):
                    if self.closed: icon.stop();return
                    icon.visible=True
                    self.tray_ready=True
                self.tray.run(setup=setup)
            except Exception as error:
                self.events.put(('log',f'托盘不可用：{error}；仍可用 {HOTKEY_LABEL} 隐藏/恢复。'))
            finally: self.tray_ready=False
        self.tray_thread=threading.Thread(target=work,daemon=True)
        self.tray_thread.start()

    def tray_action(self,action):
        if action=='quit': self.close();return
        if action=='toggle': self.toggle_hide()
        elif action=='enabled': self.enabled.set(not self.enabled.get());self.save()
        elif action=='play': self.play(datetime.now().hour)
        elif action=='stop': self.player.stop()
        elif action=='scan': self.scan()
        elif isinstance(action,tuple) and action[0]=='hour': self.play(action[1])
        elif isinstance(action,tuple) and action[0]=='volume':
            self.volume.set(max(0,min(100,self.volume.get()+action[1])))
            self.volume_changed()
        if self.tray: self.tray.update_menu()

    def close(self):
        if self.closed: return
        self.closed=True
        for name in ('save_job','tick_job'):
            if hasattr(self,name): self.root.after_cancel(getattr(self,name))
        try: self.save()
        finally:
            self.player.close()
            if self.tray: self.tray.stop()
            if self.hotkey_thread_id:
                ctypes.windll.user32.PostThreadMessageW(self.hotkey_thread_id,0x0012,0,0)
                self.hotkey_thread.join(timeout=0.5)
            self.root.destroy()


def main():
    parser=argparse.ArgumentParser(description='舰C整点报时')
    parser.add_argument('--diagnose',type=Path,help='写入无声诊断 JSON 后退出')
    parser.add_argument('--smoke-test-report',type=Path,help='静音 GUI 自检并自动退出')
    args=parser.parse_args()
    if args.diagnose:
        lib=VoiceLibrary(BASE/'kancolle')
        args.diagnose.write_text(json.dumps(dict(application_dir=str(application_dir()),
            resource_root=str(BASE),config=str(config_path()),frozen=bool(getattr(sys,'frozen',False)),
            stats=lib.stats(),error=lib.error,hotkey_label=HOTKEY_LABEL,
            hotkey_modifiers=HOTKEY_MODIFIERS,hotkey_vk=HOTKEY_VK),ensure_ascii=False,indent=2),encoding='utf-8')
        return
    temporary=None
    if args.smoke_test_report:
        os.environ['SDL_AUDIODRIVER']='dummy'
        temporary=tempfile.TemporaryDirectory(prefix='kancolle-smoke-')
        os.environ['KANCOLLE_CLOCK_CONFIG_DIR']=temporary.name
    root=tk.Tk()
    app=ClockGUI(root,smoke=bool(args.smoke_test_report))
    if args.smoke_test_report:
        attempts=[0]
        def finish():
            attempts[0]+=1
            if (app.loading or not app.tray_ready) and attempts[0]<120:
                root.after(250,finish);return
            result=dict(gui_started=True,scan_finished=not app.loading,
                        audio_driver=os.environ.get('SDL_AUDIODRIVER'),player_ok=app.player.ok,
                        scheduling_enabled=app.enabled.get(),resource_root=str(BASE),
                        tray_ready=app.tray_ready,hotkey_ready=app.hotkey_ready,
                        hotkey_error_code=app.hotkey_error_code,
                         hotkey_label=HOTKEY_LABEL,hotkey_modifiers=HOTKEY_MODIFIERS,hotkey_vk=HOTKEY_VK,
                        config=str(app.config),library_error=app.lib.error if app.lib else 'scan failed')
            args.smoke_test_report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            app.close()
        root.after(750,finish)
    root.mainloop()
    if temporary: temporary.cleanup()


if __name__=='__main__':
    main()
