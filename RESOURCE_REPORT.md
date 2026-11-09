# 舰队Collection 时报资源核对报告

仅收录整点时报用途音频。原目录 source-audio 只读保留；未运行报时 GUI。
核对边界为现有329角色台词索引；不声称这些索引覆盖游戏全部角色及最新资料。

- 原索引：329 份，17733 条路径；原MP3 17,621条。
- 原清单112条路径缺失：时报7条、普通台词105条。普通台词缺失不下载。
- 复核时报应有5,885条；本地5,878条；新增下载7条；未恢复时报0条。
- 最终音频：5,885 条，505,206,428 字节（481.80 MiB）。
- 242个角色有时报，全部覆盖24小时；同角色同小时的改造差分/旧版保留。

## 分类与漏识别纠正

以台词索引的场景/用途标签为首要证据，并核对HH00文件标识。不能仅凭父目录“时报”或普通台词提到时间就收录。
- 原函数识别5,877条；补收瑞凤/瑞凤改二/044_一七〇〇时_355-1700.mp3（17时），本地共5,878条。
- 朝潮/时报目录的补给085a-Resupply与放置085a-Idle是普通台词，明确排除。
- 保留挪威“时报イ”、熊野丸“时报！”、雾岛“时报（舊）”等确属时报的变体。
- 所有17,733条索引均核对；额外查找非时报场景中HHMM档名及明确时间正文，未发现其他漏收时报。
- 49条索引暂无中日正文（㭴改24条、滨波改二24条、扶桑改二补14时1条），根据百科明确时报用途和HH00双重标识收录；未以ASR逐条转写。

原下载器只读检查：kan.py。
复用其场景/章节安全命名、索引编号及MediaWiki文件名MD5目录规则；未运行全量抓取或其会话/防护绕过逻辑。

## 七条缺失与恢复来源

先经web搜索核对中文舰娘百科，再用公开API及文件URL核对。
川内页面11时误写158-1580.mp3：API与Special:FilePath证实该档不存在；实际158-1100.mp3存在（96,096字节）。
中文站实际音频URL返回HTML验证页，因此使用英文舰C百科同一时报的公开MP3，未伪造Cookie、登录或绕过验证。
秋月改二14、19、20、21、22、23时为真实改二差分；中文站页面有台词，但API文件条目缺失、Special:FilePath均404。
英文舰C百科的对应小时行有匹配日文台词和公开音频，已恢复全部六条；未用秋月改的旧台词替代。

