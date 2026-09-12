import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Page, crawl_batch, load_results, parse_urls, save_results


class Handler(BaseHTTPRequestHandler):
    flaky_hits = 0

    def do_GET(self):
        if self.path == "/robots.txt":
            status, body = 200, b"User-agent: *\nDisallow: /blocked\n"
        elif self.path == "/missing":
            status, body = 404, b"Not found"
        elif self.path == "/flaky" and Handler.flaky_hits == 0:
            Handler.flaky_hits += 1
            status, body = 503, b"Temporary service failure"
        else:
            status = 200
            body = ('<html><head><title>本機測試</title></head><body><main><h1>測試網頁</h1><p id="dynamic"></p><p>' + 'This local document verifies that browser rendering and UTF-8 export work correctly. ' * 8 + '</p></main><script>document.getElementById("dynamic").textContent="JavaScript rendered successfully";</script></body></html>').encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8" if self.path == "/robots.txt" else "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class Tests(unittest.TestCase):
    def test_history_validation_and_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            save_results(folder, [Page(url="https://example.com/", title="=1+1", success=True, file="001_page.md")])
            restored = load_results(folder / "results.json")
            self.assertEqual(restored[0].title, "=1+1")
            self.assertIn("'=1+1", (folder / "results.csv").read_text(encoding="utf-8-sig"))
            save_results(folder, [Page(url="https://example.com/", file="../outside.md")])
            with self.assertRaises(ValueError):
                load_results(folder / "results.json")

    def test_input(self):
        self.assertEqual(parse_urls("https://example.com\nhttps://example.com/#x"), ["https://example.com/"])
        for invalid in ("", "file:///tmp/a", "hello", "https://user:secret@example.com", "https://example.com:bad"):
            with self.assertRaises(ValueError):
                parse_urls(invalid)

    def test_real_browser_export_errors_and_stop(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with tempfile.TemporaryDirectory() as temp:
                events = []
                pages = asyncio.run(crawl_batch([base, base + "/missing", base + "/blocked"], Path(temp), .5, 10, "", threading.Event(), lambda k, d: events.append((k, d))))
                self.assertEqual(len(pages), 3)
                self.assertTrue(pages[0].success, pages[0].error)
                self.assertEqual(pages[0].title, "本機測試")
                self.assertIn("JavaScript rendered successfully", pages[0].markdown)
                self.assertFalse(pages[1].success)
                self.assertEqual(pages[1].status_code, 404)
                self.assertFalse(pages[2].success)
                folder = Path(next(d for k, d in events if k == "folder"))
                self.assertEqual(len(json.loads((folder / "results.json").read_text(encoding="utf-8"))), 3)
                self.assertTrue((folder / pages[0].file).exists())
                self.assertTrue((folder / "results.csv").read_bytes().startswith(b"\xef\xbb\xbf"))
                self.assertEqual(len(load_results(folder / "results.json")), 3)
                self.assertEqual(json.loads((folder / "run.json").read_text())["state"], "completed")
                self.assertEqual(pages[1].attempts, 1)
                self.assertEqual(pages[2].attempts, 1)
                Handler.flaky_hits = 0
                retried = asyncio.run(crawl_batch([base + "/flaky"], Path(temp), .5, 10, "", threading.Event(), lambda *_: None, retries=1))
                self.assertTrue(retried[0].success, retried[0].error)
                self.assertEqual(retried[0].attempts, 2)
                stop = threading.Event()
                def cancel_after_page(kind, data):
                    if kind == "page":
                        stop.set()
                cancelled = asyncio.run(crawl_batch([base, base + "/second"], Path(temp), 1, 10, "main", stop, cancel_after_page))
                self.assertEqual(len(cancelled), 1)
                self.assertTrue(cancelled[0].success)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
