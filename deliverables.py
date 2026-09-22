"""Export a saved LocalCrawler report as PDF, Markdown, Notion and Obsidian Canvas."""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

IMAGE = re.compile(r'!\[([^]]*)\]\(([^)]+)\)')
LINK = re.compile(r'\[([^]]+)\]\((https?://[^)]+)\)')


def _slug(value: str) -> str:
    value = re.sub(r'[^\w\-]+', '-', value, flags=re.UNICODE).strip('-_')
    return value[:48] or 'research-report'


def _local_images(markdown: str, source_dir: Path) -> list[tuple[str, Path]]:
    found = []
    root = source_dir.resolve()
    for _, reference in IMAGE.findall(markdown):
        if urlsplit(reference).scheme or reference.startswith(('/', '\\')):
            continue
        candidate = (source_dir / reference).resolve()
        if candidate.is_relative_to(root) and candidate.is_file() and candidate.stat().st_size <= 20 * 1024 * 1024:
            found.append((reference, candidate))
    return found[:24]


def _copy_markdown(markdown: str, source_dir: Path, target: Path, filename='report.md') -> Path:
    assets = target / 'assets'
    target.mkdir(parents=True, exist_ok=True)
    replacements = {}
    for index, (reference, image) in enumerate(_local_images(markdown, source_dir), 1):
        assets.mkdir(exist_ok=True)
        name = f'{index:02d}_{_slug(image.stem)}{image.suffix.lower()}'
        shutil.copy2(image, assets / name)
        replacements[reference] = 'assets/' + name
    copied = IMAGE.sub(lambda match: f'![{match.group(1)}]({replacements.get(match.group(2), match.group(2))})', markdown)
    path = target / filename
    path.write_text(copied, encoding='utf-8')
    return path


def _font_name():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    choices = [Path(r'C:\Windows\Fonts\msjh.ttc'), Path(r'C:\Windows\Fonts\arial.ttf')]
    for path in choices:
        if path.is_file():
            try:
                pdfmetrics.registerFont(TTFont('LocalCrawlerFont', str(path), subfontIndex=0))
                return 'LocalCrawlerFont'
            except Exception:
                continue
    return 'Helvetica'


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = LINK.sub(r'<link href="\2" color="#0066cc">\1</link>', escaped)
    escaped = re.sub(r'`([^`]+)`', r'<font face="Courier">\1</font>', escaped)
    escaped = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', escaped)
    return escaped


def create_pdf(markdown: str, source_dir: Path, output: Path, title: str, source_url='') -> Path:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image as PDFImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font = _font_name()
    styles = getSampleStyleSheet()
    body = ParagraphStyle('Body', parent=styles['BodyText'], fontName=font, fontSize=10.5, leading=17,
                          textColor=colors.HexColor('#303033'), spaceAfter=8)
    h1 = ParagraphStyle('H1', parent=body, fontSize=24, leading=30, textColor=colors.HexColor('#111113'), spaceAfter=16)
    h2 = ParagraphStyle('H2', parent=body, fontSize=16, leading=22, textColor=colors.HexColor('#111113'), spaceBefore=14, spaceAfter=8)
    h3 = ParagraphStyle('H3', parent=body, fontSize=12.5, leading=18, textColor=colors.HexColor('#1d1d1f'), spaceBefore=10, spaceAfter=5)
    quote = ParagraphStyle('Quote', parent=body, leftIndent=12, borderColor=colors.HexColor('#b8bcc5'), borderWidth=2,
                           borderPadding=8, backColor=colors.HexColor('#f5f6f8'))
    bullet = ParagraphStyle('Bullet', parent=body, leftIndent=14, firstLineIndent=-8)
    doc = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                            topMargin=21*mm, bottomMargin=20*mm, title=title, author='LocalCrawler')
    story = [Paragraph(_inline(title), h1)]
    if source_url:
        story += [Paragraph('來源：' + _inline(f'[{source_url}]({source_url})'), body), Spacer(1, 4)]
    lines = markdown.replace('\r\n', '\n').splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        image_match = IMAGE.fullmatch(line)
        if image_match:
            reference = image_match.group(2)
            path = (source_dir / reference).resolve()
            if path.is_relative_to(source_dir.resolve()) and path.is_file():
                try:
                    image = PDFImage(str(path))
                    scale = min(1, 170*mm/image.drawWidth, 105*mm/image.drawHeight)
                    image.drawWidth *= scale; image.drawHeight *= scale
                    story += [image, Paragraph(_inline(image_match.group(1) or path.stem), ParagraphStyle('Caption', parent=body, alignment=TA_CENTER, fontSize=8.5, textColor=colors.grey))]
                except Exception:
                    story.append(Paragraph('[圖片無法嵌入] ' + _inline(reference), body))
            index += 1
            continue
        if line.startswith('|') and index + 1 < len(lines) and re.match(r'^\|?\s*:?-+', lines[index+1].strip()):
            rows = []
            while index < len(lines) and lines[index].strip().startswith('|'):
                cells = [Paragraph(_inline(cell.strip()), body) for cell in lines[index].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', cell.getPlainText()) for cell in cells):
                    rows.append(cells)
                index += 1
            if rows:
                table = Table(rows, repeatRows=1, hAlign='LEFT')
                table.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),font),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eef0f4')),
                                           ('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd0d7')),('VALIGN',(0,0),(-1,-1),'TOP'),
                                           ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6)]))
                story += [table, Spacer(1, 8)]
            continue
        if line.startswith('### '): style, value = h3, line[4:]
        elif line.startswith('## '): style, value = h2, line[3:]
        elif line.startswith('# '): style, value = h1, line[2:]
        elif line.startswith('> '): style, value = quote, line[2:]
        elif re.match(r'^[-*] ', line): style, value = bullet, '• ' + line[2:]
        else:
            paragraph = [line]
            while index + 1 < len(lines) and lines[index+1].strip() and not re.match(r'^(#{1,3} |[-*>] |!\[|\|)', lines[index+1].strip()):
                index += 1; paragraph.append(lines[index].strip())
            style, value = body, ' '.join(paragraph)
        story.append(Paragraph(_inline(value), style))
        index += 1

    def decorate(canvas, document):
        canvas.saveState(); canvas.setFont(font, 8); canvas.setFillColor(colors.HexColor('#77777c'))
        canvas.drawString(18*mm, 10*mm, 'LocalCrawler · ' + title[:55])
        canvas.drawRightString(192*mm, 10*mm, str(document.page)); canvas.restoreState()
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return output


