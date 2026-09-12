import asyncio
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import crawl_batch, load_results
from insights import source_units, summarize
from video import format_transcript, youtube_id


class InsightTests(unittest.TestCase):
    def test_structured_ai_and_invalid_source(self):
        import httpx
        text = "本次活動在 2026/10/01 開始，報名費用 300 元。"
        item = {"text": "報名費為 300 元", "sources": ["S001"]}
        payload = {"overview": item, "points": [item], "facts": [item], "uncertainties": "未提供"}
        def response():
            return httpx.Response(200, request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"), json={"message": {"content": json.dumps(payload)}, "done_reason": "stop"})
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response())):
            result = asyncio.run(summarize(text, "https://example.com", "ollama"))
        self.assertTrue(result.mode.startswith("本機 AI"))
        self.assertIn("[S001]", result.summary)
        item["sources"] = ["S999"]
        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response())):
            result = asyncio.run(summarize(text, "https://example.com", "ollama"))
        self.assertEqual(result.mode, "基本摘錄")
        self.assertIn("來源編號", result.warning)

    def test_video_url_and_timestamps(self):
        for url in ("https://www.youtube.com/watch?v=abcdefghijk", "https://youtu.be/abcdefghijk?t=3", "https://youtube.com/shorts/abcdefghijk"):
            self.assertEqual(youtube_id(url), "abcdefghijk")
        self.assertIsNone(youtube_id("https://youtube.com.example.org/watch?v=abcdefghijk"))
        with self.assertRaises(ValueError):
            youtube_id("https://youtube.com/playlist?list=x")
        md = format_transcript([{"start": 65.9, "text": "重要訊息：報名截止 2026/10/01。"}], "abcdefghijk")
        self.assertIn("00:01:05", md)
        self.assertIn("&t=65s", md)
        self.assertEqual(source_units(md, "fallback")[0]["url"], "https://www.youtube.com/watch?v=abcdefghijk&t=65s")

    def test_basic_summary_and_ai_failure(self):
        text = "本次活動在 2026/10/01 開始，報名費用 300 元。\n請於截止日前完成登記，活動提供三場技術講座。"
        summary = asyncio.run(summarize(text, "https://example.com"))
        self.assertEqual(summary.mode, "基本摘錄")
        self.assertIn("300 元", summary.summary)
        self.assertTrue(summary.facts)
        import httpx
        with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=httpx.ConnectError("offline"))):
            fallback = asyncio.run(summarize(text, "https://example.com", "ollama"))
        self.assertIn("已改用基本摘錄", fallback.warning)
        self.assertNotIn("本機 AI ·", fallback.mode)

    def test_video_pipeline_without_browser(self):
        fake = {"title": "示範講座", "language": "zh-TW", "generated": True, "markdown": format_transcript([{"start": 10, "text": "活動報名截止日期為 2026/10/01，費用是 300 元。"}], "abcdefghijk")}
        with tempfile.TemporaryDirectory() as temp, patch("video.fetch_video", new=AsyncMock(return_value=fake)), patch("crawl4ai.AsyncWebCrawler") as browser:
            events = []
            pages = asyncio.run(crawl_batch(["https://youtu.be/abcdefghijk"], Path(temp), 1, 10, "", threading.Event(), lambda k,d: events.append((k,d))))
            browser.assert_not_called()
            self.assertTrue(pages[0].success)
            self.assertEqual(pages[0].source_type, "youtube")
            self.assertIn("自動字幕", pages[0].summary_warning)
            folder = Path(next(d for k,d in events if k == "folder"))
            self.assertTrue((folder / pages[0].summary_file).exists())
            self.assertTrue((folder / pages[0].sources_file).exists())
            self.assertEqual(load_results(folder / "results.json")[0].summary, pages[0].summary)

    def test_cancel_ai_preserves_original(self):
        stop = threading.Event()
        async def slow_summary(*args, **kwargs):
            stop.set()
            await asyncio.sleep(20)
        with tempfile.TemporaryDirectory() as temp, patch("insights.summarize", new=slow_summary):
            events = []
            pages = asyncio.run(crawl_batch([], Path(temp), 1, 10, "", stop, lambda k,d: events.append((k,d)), pasted_text="這是一份足夠長的原始資料，停止 AI 仍應保留。"))
            self.assertEqual(len(pages), 1)
            folder = Path(next(d for k,d in events if k == "folder"))
            self.assertTrue((folder / pages[0].file).exists())
            self.assertTrue(load_results(folder / "results.json")[0].markdown)
            self.assertFalse(pages[0].summary)


if __name__ == "__main__":
    unittest.main()
