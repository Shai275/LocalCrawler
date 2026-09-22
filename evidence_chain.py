"""Portable, hash-verifiable research evidence (not legal certification)."""
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_chain(folder):
    """Check local files against the manifest, without trusting paths in it."""
    folder = Path(folder).resolve()
    errors = []
    def check(name, expected):
        path = (folder / name).resolve()
        if not path.is_relative_to(folder) or not path.is_file():
            errors.append(f'Missing or unsafe file: {name}')
        elif digest(path) != expected:
            errors.append(f'Hash mismatch: {name}')
    try:
        expected = (folder / 'evidence.sha256').read_text(encoding='ascii').split()[0]
        check('evidence.json', expected)
        if errors:
            return errors
        data = json.loads((folder / 'evidence.json').read_text(encoding='utf-8'))
        if data.get('schema') != 'localcrawler.evidence.v1':
            return ['Unsupported evidence schema']
        if data.get('transcript_file'):
            check(data['transcript_file'], data['transcript_sha256'])
        else:
            errors.append('Original transcript file unavailable')
        for record in data['records']:
            check(record['frame']['file'], record['frame_sha256'])
        if data.get('report_sha256'):
            check('evidence.html', data['report_sha256'])
        if data.get('capture_sha256'):
            check('capture.json', data['capture_sha256'])
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        errors.append(f'Invalid evidence bundle: {type(exc).__name__}')
    return errors


def export_chain(folder, video_id, frames, notes, transcript, provider, model):
    folder = Path(folder)
    raw = folder / 'transcript.json'
    source = json.loads(raw.read_text(encoding='utf-8')) if raw.exists() else None
    if source is None:
        (folder / 'transcript.md').write_text(transcript, encoding='utf-8')
    raw_units = source.get('snippets', []) if source else []
    records = []
    for index, note in enumerate(notes, 1):
        frame = next(f for f in frames if f['id'] == note['frame_id'])
        clean = lambda value: ' '.join(str(value).split())
        matches = [s for s in raw_units if clean(s.get('text', '')) == clean(note['caption'])]
        anchor = note.get('caption_seconds', frame.get('decoded_seconds') or frame['seconds'])
        caption = min(matches, key=lambda s: abs(float(s['start'])-anchor)) if matches else None
        start = float(caption['start']) if caption else note.get('caption_seconds')
        records.append({'id': f'E{index:03d}', 'frame': dict(frame),
            'frame_sha256': digest(folder / frame['file']), 'caption_text': note['caption'],
            'caption_start': start, 'caption_duration': caption.get('duration') if caption else None,
            'caption_precision': 'source-timestamp' if caption else 'markdown-whole-seconds',
            'summary': note['visual_evidence'], 'title': note['title'], 'ocr': note['ocr'],
            'shared_text': note['shared'], 'association': note.get('association', 'text-overlap' if note['shared'] else 'temporal-only'),
            'provider': provider, 'model': model})
    data = {'schema': 'localcrawler.evidence.v1', 'created_at': datetime.now(timezone.utc).isoformat(),
            'video_url': f'https://www.youtube.com/watch?v={video_id}',
            'transcript_sha256': digest(raw if raw.exists() else folder / 'transcript.md'),
            'transcript_file': 'transcript.json' if raw.exists() else 'transcript.md',
            'limitations': 'Hashes detect changes against this manifest, not authenticity or legal admissibility. AI descriptions may be wrong.',
            'records': records}
    path = folder / 'evidence.json'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'evidence.sha256').write_text(digest(path) + '  evidence.json\n', encoding='ascii')
    esc = lambda x: html.escape(str(x), quote=True)
    cards = []
    for r in records:
        frame = r['frame']; t = r['caption_start']
        target = f"{data['video_url']}&t={int(t if t is not None else frame['seconds'])}s"
        image_target = f"{data['video_url']}&t={int(frame.get('decoded_seconds') or frame['seconds'])}s"
        cards.append(f'<article id="{r["id"]}"><h2>{esc(r["title"])}</h2>'
            f'<a href="{esc(image_target)}" target="_blank" rel="noopener noreferrer"><img src="{esc(frame["file"])}" alt="影格 {esc(frame["id"])}"></a>'
            f'<p>{esc(r["summary"])}</p><blockquote>{esc(r["caption_text"])}</blockquote>'
            f'<p>對齊：{esc("共同文字，不代表 AI 描述已核實" if r["association"] == "text-overlap" else "僅時間相鄰，內容關係尚未核實")}</p>'
            f'<p>字幕起點：{esc(t)} 秒 · 影格解碼時間：{esc(frame.get("decoded_seconds"))} 秒</p>'
            f'<p>OCR：{esc(r["ocr"])}</p><a href="{esc(target)}" target="_blank" rel="noopener noreferrer">跳回影片字幕時間點</a>'
            f'<details><summary>來源與完整性</summary><pre>{esc(json.dumps(r, ensure_ascii=False, indent=2))}</pre></details></article>')
    verified = sum(r['association'] == 'text-overlap' for r in records)
    temporal = len(records) - verified
    decoders = sorted({r['frame'].get('decoder_status', 'unknown') for r in records})
    nav = ''.join(f'<a href="#{esc(r["id"])}">{esc(r["id"])} · {esc(r["frame"]["seconds"])}s</a>' for r in records)
    page = '<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
    page += '<title>LocalCrawler 來源核對</title><style>:root{color-scheme:light}body{font:16px system-ui;color:#1d1d1f;background:#f5f5f7;max-width:940px;margin:30px auto;padding:20px}header,article{background:#fff;padding:28px;border-radius:20px;margin:20px 0;box-shadow:0 1px 2px #0001}h1{letter-spacing:-.04em}img{display:block;max-width:100%;border-radius:12px;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#0672d8}.stats{display:flex;gap:10px;flex-wrap:wrap}.stats span,.timeline a{background:#f0f2f5;border-radius:999px;padding:8px 12px}.timeline{display:flex;gap:8px;overflow:auto;padding:8px 0}.timeline a{white-space:nowrap;text-decoration:none}blockquote{border-left:3px solid #bbb;margin-left:0;padding-left:16px;color:#555}@media(max-width:600px){body{margin:0;padding:12px}header,article{padding:18px}}</style>'
    page += (f'<header><h1>影格・字幕・摘要來源核對</h1><p>點擊圖片跳到影格時間；字幕連結跳到字幕時間。AI 與 OCR 仍可能誤判，時間相鄰不代表內容互相證實。</p>'
             f'<div class="stats"><span>{len(records)} 項來源</span><span>{verified} 項共同文字</span><span>{temporal} 項僅時間相鄰</span><span>解碼：{esc(", ".join(decoders))}</span></div>'
             f'<nav class="timeline">{nav}</nav><p>SHA-256 可檢查保存後的檔案變化，不代表來源真實性、可信時間戳或司法鑑定。</p></header>') + ''.join(cards) + '</html>'
    (folder / 'evidence.html').write_text(page, encoding='utf-8')
    data['report_sha256'] = digest(folder / 'evidence.html')
    if (folder / 'capture.json').exists():
        data['capture_sha256'] = digest(folder / 'capture.json')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder / 'evidence.sha256').write_text(digest(path) + '  evidence.json\n', encoding='ascii')
    return records


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Verify local evidence integrity (not authenticity).')
    parser.add_argument('folder')
    failures = verify_chain(parser.parse_args().folder)
    print('\n'.join(failures) if failures else 'OK: manifest, transcript and frames match.')
    raise SystemExit(bool(failures))