|角色|小时|原索引档名|下载原文件名|来源|SHA256|
|---|---:|---|---|---|---|
|川内|11:00|158-1580|SendaiKaiNi-1100.mp3|[MP3](https://yksk.kancollewiki.net/images/a/a1/SendaiKaiNi-1100.mp3)|`e87dd9e6ef9c6178b2a230fbf44cdc5d5cd328ce9ebc4e4d8e8ed58e9b81f185`|
|秋月|14:00|563-1400|Ship_Voice_Akizuki_Kai_Ni_14.mp3|[MP3](https://yksk.kancollewiki.net/images/0/02/Ship_Voice_Akizuki_Kai_Ni_14.mp3)|`c66cec2b95706d666257105a8da9c4683f505d2a0abefcfb50e3ce1f70000ee4`|
|秋月|19:00|563-1900|Ship_Voice_Akizuki_Kai_Ni_19.mp3|[MP3](https://yksk.kancollewiki.net/images/4/4d/Ship_Voice_Akizuki_Kai_Ni_19.mp3)|`4974224d57b7b63abdadd8e45b5acd06caff571c4649857ab8fd2f9a3605a8af`|
|秋月|20:00|563-2000|Ship_Voice_Akizuki_Kai_Ni_20.mp3|[MP3](https://yksk.kancollewiki.net/images/6/6c/Ship_Voice_Akizuki_Kai_Ni_20.mp3)|`0cd7aa0c1521ccb360d8b71a0c69c13c64dbd26c1d66f54469381d8443e8105e`|
|秋月|21:00|563-2100|Ship_Voice_Akizuki_Kai_Ni_21.mp3|[MP3](https://yksk.kancollewiki.net/images/c/ce/Ship_Voice_Akizuki_Kai_Ni_21.mp3)|`0b09d757cc76b81dd4f842facde50f15675732f1b472522d106b9ee3593c374a`|
|秋月|22:00|563-2200|Ship_Voice_Akizuki_Kai_Ni_22.mp3|[MP3](https://yksk.kancollewiki.net/images/d/d5/Ship_Voice_Akizuki_Kai_Ni_22.mp3)|`8ac4e6d496a4571954db91cd9fd1a8d3f8885945ee3e157f4b5263b7e827bbdb`|
|秋月|23:00|563-2300|Ship_Voice_Akizuki_Kai_Ni_23.mp3|[MP3](https://yksk.kancollewiki.net/images/b/bd/Ship_Voice_Akizuki_Kai_Ni_23.mp3)|`d31bd4ef8954f22746839d4a476bec56ac61a4cb1a474daa780ace480cfb0e87`|

川内输出文件使用正确的158-1100.mp3；manifest中original_relative_path保留错误旧路径用于追溯。

资料页：[川内](https://zh.kcwiki.cn/wiki/%E5%B7%9D%E5%86%85)、[秋月](https://zh.kcwiki.cn/wiki/%E7%A7%8B%E6%9C%88)、[瑞凤](https://zh.kcwiki.cn/wiki/%E7%91%9E%E5%87%A4)、[英文Sendai](https://en.kancollewiki.net/Sendai)、[英文Akizuki](https://en.kancollewiki.net/Akizuki)。

## 文件来源清单与软件接口

`audio_manifest.json`为完整逐文件来源清单，schema_version=1。files中的path是以kancolle/开头的相对POSIX路径；hour是0..23整数；character为原角色目录名；sha256为完整文件哈希。
每条另含source_url、source_filename、source_page、source_kind、original_filename、original_relative_path、scene、section、size_bytes以及完整解码统计。
本地复制项source_url来自历史台词索引，仅下载补齐项在本次逐项联网取回；未宣称已重新下载核验所有历史远端URL。
软件应直接使用manifest的hour映射，不能继续依赖旧文件名/目录猜测；同角色同小时可能有多个合法版本。

## 完整静默验证

- 5885 / 5885 个最终文件逐个全程PyAV静默解码，失败0；哈希不符0；未列出文件0；普通台词用途条目0；空目录0。
- PyAV 18.1.0，单进程、最多4线程；解码验证71.92秒；有警告文件1。
- 未播放音频、未调用GUI、未循环启动ffmpeg。下载只接受固定SHA256匹配并完整解码成功的音频，404/HTML不进入输出。
- 原目录文件逐项只读复制并比对SHA256；最终kancolle/仅MP3，无完整游戏台词TXT。

复现准备（cache目录置于包外；--download-missing只请求上表7条白名单）：

```powershell
python tools/prepare_audio.py --source "source-audio" --cache-dir "<包外工作缓存>" --download-missing --workers 4
python tools/prepare_audio.py --verify-only --workers 4
```

## 原索引没有时报的角色

以下87个原角色索引没有时报用途条目，因此不创建空目录，也不把它们计成“各缺24条”、不合成或用普通台词填充。这是本次索引范围的结论，不代表游戏永远不会更新时报。

三日月、不知火、五十铃、五月雨、仓桥、伊势、佐渡、八丈、凉风、凤翔、利根、加古、占守、卯月、古鹰、名取、国后、塔什干、多摩、大东、大潮、天龙、如月、子日、宗谷、对马、屋代、岛风、平户、弥生、御藏、择捉、摩耶、敷波、文月、日向、日振、昭南、望月、木曾、村雨、松轮、浦风、涟、深雪、满潮、滨风、爱宕、球磨、甘比尔湾、电、皋月、睦月、石垣、矶波、祥凤、福江、稻木、第三〇号海防舰、第二十二号海防舰、第四号海防舰、第百一号输送舰、筑摩、羽黑、能美、若叶、荒潮、菊月、谷风、赤城、那智、长月、长良、阳炎、隼鹰、雪风、雷、霞、霰、青叶、飞鹰、高雄、鸟海、鹈来、黑潮、龙田、龙骧
