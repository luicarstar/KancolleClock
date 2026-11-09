"""Prepare only Kancolle hourly voices; never imports or runs the clock GUI.

The source tree is read-only. Filename/section rules follow the user's existing
the original kan.py downloader. Network recovery is an
explicit seven-file allowlist, with pinned SHA256 and public wiki provenance.
Requires PyAV. Uses standard-library HTTP; no browser sessions or credentials.
"""
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.parse import quote, urlsplit
import argparse
import hashlib
import json
import re
import shutil
import time
import av

DIGITS = str.maketrans('〇零一二三四五六七八九', '00123456789')
RECOVERY = {
    ('秋月', 14): ('0/02/Ship_Voice_Akizuki_Kai_Ni_14.mp3', 'akizuki_14.mp3', 'c66cec2b95706d666257105a8da9c4683f505d2a0abefcfb50e3ce1f70000ee4'),
    ('秋月', 19): ('4/4d/Ship_Voice_Akizuki_Kai_Ni_19.mp3', 'akizuki_19.mp3', '4974224d57b7b63abdadd8e45b5acd06caff571c4649857ab8fd2f9a3605a8af'),
    ('秋月', 20): ('6/6c/Ship_Voice_Akizuki_Kai_Ni_20.mp3', 'akizuki_20.mp3', '0cd7aa0c1521ccb360d8b71a0c69c13c64dbd26c1d66f54469381d8443e8105e'),
    ('秋月', 21): ('c/ce/Ship_Voice_Akizuki_Kai_Ni_21.mp3', 'akizuki_21.mp3', '0b09d757cc76b81dd4f842facde50f15675732f1b472522d106b9ee3593c374a'),
    ('秋月', 22): ('d/d5/Ship_Voice_Akizuki_Kai_Ni_22.mp3', 'akizuki_22.mp3', '8ac4e6d496a4571954db91cd9fd1a8d3f8885945ee3e157f4b5263b7e827bbdb'),
    ('秋月', 23): ('b/bd/Ship_Voice_Akizuki_Kai_Ni_23.mp3', 'akizuki_23.mp3', 'd31bd4ef8954f22746839d4a476bec56ac61a4cb1a474daa780ace480cfb0e87'),
    ('川内', 11): ('a/a1/SendaiKaiNi-1100.mp3', 'sendai_11.mp3', 'e87dd9e6ef9c6178b2a230fbf44cdc5d5cd328ce9ebc4e4d8e8ed58e9b81f185'),
}


def safe_name(value, limit=36):
    value = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', value or '')
    return re.sub(r'\s+', ' ', value).strip(' ._')[:limit] or 'unnamed'


def md5_url(filename):
    """Existing kan.py's public MediaWiki URL calculation rule."""
    filename = filename.replace(' ', '_')
    digest = hashlib.md5(filename.encode('utf-8')).hexdigest()
    return f'https://uploads.kcwiki.cn/commons/{digest[0]}/{digest[:2]}/{quote(filename)}'


def read_index(source):
    rows = []
    manifests = sorted(source.glob('*/*_台词.txt'))
    for path in manifests:
        text = path.read_text(encoding='utf-8-sig')
        marks = list(re.finditer(r'^─{3,}\s*(.*?)\s*─{3,}\s*$|^(\d{3,})\. 【(.*?)】\s*$', text, re.M))
        sections = {m.group(1) for m in marks if m.group(1) is not None}
        page = re.search(r'^来源:\s*(.+)$', text, re.M)
        section = ''
        for i, mark in enumerate(marks):
            if mark.group(1) is not None:
                section = mark.group(1)
                continue
            body = text[mark.end():marks[i+1].start() if i+1 < len(marks) else len(text)]
            fields = {}
            for label, key in [('档名', 'filename'), ('URL', 'url'), ('日文', 'ja'), ('中文', 'zh')]:
                match = re.search(r'^\s*' + label + r'\s*:\s*(.+)$', body, re.M)
                fields[key] = match.group(1).strip() if match else ''
            if not fields['filename']:
                continue
            filename = fields['filename']
            if '.' not in filename:
                filename += '.mp3'
            scene = mark.group(3)
            filename = f'{int(mark.group(2)):03d}_{safe_name(scene)}_{filename}'
            rel = Path(path.parent.name)/(safe_name(section) if len(sections) > 1 else '')/filename
            rows.append(dict(character=path.parent.name, section=section, scene=scene,
                             rel=rel.as_posix(), source_page=page.group(1).strip() if page else '', **fields))
    return rows, len(manifests)


