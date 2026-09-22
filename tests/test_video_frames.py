import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai_providers import AIProviderConfig, create_provider
from test_cloud_ai import response
from video_frames import choose_timestamps, candidate_timestamps, select_candidates, infer_layout_hints, render_gallery
from visual_insights import caption_contexts, matched_evidence, summarize_frames, adds_visual_information
from video import format_transcript


class VideoFrameTests(unittest.TestCase):
    def test_unsupported_number_gets_one_bounded_retry(self):
        bad = response('gemini', {'notes':[{'frame_id':'F001','title':'錯誤','visual_evidence':'圖表數值為99。'}]})
        good = response('gemini', {'notes':[{'frame_id':'F001','title':'圖表','visual_evidence':'藍色長條由左向右變高。'}]})
        provider = create_provider(AIProviderConfig('gemini', 'test-model'), api_key='fake-key', cloud_allowed=True)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder/'F001.jpg').write_bytes(b'test')
            frames = [{'id':'F001', 'seconds':10, 'file':'F001.jpg', 'ocr':['Q1 20']}]
            transcript = format_transcript([{'start':10, 'text':'Review results.'}], 'abcdefghijk')
            mocked = AsyncMock(side_effect=[bad, good])
            with patch('httpx.AsyncClient.post', new=mocked):
                report = asyncio.run(summarize_frames(provider, 'test-model', frames, folder, 'abcdefghijk', transcript))
            self.assertEqual(mocked.await_count, 2)
            self.assertIn('藍色長條', report)

    def test_empty_vision_result_keeps_layout_hints(self):
        provider = create_provider(AIProviderConfig('gemini', 'test-model'), api_key='fake-key', cloud_allowed=True)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder/'F001.jpg').write_bytes(b'test')
            frames = [{'id':'F001', 'seconds':10, 'file':'F001.jpg', 'ocr':['Q1','20'],
                       'layout_hints':['位置配對：Q1 ↔ 20']}]
            transcript = format_transcript([{'start':10, 'text':'Review the results.'}], 'abcdefghijk')
            with patch('httpx.AsyncClient.post', new=AsyncMock(return_value=response('gemini', {'notes':[]}))):
                report = asyncio.run(summarize_frames(provider, 'test-model', frames, folder, 'abcdefghijk', transcript))
            self.assertIn('Q1 ↔ 20', report)
            self.assertIn('請核對影格', report)
            self.assertIn('影格可見文字', report)
            self.assertTrue((folder/'evidence.html').exists())

    def test_ocr_layout_pairs_chart_labels_without_claiming_semantics(self):
        items = [
            {'text':'20','center':[100,100]}, {'text':'35','center':[200,70]},
            {'text':'Q1','center':[100,300]}, {'text':'Q2','center':[200,300]},
        ]
        hints = infer_layout_hints(items)
        self.assertIn('Q1 ↔ 20', hints[0])
        self.assertIn('Q2 ↔ 35', hints[0])
    def test_adaptive_candidates_keep_coverage_and_strong_slide(self):
        points = candidate_timestamps(600, max_frames=8)
        self.assertGreater(len(points), 8)
        self.assertLessEqual(len(candidate_timestamps(5400)), 48)
        items = [{'requested_seconds': second, 'selection_score': 1} for second in points]
        special = min(items, key=lambda item: abs(item['requested_seconds'] - 275))
        special['selection_score'] = 999
        selected = select_candidates(items, 600, 8)
        self.assertEqual(len(selected), 8)
        self.assertIn(special, selected)
        self.assertLess(selected[0]['requested_seconds'], 75)
        self.assertGreater(selected[-1]['requested_seconds'], 525)

    def test_repeated_caption_is_not_a_visual_insight(self):
        self.assertFalse(adds_visual_information({'visual_evidence':'阿伯我們拿了9分。'}, '阿伯我們拿了9分', '阿伯我們拿了9分'))
        self.assertFalse(adds_visual_information({'visual_evidence':'畫面字幕顯示阿伯拿了9分。'}, '阿伯我們拿了9分', '阿伯我們拿了9分'))
        self.assertTrue(adds_visual_information({'visual_evidence':'折線圖右側高於左側。'}, 'Q1 Q2', '營收提高'))
        self.assertFalse(adds_visual_information({'visual_evidence':'圖中得分為99。'}, '得分9', '拿了9分'))

    def test_chart_without_ocr_overlap_has_temporal_label(self):
        payload = {'notes': [{'frame_id': 'F001', 'title': '季度走勢', 'visual_evidence': '折線圖右側高於左側，數字無法辨讀。'}]}
        provider = create_provider(AIProviderConfig('gemini', 'test-model'), api_key='fake-key', cloud_allowed=True)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder/'F001.jpg').write_bytes(b'test')
            frames = [{'id':'F001', 'seconds':65, 'file':'F001.jpg', 'ocr':['Q1 Q2 Q3']}]
            transcript = format_transcript([{'start':65, 'text':'這段時間營收提高。'}], '8NYdGenlji8')
            with patch('httpx.AsyncClient.post', new=AsyncMock(return_value=response('gemini', payload))):
                report = asyncio.run(summarize_frames(provider, 'test-model', frames, folder, '8NYdGenlji8', transcript))
            self.assertIn('僅時間相鄰，內容關係尚未核實', report)
            self.assertIn('temporal-only', (folder/'evidence.json').read_text(encoding='utf-8'))

    def test_timestamps_are_bounded_and_cover_video(self):
        points = choose_timestamps(600, max_frames=8)
        self.assertLessEqual(len(points), 8)
        self.assertEqual(points, sorted(points))
        self.assertGreater(points[0], 0)
        self.assertGreater(points[-1], 540)
        with self.assertRaises(ValueError):
            choose_timestamps(6000)

    def test_gallery_links_images_and_youtube_time(self):
        result = render_gallery([{'id': 'F001', 'seconds': 65, 'file': 'F001.jpg'}], '8NYdGenlji8', '001_frames')
        self.assertIn('&t=65s', result)
        self.assertIn('智慧挑選', result)
        self.assertIn('001_frames/F001.jpg', result)

    def test_gemini_visual_request_and_report(self):
        payload = {'notes': [{'frame_id': 'F001', 'title': '得分與畫面相符',
            'visual_evidence': '記分板中央是白色大型數字，右側另有紅色隊伍標誌。'}]}
        provider = create_provider(AIProviderConfig('gemini', 'test-model'), api_key='fake-key', cloud_allowed=True)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'F001.jpg').write_bytes(b'jpeg-test')
            frames = [{'id': 'F001', 'seconds': 65, 'file': 'F001.jpg', 'ocr': ['阿伯我們拿了9分']}]
            transcript = format_transcript([{'start': 60, 'text': '主持人說阿伯我們拿了9分，第一次玩很有天分。'}], '8NYdGenlji8')
            with patch('httpx.AsyncClient.post', new=AsyncMock(return_value=response('gemini', payload))) as post:
                report = asyncio.run(summarize_frames(provider, 'test-model', frames, folder, '8NYdGenlji8', transcript))
            sent = post.await_args.kwargs['json']['contents'][0]['parts']
            self.assertIn('inlineData', sent[1])
            self.assertNotIn('jpeg-test', str(sent))
            self.assertIn('字幕＋畫面融合重點', report)
            self.assertIn('阿伯我們拿了9分', report)
            self.assertIn('[00:01:05]', report)

    def test_ocr_caption_match_requires_useful_overlap(self):
        captions = [{'text': '主持人說阿伯我們拿了9分'}]
        self.assertEqual(matched_evidence({'ocr': ['阿伯我們拿了9分']}, captions)[0], '阿伯我們拿了9分')
        self.assertEqual(matched_evidence({'ocr': ['畫面']}, captions)[0], '')

    def test_caption_context_is_near_frame(self):
        transcript = format_transcript([{'start': 5, 'text': '開場。'}, {'start': 100, 'text': '圖表顯示營收增加。'}], '8NYdGenlji8')
        result = caption_contexts(transcript, 'url', [{'id': 'F001', 'seconds': 100, 'file': 'x.jpg'}], window=10)
        self.assertIn('營收增加', result['F001'][0]['text'])
        self.assertNotIn('開場', result['F001'][0]['text'])


if __name__ == '__main__':
    unittest.main()