def _sections(markdown: str) -> list[tuple[str, str]]:
    sections, title, lines = [], '摘要', []
    for line in markdown.splitlines():
        if line.startswith(('## ', '### ')):
            if lines:
                sections.append((title, '\n'.join(lines).strip()))
            title, lines = line.lstrip('# ').strip(), []
        else:
            lines.append(line)
    if lines:
        sections.append((title, '\n'.join(lines).strip()))
    return [(title, body) for title, body in sections if body][:20]


def create_canvas(markdown: str, source_dir: Path, target: Path, title: str) -> Path:
    report = _copy_markdown(markdown, source_dir, target, 'report.md')
    portable = report.read_text(encoding='utf-8')
    cards = target / 'cards'; cards.mkdir(exist_ok=True)
    nodes, edges = [], []
    for index, (heading, content) in enumerate(_sections(portable), 1):
        name = f'{index:02d}_{_slug(heading)}.md'
        content = content.replace('](assets/', '](../assets/')
        (cards/name).write_text(f'# {heading}\n\n{content}\n', encoding='utf-8')
        node_id = hashlib.sha256(name.encode()).hexdigest()[:16]
        nodes.append({'id':node_id, 'type':'file', 'file':'cards/'+name, 'x':0, 'y':(index-1)*300, 'width':520, 'height':240})
        if index > 1:
            edges.append({'id':f'e{index:03d}', 'fromNode':nodes[-2]['id'], 'fromSide':'bottom', 'toNode':node_id, 'toSide':'top'})
    for index, image in enumerate(sorted((target/'assets').glob('*')) if (target/'assets').exists() else [], 1):
        nodes.append({'id':hashlib.sha256(image.name.encode()).hexdigest()[:16], 'type':'file', 'file':'assets/'+image.name,
                      'x':620, 'y':(index-1)*340, 'width':520, 'height':300})
    canvas = target / f'{_slug(title)}.canvas'
    canvas.write_text(json.dumps({'nodes':nodes, 'edges':edges}, ensure_ascii=False, indent=2), encoding='utf-8')
    return canvas


def export_deliverables(source: str | Path, title: str, source_url='') -> dict[str, Path]:
    source = Path(source).resolve()
    if not source.is_file() or source.suffix.lower() != '.md' or source.stat().st_size > 10 * 1024 * 1024:
        raise ValueError('請選擇 10 MB 以內的本機 Markdown 報告。')
    markdown = source.read_text(encoding='utf-8-sig')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    root = source.parent / 'deliverables' / f'{stamp}_{_slug(title)}'
    root.mkdir(parents=True, exist_ok=False)
    markdown_path = _copy_markdown(markdown, source.parent, root/'markdown')
    notion_path = _copy_markdown(f'# {title}\n\n來源：{source_url or "本機研究資料"}\n\n{markdown}', source.parent, root/'notion', 'notion-import.md')
    notion_zip = root/'notion-import.zip'
    with zipfile.ZipFile(notion_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in (root/'notion').rglob('*'):
            if path.is_file(): archive.write(path, path.relative_to(root/'notion'))
    canvas_path = create_canvas(markdown, source.parent, root/'obsidian', title)
    pdf_path = create_pdf(markdown, source.parent, root/f'{_slug(title)}.pdf', title, source_url)
    manifest = {'schema':'localcrawler.deliverables.v1', 'created_at':datetime.now().astimezone().isoformat(),
                'source_file':source.name, 'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                'outputs':{'pdf':pdf_path.name, 'markdown':str(markdown_path.relative_to(root)),
                           'notion':notion_zip.name, 'obsidian':str(canvas_path.relative_to(root))}}
    (root/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'folder':root, 'pdf':pdf_path, 'markdown':markdown_path, 'notion':notion_zip, 'canvas':canvas_path}
