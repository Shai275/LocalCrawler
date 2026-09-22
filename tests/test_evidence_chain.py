import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evidence_chain import export_chain, digest, verify_chain
from visual_insights import caption_contexts
from resource_policy import THREADS, worker_environment


class EvidenceTests(unittest.TestCase):
    def test_exact_caption_image_hash_and_html_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder/'F001.jpg').write_bytes(b'evidence')
            (folder/'transcript.json').write_text(json.dumps({'snippets': [
                {'start': 65.375, 'duration': 1.125, 'text': '得分九分'}]}), encoding='utf-8')
            frames = [{'id': 'F001', 'file': 'F001.jpg', 'seconds': 66, 'decoded_seconds': 66.04}]
            notes = [{'frame_id': 'F001', 'caption': '得分九分', 'visual_evidence': '<script>bad</script>',
                      'title': '比分', 'ocr': '九分', 'shared': '九分'}]
            records = export_chain(folder, 'abcdefghijk', frames, notes, '', 'ollama', 'test')
            self.assertEqual(records[0]['caption_start'], 65.375)
            page = (folder/'evidence.html').read_text(encoding='utf-8')
            self.assertIn('&amp;t=65s', page)
            self.assertIn('1 項共同文字', page)
            self.assertIn('timeline', page)
            self.assertNotIn('<script>bad', page)
            self.assertEqual(records[0]['frame_sha256'], digest(folder/'F001.jpg'))
            self.assertEqual(verify_chain(folder), [])
            (folder/'F001.jpg').write_bytes(b'tampered')
            self.assertIn('Hash mismatch: F001.jpg', verify_chain(folder))
            self.assertNotEqual(records[0]['frame_sha256'], digest(folder/'F001.jpg'))

    def test_far_caption_is_not_associated(self):
        text = '[00:00:01](https://www.youtube.com/watch?v=abcdefghijk&t=1s) 遠方字幕'
        self.assertEqual(caption_contexts(text, '', [{'id':'F001', 'seconds':100}])['F001'], [])

    def test_threads_and_environment_are_bounded(self):
        self.assertIn(THREADS, (1, 2))
        self.assertEqual(worker_environment()['OMP_NUM_THREADS'], str(THREADS))

    def test_fractional_caption_interval_uses_decoded_time(self):
        snippets = [{'text': '跨行\n字幕', 'start': 10.25, 'duration': 20.5},
                    {'text': '太晚', 'start': 50, 'duration': 1}]
        result = caption_contexts('', '', [{'id': 'F001', 'seconds': 1, 'decoded_seconds': 25}], snippets=snippets)
        self.assertEqual(result['F001'][0]['seconds'], 10.25)
        self.assertEqual(result['F001'][0]['text'], '跨行 字幕')
        self.assertEqual(len(result['F001']), 1)

    def test_html_and_fallback_transcript_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            export_chain(folder, 'abcdefghijk', [], [], '逐字稿\n第二行\n', 'basic', '')
            self.assertEqual(verify_chain(folder), [])
            (folder/'evidence.html').write_text('changed', encoding='utf-8')
            self.assertIn('Hash mismatch: evidence.html', verify_chain(folder))
