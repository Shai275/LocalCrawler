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
    def test_evidence_view_blocks_modified_report(self):
        from evidence_chain import export_chain
        with tempfile.TemporaryDirectory() as temp, patch.object(app, 'PREFERENCES', Path(temp)/'settings.json'):
            window = app.App()
            window.withdraw()
            try:
                window.folder = Path(temp)
                folder = Path(temp)/'001_frames'
                folder.mkdir()
                export_chain(folder, 'abcdefghijk', [], [], '原文\n第二行', 'basic', '')
                window.pages = [Page(url='https://youtube.com/watch?v=abcdefghijk', success=True, summary_file='001_summary.md')]
                window.refresh_table()
                window.table.selection_set('0')
                with patch.object(app.webbrowser, 'open') as opened, patch.object(app.messagebox, 'showerror') as error:
                    window.open_evidence()
                    opened.assert_called_once()
                    error.assert_not_called()
                    opened.reset_mock()
                    (folder/'evidence.html').write_text('modified', encoding='utf-8')
                    window.open_evidence()
                    opened.assert_not_called()
                    error.assert_called_once()
            finally:
                window.destroy()

    def test_cloud_switching_secret_preferences_and_declined_send(self):
        import json
        with tempfile.TemporaryDirectory() as temp, patch.object(app, 'PREFERENCES', Path(temp) / 'settings.json'):
            window = app.App()
            window.withdraw()
            try:
                window.model.set('local-model')
                window.ai_mode.set('OpenAI API')
                window.change_provider()
                self.assertEqual(window.model.get(), '')
                window.model.set('cloud-model')
                window.session_keys['openai'] = 'test-private-key'
                window.ai_mode.set('Gemini API')
                window.change_provider()
                self.assertEqual(window.model.get(), '')
                window.ai_mode.set('OpenAI API')
                window.change_provider()
                self.assertEqual(window.model.get(), 'cloud-model')
                window.save_preferences()
                saved = app.PREFERENCES.read_text(encoding='utf-8')
                self.assertNotIn('test-private-key', saved)
                self.assertNotIn('session_keys', saved)
                self.assertEqual(json.loads(saved)['provider_models']['ollama'], 'local-model')
                with patch.object(app.messagebox, 'askyesno', return_value=False), patch.object(app, 'crawl_batch') as crawl:
                    window.start(pasted_text='這是測試文字，取消雲端傳送。')
                    crawl.assert_not_called()
                    self.assertIsNone(window.worker)
            finally:
                window.destroy()

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
