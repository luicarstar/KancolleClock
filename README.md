# 舰C整点报时

Windows 桌面整点语音报时，只使用舰队Collection（舰C）**对应小时**的时报。支持角色筛选、00～23 点试听、音量、停止播放、Ctrl+Alt+F10 全局隐藏/恢复及托盘菜单。关闭主窗口或托盘“退出”会结束程序；隐藏窗口继续报时。

本次配套资源共 **242 个角色、5885 条时报，覆盖全部 24 小时**；MP3 总计 **505,206,428 字节（约 482 MiB）**。每个角色的小时覆盖情况以界面筛选后的统计为准。用户尚未指定代码许可证。

如果 Ctrl+Alt+F10 已被其他程序占用，日志会显示 Windows 1409；报时、试听和托盘操作仍正常，可通过托盘菜单显示/隐藏窗口，也可使用窗口按钮。程序不会关闭其他进程或抢占热键。

## Windows 成品

解压完整 `KancolleClock-Windows` 文件夹，双击 `KancolleClock.exe`。不需要安装 Python，必须保留 `_internal/`。音频外置，不嵌入 EXE：

```text
KancolleClock-Windows/
  KancolleClock.exe
  _internal/
  audio_manifest.json
  RESOURCE_REPORT.md
  kancolle/
    角色/音频文件.mp3
```

源码包可以不带大音频；需要取得配套资源包，把 `audio_manifest.json` 和 `kancolle/` 放到程序根目录。文件和清单必须配套：程序检查文件头和 SHA256，缺失、损坏及摘要不符的条目会跳过。资源添加后点“重新扫描”。

**无清单不播放；当前小时或选定角色没有可用时报时，跳过并保持静音。** 界面显示缺失小时和无效条目数量，不使用普通台词、不借用其他小时或角色。只接受清单明确列出的音频，即使文件名含数字或“时报”，未列入清单也不会播放。瑞凤 `-1700` 等不含“时报”的文件，只要清单认定为 17 点就能正确使用。

自动报时按电脑本地时间，在整点分钟内触发，同一日期/小时只触发一次。暂停时仍可试听；休眠后若已错过整点分钟，不补播。扫描期间暂停自动触发；如扫描在整点分钟内完成，则允许触发该小时。试听不改变自动报时状态。重复启动会产生独立实例，请只运行一份。

## 源码运行

需要带 Tk 的 Python 3.11 或更新版本（本次构建使用本机 Python），在项目目录执行：

```powershell
python -m pip install -r requirements.txt
.\launch.ps1
# 或双击 launch.cmd；也可直接 python clock_gui.pyw
```

默认资源根目录是源码目录，冻结程序则是 EXE 所在目录，与启动时的工作目录无关。兼容环境变量 `AGENT_CLOCK_HOME`，指定同时包含清单和 `kancolle/` 的目录；相对值以程序目录为基准。不设置时无需任何本机绝对路径。

配置默认保存到 `%LOCALAPPDATA%\KancolleClock\config.json`，不要求程序文件夹可写。可通过 `KANCOLLE_CLOCK_CONFIG_DIR` 指定其他可写配置目录。配置损坏会使用默认值，保存采用临时文件和原子替换。程序不会读写旧安装目录的配置。

## 清单格式

根目录 `audio_manifest.json`：

```json
{
  "schema_version": 1,
  "files": [
    {
      "path": "kancolle/角色/角色-1700.mp3",
      "hour": 17,
      "character": "角色",
      "sha256": "文件的64位SHA256十六进制摘要",
      "source_url": "可选的素材来源URL"
    }
  ]
}
```

`path` 必须是以 `kancolle/` 开头的正斜杠相对路径，`hour` 为整数 0～23。角色和小时由清单指定，不依赖文件名。清单应由已核对用途的资源整理流程生成；程序本身不联网补音频。

## 测试与构建

```powershell
python -m unittest discover -s tests -v
python -m pip install -r requirements-build.txt
.\build_windows.ps1
# 可选 -Python '<Python解释器路径>' -OutputDirectory '<成品输出目录>'
```

构建脚本生成 Windows onedir，默认成品位于源码目录同级 `KancolleClock-Windows`；缓存位于系统临时目录，可用 `-WorkDirectory` 改写。脚本只构建程序，不自动整合大音频。Windows 成品应在 Windows 上构建，当前版本不含自动更新、自启动、网络下载或签名。

重复构建会在路径校验通过后清空并替换源码同级的 `KancolleClock-Windows`，其中此前整合的音频也需重新整合；请勿把个人文件存入该成品目录。为防止误删，其他已存在的自定义目录会被拒绝替换；构建缓存与成品目录不可重叠，路径祖先不可为 junction/symlink。可先用 `-ValidatePathsOnly` 无修改地检查路径。

资源整理完成、清单和 `RESOURCE_REPORT.md` 就绪后，可执行 `python tools/package_release.py --release ../KancolleClock-Windows`。该命令先校验全部清单音频，复制清单内文件，再校验成品并生成同级源码 ZIP（不含音频）和完整 Windows ZIP；任何缺失或摘要不符都会中止打包。整库哈希校验和压缩可能需要一段时间。

单元测试不初始化音频。以下诊断模式也不会播放声音，并会自动退出；报告路径请使用存在的目录：

```powershell
python clock_gui.pyw --diagnose "$env:TEMP\kancolle-diagnose.json"
python clock_gui.pyw --smoke-test-report "$env:TEMP\kancolle-smoke.json"
# 成品 EXE 支持同样两个参数；smoke 模式使用 SDL dummy 音频并关闭自动报时。
```

源码只整理舰C模式，不包含碧蓝航线或普通台词回退。代码许可证尚未由所有者指定；素材来源及再分发权利需单独确认，见 `THIRD_PARTY_NOTICES.md` 与资源包报告。此目录尚未自动上传 GitHub。
