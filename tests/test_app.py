"""Controller checks against real Tk widgets; no third-party app automation."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from engine import Page


class AppTests(unittest.TestCase):
    def test_filter_preview_failure_and_settings(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app, "PREFERENCES", Path(temp) / "settings.json"):
            window = app.App()
            window.withdraw()
            try:
                self.assertFalse(window.advanced.winfo_manager())
                window.toggle_advanced()
                self.assertEqual(window.advanced.winfo_manager(), 'pack')
                window.toggle_advanced()
                window.pages = [Page(url="https://example.com/", title="Example", success=True, markdown="本文 Alpha", file="001.md"), Page(url="https://example.com/missing", error="HTTP 404")]
                window.refresh_table()
                self.assertEqual(len(window.table.get_children()), 2)
                window.filter.set("失敗")
                self.assertEqual(window.table.get_children(), ("1",))
                window.filter.set("全部")
                window.search.set("alpha")
                self.assertEqual(window.table.get_children(), ("0",))
                window.table.selection_set("0")
                window.preview()
                self.assertIn("本文 Alpha", window.preview_text.get("1.0", "end"))
                window.folder = Path(temp)
                (Path(temp) / 'batch_summary.md').write_text('整批共通點內容', encoding='utf-8')
                window.preview_mode.set('整批比較')
                self.assertIn('整批共通點內容', window.preview_text.get('1.0', 'end'))
                window.preview_mode.set('重點摘要')
                window.search.set("no match")
                self.assertFalse(window.table.get_children())
                self.assertIn("disabled", window.copy_button.state())
                window.total = 2
                window.events.put(("fatal", "Disk unavailable"))
                window.events.put(("done", None))
                with patch.object(app.messagebox, "showerror"):
                    window.poll()
                self.assertTrue(window.status.get().startswith("作業失敗"))
                window.retries.set("2")
                window.save_preferences()
                self.assertTrue(app.PREFERENCES.exists())
            finally:
                window.destroy()
            reopened = app.App()
            reopened.withdraw()
            try:
                self.assertEqual(reopened.retries.get(), "2")
            finally:
                reopened.destroy()


if __name__ == "__main__":
    unittest.main()
