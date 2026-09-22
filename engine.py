"""Crawl4AI backend, independent of the desktop interface."""
from __future__ import annotations

import asyncio
import csv
import json
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
from insights import DEFAULT_MODEL

@dataclass
class Page:
    url: str
    final_url: str = ""
    title: str = ""
    success: bool = False
    status_code: int | None = None
    markdown: str = ""
    error: str = ""
    file: str = ""
    attempts: int = 0
    elapsed_seconds: float = 0
    crawled_at: str = ""
    source_type: str = "web"
    summary: str = ""
    summary_mode: str = ""
    summary_warning: str = ""
    summary_file: str = ""
    sources_file: str = ""
    language: str = ""
    facts: list[str] = field(default_factory=list)


def parse_urls(text: str) -> list[str]:
    urls = []
    for line in text.splitlines():
        value = line.strip()
        if not value:
            continue
        if any(c.isspace() for c in value):
            raise ValueError(f"每行只能有一個完整網址：{value}")
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError(f"請使用 http:// 或 https:// 網址：{value}")
        if parts.username or parts.password:
            raise ValueError("網址不能包含帳號或密碼。")
        try:
            _ = parts.port
        except ValueError as exc:
            raise ValueError(f"網址連接埠不正確：{value}") from exc
        value = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))
        if value not in urls:
            urls.append(value)
    if not urls:
        raise ValueError("請至少輸入一個網址。")
    if len(urls) > 100:
        raise ValueError("每批最多 100 個網址，請分批執行。")
    return urls


def save_results(folder: Path, pages: list[Page]) -> None:
    """Write metadata atomically; CSV contains no executable cell prefixes."""
    temp = folder / "results.json.tmp"
    temp.write_text(json.dumps([asdict(p) for p in pages], ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(folder / "results.json")
    with (folder / "results.csv.tmp").open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["網址", "最終網址", "標題", "成功", "HTTP 狀態", "Markdown 檔案", "錯誤", "嘗試次數", "耗時秒", "擷取時間", "來源類型", "摘要方式", "摘要", "摘要提醒"])
        for p in pages:
            cells = [p.url, p.final_url, p.title, p.success, p.status_code, p.file, p.error, p.attempts, p.elapsed_seconds, p.crawled_at, p.source_type, p.summary_mode, p.summary, p.summary_warning]
            writer.writerow(["'" + c if isinstance(c, str) and c.lstrip().startswith(("=", "+", "-", "@")) else c for c in cells])
    (folder / "results.csv.tmp").replace(folder / "results.csv")


def load_results(path: Path) -> list[Page]:
    """Load this app's saved results, validating types and file references."""
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("結果檔超過 50 MB，請直接在文字編輯器開啟。")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list) or len(data) > 100:
        raise ValueError("請選擇本程式產生的 results.json（最多 100 筆）。")
    pages = []
    for row in data:
        if not isinstance(row, dict) or not isinstance(row.get("url"), str) or not isinstance(row.get("success"), bool):
            raise ValueError("結果檔格式不正確。")
        page = Page(**{k: v for k, v in row.items() if k in Page.__dataclass_fields__})
        for name in ("url", "final_url", "title", "markdown", "error", "file", "crawled_at", "source_type", "summary", "summary_mode", "summary_warning", "summary_file", "sources_file", "language"):
            if not isinstance(getattr(page, name), str):
                raise ValueError(f"結果欄位 {name} 格式不正確。")
        if not isinstance(page.attempts, int) or not isinstance(page.elapsed_seconds, (int, float)):
            raise ValueError("結果中的嘗試次數或耗時格式不正確。")
        for filename in (page.file, page.summary_file, page.sources_file):
            if filename and (Path(filename).name != filename or not filename.endswith(".md") or ":" in filename or "\\" in filename):
                raise ValueError("結果檔包含不正確的 Markdown 檔名。")
        if not isinstance(page.facts, list) or not all(isinstance(item, str) for item in page.facts):
            raise ValueError("結果檔的重要訊息格式不正確。")
        pages.append(page)
    return pages


