import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from video import format_transcript
from video_insights import video_units, selected_units, validate_notes, QualityError
from insights import source_units, summarize
from ai_providers import create_provider, AIProviderConfig
from test_cloud_ai import response


class VideoNoteTests(unittest.TestCase):
    def test_simplified_evidence_matches_traditional_caption(self):
        units = [{'id': 'S001', 'text': '阿伯直接按投籃鍵就可以了'}]
        note = {'title': '操作投籃鍵', 'text': '字幕指示阿伯直接按投籃鍵。', 'sources': ['S001'], 'evidence': '阿伯直接按投篮键就可以了'}
        answer = {'notes': [note], 'uncertainties': ''}
        validate_notes(answer, units)
        self.assertEqual(len(answer['points']), 1)

    def test_valid_note_survives_bad_item_and_cross_block_quote(self):
        units = [
            {'id': 'S001', 'text': '受訪者第一次玩這個遊戲。'},
            {'id': 'S002', 'text': '主持人說你拿了9分，最後可惜被絕殺。'},
        ]
        good = {'title': '首次遊玩拿九分', 'text': '片中受訪者第一次玩這個遊戲，主持人說他拿了9分。', 'sources': ['S001'], 'evidence': '第一次玩這個遊戲。 主持人說你拿了9分'}
        bad = dict(good, evidence='虛構而不存在的原句')
        answer = {'notes': [good, bad], 'uncertainties': ''}
        validate_notes(answer, units)
        self.assertEqual(len(answer['points']), 1)
        self.assertEqual(answer['points'][0]['sources'], ['S001', 'S002'])
        self.assertGreater(answer['_dropped'], 0)

    def test_timestamp_inherited_for_second_sentence(self):
        text = format_transcript([{'start': 65, 'text': '第一句包含重要資訊。第二句提供具體細節。'}], '8NYdGenlji8')
        units = source_units(text, 'fallback')
        self.assertGreaterEqual(len(units), 2)
        self.assertTrue(all(u['url'].endswith('&t=65s') for u in units))

    def test_captions_join_and_long_video_includes_ending(self):
        snippets = [{'start': i*40, 'text': '講者說明具體的例子與限制。'*30} for i in range(120)]
        units = video_units(format_transcript(snippets, '8NYdGenlji8'), 'url')
        selected, sampled = selected_units(units, 3000)
        self.assertTrue(sampled)
        self.assertEqual(selected[-1]['seconds'], snippets[-1]['start'])
        self.assertLessEqual(sum(len(u['text']) for u in selected), 3000)

    def test_reject_vague_or_fabricated_evidence(self):
        units = [{'id': 'S001', 'text': '片中說角色洪壽攻框動作慢，大招容易被蓋帽。', 'url': 'url'}]
        item = {'text': '講者說洪壽攻框動作慢，而且大招容易被蓋帽，這是玩家不愛用他的原因。', 'sources': ['S001'], 'evidence': '大招容易被蓋帽'}
        answer = {'outline': [], 'points': [item], 'uncertainties': ''}
        validate_notes(answer, units)
        item['evidence'] = '不存在的原文證據'
        with self.assertRaises(QualityError):
            validate_notes(answer, units)
        item['evidence'] = '大招容易被蓋帽'
        item['text'] = '影片介紹了一些重要的角色選擇技巧'
        with self.assertRaises(QualityError):
            validate_notes(answer, units)

    def test_gemini_video_notes_have_outline_details_and_time(self):
        text = format_transcript([{'start': 65, 'text': '片中說角色洪壽攻框動作慢，大招容易被蓋帽。'}], '8NYdGenlji8')
        item = {'text': '講者以洪壽攻框動作慢、大招容易被蓋帽，解釋玩家不愛選這個角色的理由。', 'sources': ['S001'], 'evidence': '大招容易被蓋帽'}
        payload = {'notes': [dict(item, title='洪壽為何不受歡迎')], 'uncertainties': '字幕不能證明實際遊戲平衡。'}
        provider = create_provider(AIProviderConfig('gemini', 'test-model'), api_key='fake-key', cloud_allowed=True)
        with patch('httpx.AsyncClient.post', new=AsyncMock(side_effect=[response('gemini', payload), response('gemini', {'supported': True, 'reason': '字幕有交代角色弱點。'})])):
            result = asyncio.run(summarize(text, 'url', 'gemini', 'test-model', provider=provider, title='遊戲角色', source_type='youtube'))
        self.assertIn('影片大綱', result.summary)
        self.assertIn('大招容易被蓋帽', result.summary)
        self.assertIn('[00:01:05]', result.summary)
        self.assertIn('字幕依據', result.summary)

    def test_unsupported_claim_becomes_explicit_raw_excerpt(self):
        text = format_transcript([{'start': 72, 'text': '公園阿伯，你今晚的噩夢。'}], '8NYdGenlji8')
        note = {'title': '名字的由來', 'text': '這句話就是洪壽名字的由來。', 'evidence': '公園阿伯，你今晚的噩夢', 'sources': ['S001']}
        provider = create_provider(AIProviderConfig('gemini', 'test-model'), api_key='fake-key', cloud_allowed=True)
        with patch('httpx.AsyncClient.post', new=AsyncMock(side_effect=[response('gemini', {'notes': [note], 'uncertainties': ''}), response('gemini', {'supported': False, 'reason': '原文沒有說明名字由來。'})])):
            result = asyncio.run(summarize(text, 'url', 'gemini', 'test-model', provider=provider, source_type='youtube'))
        self.assertNotIn('名字的由來', result.summary)
        self.assertIn('原句參考（AI 解讀未通過核對）', result.summary)
        self.assertIn('公園阿伯，你今晚的噩夢', result.summary)