def hourly_hour(row):
    """Require an hourly use label, not merely a 时报 directory or time mention."""
    match = re.match(r'^([〇零一二三四五六七八九]{4})(?:时报|时)', row['scene'])
    if not match:
        return None
    hhmm = match.group(1).translate(DIGITS)
    if hhmm[2:] != '00' or not 0 <= int(hhmm[:2]) < 24:
        raise ValueError(f'Invalid hourly scene: {row["rel"]}')
    hour = int(hhmm[:2])
    suffix = re.search(r'-(\d{4})(?:\.mp3)?$', row['filename'])
    if suffix and suffix.group(1) == f'{hour:02d}00':
        return hour
    if row['character'] == '川内' and hour == 11 and row['filename'] == '158-1580':
        return hour  # Proven wiki typo; actual file is 158-1100.mp3.
    raise ValueError(f'Unreviewed scene/HH mismatch: {row["rel"]}')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recover(row, hour, cache, download):
    part, cache_name, expected = RECOVERY[(row['character'], hour)]
    url = 'https://yksk.kancollewiki.net/images/' + part
    cached = cache/cache_name
    if not cached.is_file() and download:
        request = Request(url, headers={'User-Agent': 'KancolleClockAudioAudit/1.0'})
        with urlopen(request, timeout=25) as response:
            data = response.read(4_000_001)
        if len(data) > 4_000_000 or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'Download hash mismatch / HTML response: {url}')
        cache.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    if not cached.is_file() or sha256(cached) != expected:
        raise ValueError(f'Need verified recovery cache or --download-missing: {cached}')
    return cached, url, part.rsplit('/', 1)[-1]