async def crawl_batch(urls: list[str], output: Path, delay: float, timeout: int,
                      selector: str, stop: threading.Event,
                      emit: Callable[[str, object], None], retries: int = 1,
                      summary_mode: str = "basic", model: str = DEFAULT_MODEL,
                      pasted_text: str | None = None, provider=None,
                      analyze_frames: bool = False, vision_model: str = "") -> list[Page]:
    # Delay heavy imports until a job starts so the desktop opens immediately.
    from bs4 import BeautifulSoup
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    from insights import source_markdown, summarize
    from video import fetch_video, youtube_id
    from ai_providers import AIProviderConfig, create_provider, validate_provider_config

    validate_provider_config(AIProviderConfig(summary_mode, model))
    if summary_mode != 'basic':
        provider = provider or create_provider(AIProviderConfig(summary_mode, model))
        if provider.name != summary_mode:
            raise ValueError('AI 供應商與摘要方式不一致')

    if not 0.5 <= delay <= 60 or not 5 <= timeout <= 180:
        raise ValueError("間隔需為 0.5–60 秒，逾時需為 5–180 秒。")
    if not isinstance(retries, int) or not 0 <= retries <= 2:
        raise ValueError("自動重試需為 0–2 次。")
    urls = parse_urls("\n".join(urls)) if pasted_text is None else ["使用者貼上的文字／字幕"]
    folder = output / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:6])
    folder.mkdir(parents=True, exist_ok=False)
    pages: list[Page] = []
    emit("folder", str(folder))
    save_results(folder, pages)

    def save_manifest(state: str, error: str = ""):
        completed = {p.url for p in pages}
        data = {"version": 3, "state": state, "urls": urls,
                "pending_urls": [url for url in urls if url not in completed],
                "summary_pending_urls": [p.url for p in pages if p.success and not p.summary],
                "completed": len(pages), "error": error,
                "ai_provider": summary_mode, "ai_model": model if summary_mode != 'basic' else '',
                "analyze_frames": bool(analyze_frames)}
        temp = folder / "run.json.tmp"
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(folder / "run.json")

    save_manifest("running")

    async def fetch(crawler, url: str) -> Page:
        page = Page(url=url, crawled_at=datetime.now().astimezone().isoformat(timespec="seconds"))
        started = time.monotonic()
        for attempt in range(retries + 1):
            page.attempts = attempt + 1
            transient = False
            try:
                result = await asyncio.wait_for(crawler.arun(
                    url=url, config=CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS, check_robots_txt=True,
                        page_timeout=timeout * 1000, wait_until="domcontentloaded",
                        delay_before_return_html=0.5, css_selector=selector or None,
                        word_count_threshold=0, verbose=False,
                        excluded_tags=['nav', 'footer', 'header', 'aside'],
                    ),
                ), timeout=timeout + 10)
                page.status_code = result.status_code
                page.final_url = getattr(result, "redirected_url", None) or result.url
                page.success = bool(result.success) and (not page.status_code or page.status_code < 400)
                if page.success:
                    title = BeautifulSoup(result.html or "", "html.parser").title
                    page.title = title.get_text(" ", strip=True) if title else urlsplit(url).hostname or url
                    page.markdown = str(result.markdown or "")
                    if not page.markdown.strip():
                        page.success = False
                        page.error = "頁面沒有可擷取的文字；請檢查 CSS 範圍或網站內容。"
                    else:
                        page.error = ""
                    break
                page.error = result.error_message or f"HTTP {page.status_code}"
                transient = page.status_code in (408, 500, 502, 503, 504) or (not page.status_code and any(s in page.error.lower() for s in ("timeout", "timed out", "net::err_connection")))
            except asyncio.TimeoutError:
                page.success, page.error, transient = False, "頁面載入逾時。", True
            except Exception as exc:
                page.success, page.error = False, str(exc)
                transient = any(s in page.error.lower() for s in ("timeout", "timed out", "net::err_connection"))
            if stop.is_set() or not transient or attempt == retries:
                break
            emit("retry", (url, attempt + 1))
            await asyncio.sleep(max(delay, 2 * (attempt + 1)))
        page.elapsed_seconds = round(time.monotonic() - started, 2)
        return page

    async def work():
        from contextlib import AsyncExitStack
        async with AsyncExitStack() as stack:
            crawler = None
            for index, url in enumerate(urls):
                if stop.is_set():
                    break
                emit("fetch", (index, url))
                if pasted_text is not None:
                    page = Page(url=url, title="貼上文字摘要", source_type="text", success=bool(pasted_text.strip()), markdown=pasted_text, attempts=1, crawled_at=datetime.now().astimezone().isoformat(timespec="seconds"))
                else:
                    try:
                        video_id = youtube_id(url)
                        if video_id:
                            emit("stage", "正在取得 YouTube 字幕；若沒有字幕會改用本機語音轉文字…")
                            begin = time.monotonic()
                            frame_dir = folder / f"{index + 1:03d}_frames" if analyze_frames else None
                            data = await fetch_video(video_id, timeout, lambda message: emit("stage", message), frame_dir)
                            page = Page(url=url, final_url=f"https://www.youtube.com/watch?v={video_id}", title=data["title"], source_type="youtube", success=True, markdown=data["markdown"], language=data["language"], attempts=1, elapsed_seconds=round(time.monotonic() - begin, 2), crawled_at=datetime.now().astimezone().isoformat(timespec="seconds"))
                            if data.get("audio_transcribed"):
                                page.summary_warning = "影片未提供字幕；此內容由本機 Whisper 語音轉文字產生，可能有辨識錯誤。暫存音訊已在轉錄後刪除。"
                            elif data.get("generated"):
                                page.summary_warning = "來源為 YouTube 自動字幕，可能有辨識錯誤。"
                            if data.get("frame_warning"):
                                page.summary_warning = "\n".join(filter(None, [page.summary_warning, data["frame_warning"]]))
                            page._frames = data.get("frames", [])
                        else:
                            if crawler is None:
                                from secure_browser import verified_strategy
                                config = BrowserConfig(headless=True, verbose=False, ignore_https_errors=False, user_agent="LocalCrawler/3.4")
                                crawler = await stack.enter_async_context(AsyncWebCrawler(config=config, crawler_strategy=verified_strategy(config)))
                            page = await fetch(crawler, url)
                    except (ValueError, asyncio.TimeoutError) as exc:
                        page = Page(url=url, source_type="youtube", error=str(exc) or "字幕讀取逾時。", attempts=1)
                if page.success:
                    slug = re.sub(r"[^\w-]", "_", page.title)[:36] or "page"
                    page.file = f"{index + 1:03d}_{slug}.md"
                    (folder / page.file).write_text(page.markdown, encoding="utf-8")
                    # Persist the original first: cancelling AI must not lose fetched content.
                    page.summary_mode = "尚未完成"
                    pages.append(page)
                    save_results(folder, pages)
                    emit("page", page)
                    emit("stage", f"正在整理重點 · {page.title[:50]}")
                    insight = await summarize(page.markdown, page.final_url or page.url, summary_mode, model, lambda message: emit("stage", message), provider=provider, title=page.title, source_type=page.source_type)
                    frames = getattr(page, "_frames", [])
                    if frames:
                        from video_frames import render_gallery
                        from visual_insights import export_frame_sources
                        export_frame_sources(frames, frame_dir, video_id, page.markdown)
                        visual = render_gallery(frames, video_id, frame_dir.name)
                        if summary_mode != "basic":
                            try:
                                from visual_insights import summarize_frames
                                emit("stage", f"{page.title[:40]} · 正在理解投影片、圖表與畫面…")
                                visual = await summarize_frames(provider, vision_model or model, frames, frame_dir, video_id, page.markdown) + "\n\n" + visual
                            except Exception as exc:
                                visual = "畫面 AI 分析未完成；以下關鍵影格仍可人工核對。\n\n" + visual
                                reason = str(exc) if type(exc).__name__ == "ProviderError" else "視覺分析發生未預期錯誤。"
                                page.summary_warning = "\n".join(filter(None, [page.summary_warning, reason]))
                        insight.summary += "\n\n" + visual
                    page.summary, page.summary_mode = insight.summary, insight.mode
                    page.summary_warning = "\n".join(filter(None, [page.summary_warning, insight.warning]))
                    page.facts = insight.facts
                    page.summary_file = f"{index + 1:03d}_summary.md"
                    page.sources_file = f"{index + 1:03d}_sources.md"
                    report = f"# {page.title}\n\n來源：{page.final_url or page.url}\n\n方式：{page.summary_mode}\n\n{page.summary_warning}\n\n{page.summary}\n\n核對原文：{page.sources_file}\n"
                    (folder / page.summary_file).write_text(report, encoding="utf-8")
                    (folder / page.sources_file).write_text(source_markdown(insight.sources), encoding="utf-8")
                else:
                    pages.append(page)
                save_results(folder, pages)
                save_manifest("running")
                emit("updated" if page.success else "page", page)
                if index + 1 < len(urls):
                    await asyncio.sleep(delay)
            if not stop.is_set() and len([p for p in pages if p.success]) >= 2:
                from comparison import compare_pages
                emit("stage", "正在合併各來源，整理共通點與差異…")
                report = await compare_pages(pages, folder, summary_mode, model, lambda message: emit("stage", message), provider=provider)
                if report:
                    emit("comparison", report)

    task = asyncio.create_task(work())
    final_state, final_error = "completed", ""
    try:
        while not task.done():
            if stop.is_set():
                task.cancel()
                break
            await asyncio.sleep(0.1)
        await task
    except asyncio.CancelledError:
        final_state = "stopped"
        if not stop.is_set():
            raise
    except Exception as exc:
        final_state, final_error = "failed", str(exc)
        raise
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        save_results(folder, pages)
        save_manifest("stopped" if stop.is_set() else final_state, final_error)
    return pages