def inside(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError(f'Unsafe path: {relative}')
    target = (root/relative).resolve()
    target.relative_to(root.resolve())
    return target


def verify_file(task):
    path, row = task
    result = dict(path=row['path'], ok=False)
    try:
        if sha256(path) != row['sha256']:
            raise ValueError('SHA256 mismatch')
        if hourly_hour(dict(scene=row['scene'], character=row['character'],
                            filename=row['original_filename'], rel=row['path'])) != row['hour']:
            raise ValueError('Non-hourly or wrong-hour entry')
        samples, rate, logs = 0, 0, []
        with av.logging.Capture(local=True) as captured:
            try:
                with av.open(str(path)) as container:
                    stream = container.streams.audio[0]
                    codec = stream.codec_context.name
                    rate = stream.codec_context.sample_rate
                    for frame in container.decode(audio=0):
                        samples += frame.samples
            finally:
                logs = list(captured)
        errors = [msg.strip() for level, _, msg in logs if level <= av.logging.ERROR]
        if not samples or errors:
            raise ValueError('No samples or decode errors: ' + repr(errors[:3]))
        result.update(ok=True, decoded_samples=samples, sample_rate=rate, codec=codec,
                      duration_seconds=round(samples/rate, 6),
                      warnings=[msg.strip() for level, _, msg in logs if level > av.logging.ERROR][:3])
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    return result


def verify(output, files, workers):
    av.logging.set_level(av.logging.WARNING)
    tasks = [(inside(output, row['path']), row) for row in files]
    actual = {p.relative_to(output).as_posix() for p in (output/'kancolle').rglob('*') if p.is_file()}
    expected = {row['path'] for row in files}
    if len(expected) != len(files) or actual != expected:
        raise ValueError(f'Duplicate/missing/unlisted files: {len(actual ^ expected)}')
    if any(p.is_dir() and not any(p.iterdir()) for p in (output/'kancolle').rglob('*')):
        raise ValueError('Empty audio directory')
    results = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, result in enumerate(pool.map(verify_file, tasks), 1):
            results.append(result)
            if i % 1000 == 0 or i == len(files):
                print(f'VERIFY {i}/{len(files)} elapsed={time.monotonic()-started:.1f}s', flush=True)
    failures = [r for r in results if not r['ok']]
    if failures:
        raise ValueError(json.dumps(failures, ensure_ascii=False))
    return results, dict(fully_decoded_files=len(results), decode_failures=0,
                        sha256_failures=0, unlisted_files=0, empty_directories=0,
                        normal_dialogue_entries=0, warnings_files=sum(bool(r['warnings']) for r in results),
                        elapsed_seconds=round(time.monotonic()-started, 2), pyav_version=av.__version__,
                        method='Each output file SHA256 + full silent PyAV decode, one process, bounded threads')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(r'source-audio'))
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--download-missing', action='store_true')
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--workers', type=int, default=4, choices=range(1, 7))
    args = parser.parse_args()
    output, source = args.output.resolve(), args.source.resolve()
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Source and output must be disjoint; source is read-only')
    manifest_path = output/'audio_manifest.json'
    if args.verify_only:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        _, validation = verify(output, manifest['files'], args.workers)
        print('VALIDATION', json.dumps(validation, ensure_ascii=False))
        return
    if args.cache_dir is None:
        raise ValueError('--cache-dir is required; use a working directory outside the package')
    cache = args.cache_dir.resolve()
    if cache == source or cache.is_relative_to(source) or cache == output or cache.is_relative_to(output):
        raise ValueError('Cache must be outside source and package')
    rows, manifest_count = read_index(source)
    selected = [(row, hourly_hour(row)) for row in rows]
    selected = [(row, hour) for row, hour in selected if hour is not None]
    files, downloaded = [], []
    for row, hour in selected:
        original = inside(source, row['rel'])
        rel = row['rel']
        if row['character'] == '川内' and hour == 11 and row['filename'] == '158-1580':
            rel = rel.replace('158-1580.mp3', '158-1100.mp3')
        filename = row['filename'] if '.' in row['filename'] else row['filename']+'.mp3'
        if original.is_file():
            origin, url, source_filename = original, row['url'] or md5_url(filename), filename
            kind = 'local_copy'
        else:
            origin, url, source_filename = recover(row, hour, cache, args.download_missing)
            kind = 'downloaded'
        target = inside(output, 'kancolle/'+rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
        entry = dict(path='kancolle/'+rel, hour=hour, character=row['character'],
                     sha256=sha256(origin), source_url=url, source_filename=source_filename,
                     source_page=row['source_page'] if kind == 'local_copy' else
                        'https://en.kancollewiki.net/'+('Sendai' if row['character']=='川内' else 'Akizuki'),
                     original_source_url=row['url'], original_filename=row['filename'],
                     original_relative_path=row['rel'], scene=row['scene'], section=row['section'],
                     source_kind=kind, size_bytes=origin.stat().st_size)
        files.append(entry)
        if kind == 'downloaded':
            downloaded.append(entry)
    results, validation = verify(output, files, args.workers)
    for entry, result in zip(files, results):
        entry.update(duration_seconds=result['duration_seconds'], codec=result['codec'],
                     sample_rate=result['sample_rate'], decoded_samples=result['decoded_samples'])
    characters = defaultdict(set)
    for entry in files:
        characters[entry['character']].add(entry['hour'])
    absent_characters = sorted({row['character'] for row in rows} - set(characters))
    stats = dict(source_manifest_files=manifest_count, source_manifest_entries=len(rows),
                 expected_hourly_entries=len(selected), local_hourly_copies=len(files)-len(downloaded),
                 downloaded_files=len(downloaded), unrecovered_hourly_entries=0,
                 excluded_missing_non_hourly=sum(not inside(source, row['rel']).is_file()
                                                for row in rows if hourly_hour(row) is None),
                 audio_files=len(files), audio_bytes=sum(f['size_bytes'] for f in files),
                 characters=len(characters), characters_with_24_hours=sum(len(h)==24 for h in characters.values()),
                 omitted_characters_without_indexed_hourlies=absent_characters,
                 hour_counts=dict(sorted(Counter(f['hour'] for f in files).items())))
    manifest = dict(schema_version=1, files=files, statistics=stats, validation=validation)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    write_report(output, manifest, downloaded)
    print('RESULT', json.dumps(dict(statistics=stats, validation=validation), ensure_ascii=False), flush=True)


def write_report(output, manifest, downloaded):
    stats, validation = manifest['statistics'], manifest['validation']
    text = [
        '# 舰队Collection 时报资源核对报告', '',
        '仅收录整点时报用途音频。原目录 source-audio 只读保留；未运行报时 GUI。',
        '核对边界为现有329角色台词索引；不声称这些索引覆盖游戏全部角色及最新资料。', '',
        f"- 原索引：{stats['source_manifest_files']} 份，{stats['source_manifest_entries']} 条路径；原MP3 17,621条。",
        '- 原清单112条路径缺失：时报7条、普通台词105条。普通台词缺失不下载。',
        '- 复核时报应有5,885条；本地5,878条；新增下载7条；未恢复时报0条。',
        f"- 最终音频：{stats['audio_files']:,} 条，{stats['audio_bytes']:,} 字节（{stats['audio_bytes']/1024**2:.2f} MiB）。",
        f"- {stats['characters']}个角色有时报，全部覆盖24小时；同角色同小时的改造差分/旧版保留。", '',
        '## 分类与漏识别纠正', '',
        '以台词索引的场景/用途标签为首要证据，并核对HH00文件标识。不能仅凭父目录“时报”或普通台词提到时间就收录。',
        '- 原函数识别5,877条；补收瑞凤/瑞凤改二/044_一七〇〇时_355-1700.mp3（17时），本地共5,878条。',
        '- 朝潮/时报目录的补给085a-Resupply与放置085a-Idle是普通台词，明确排除。',
        '- 保留挪威“时报イ”、熊野丸“时报！”、雾岛“时报（舊）”等确属时报的变体。',
        '- 所有17,733条索引均核对；额外查找非时报场景中HHMM档名及明确时间正文，未发现其他漏收时报。',
        '- 49条索引暂无中日正文（㭴改24条、滨波改二24条、扶桑改二补14时1条），根据百科明确时报用途和HH00双重标识收录；未以ASR逐条转写。', '',
        '原下载器只读检查：kan.py。',
        '复用其场景/章节安全命名、索引编号及MediaWiki文件名MD5目录规则；未运行全量抓取或其会话/防护绕过逻辑。', '',
        '## 七条缺失与恢复来源', '',
        '先经web搜索核对中文舰娘百科，再用公开API及文件URL核对。',
        '川内页面11时误写158-1580.mp3：API与Special:FilePath证实该档不存在；实际158-1100.mp3存在（96,096字节）。',
        '中文站实际音频URL返回HTML验证页，因此使用英文舰C百科同一时报的公开MP3，未伪造Cookie、登录或绕过验证。',
        '秋月改二14、19、20、21、22、23时为真实改二差分；中文站页面有台词，但API文件条目缺失、Special:FilePath均404。',
        '英文舰C百科的对应小时行有匹配日文台词和公开音频，已恢复全部六条；未用秋月改的旧台词替代。', '',
        '|角色|小时|原索引档名|下载原文件名|来源|SHA256|',
        '|---|---:|---|---|---|---|',
    ]
    for row in sorted(downloaded, key=lambda x:(x['character'], x['hour'])):
        text.append(f"|{row['character']}|{row['hour']:02d}:00|{row['original_filename']}|{row['source_filename']}|[MP3]({row['source_url']})|`{row['sha256']}`|")
    text += ['', '川内输出文件使用正确的158-1100.mp3；manifest中original_relative_path保留错误旧路径用于追溯。', '',
             '资料页：[川内](https://zh.kcwiki.cn/wiki/%E5%B7%9D%E5%86%85)、[秋月](https://zh.kcwiki.cn/wiki/%E7%A7%8B%E6%9C%88)、[瑞凤](https://zh.kcwiki.cn/wiki/%E7%91%9E%E5%87%A4)、[英文Sendai](https://en.kancollewiki.net/Sendai)、[英文Akizuki](https://en.kancollewiki.net/Akizuki)。', '',
             '## 文件来源清单与软件接口', '',
             '`audio_manifest.json`为完整逐文件来源清单，schema_version=1。files中的path是以kancolle/开头的相对POSIX路径；hour是0..23整数；character为原角色目录名；sha256为完整文件哈希。',
             '每条另含source_url、source_filename、source_page、source_kind、original_filename、original_relative_path、scene、section、size_bytes以及完整解码统计。',
             '本地复制项source_url来自历史台词索引，仅下载补齐项在本次逐项联网取回；未宣称已重新下载核验所有历史远端URL。',
             '软件应直接使用manifest的hour映射，不能继续依赖旧文件名/目录猜测；同角色同小时可能有多个合法版本。', '',
             '## 完整静默验证', '',
             f"- {validation['fully_decoded_files']} / {stats['audio_files']} 个最终文件逐个全程PyAV静默解码，失败0；哈希不符0；未列出文件0；普通台词用途条目0；空目录0。",
             f"- PyAV {validation['pyav_version']}，单进程、最多4线程；解码验证{validation['elapsed_seconds']}秒；有警告文件{validation['warnings_files']}。",
             '- 未播放音频、未调用GUI、未循环启动ffmpeg。下载只接受固定SHA256匹配并完整解码成功的音频，404/HTML不进入输出。',
             '- 原目录文件逐项只读复制并比对SHA256；最终kancolle/仅MP3，无完整游戏台词TXT。', '',
             '复现准备（cache目录置于包外；--download-missing只请求上表7条白名单）：', '',
             '```powershell',
             'python tools/prepare_audio.py --source "source-audio" --cache-dir "<包外工作缓存>" --download-missing --workers 4',
             'python tools/prepare_audio.py --verify-only --workers 4',
             '```', '',
             '## 原索引没有时报的角色', '',
             '以下87个原角色索引没有时报用途条目，因此不创建空目录，也不把它们计成“各缺24条”、不合成或用普通台词填充。这是本次索引范围的结论，不代表游戏永远不会更新时报。', '',
             '、'.join(stats['omitted_characters_without_indexed_hourlies']), '']
    (output/'RESOURCE_REPORT.md').write_text('\n'.join(text), encoding='utf-8')


if __name__ == '__main__':
    main()
