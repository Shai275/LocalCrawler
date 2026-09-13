"""Offline provider contracts and privacy boundaries: never use real API keys."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from ai_providers import AIProviderConfig, ProviderError, create_provider
from insights import summarize
from comparison import compare_pages
from engine import Page, crawl_batch

KEY = 'test-secret-not-a-real-key'
TEXT = '活動在十月開始，報名費用為三百元，請提早完成報名。'


def summary_payload():
    item = {'text': '活動報名費用為三百元。', 'sources': ['S001']}
    return {'overview': item, 'points': [item], 'facts': [], 'uncertainties': '未提供'}


def response(provider, payload, status=200):
    raw = json.dumps(payload)
    data = {'message': {'content': raw}, 'done_reason': 'stop'}
    if provider == 'openai':
        data = {'choices': [{'finish_reason': 'stop', 'message': {'content': raw}}]}
    elif provider == 'gemini':
        data = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': raw}]}}]}
    if status != 200:
        data = {'error': KEY}
    return httpx.Response(status, request=httpx.Request('POST', 'https://example.test'), json=data)


class CloudTests(unittest.TestCase):
    def backend(self, name):
        return create_provider(AIProviderConfig(name, 'test-model'), api_key=KEY, cloud_allowed=True)

    def test_each_provider_generates_verified_source_summary(self):
        for name in ('ollama', 'openai', 'gemini'):
            with self.subTest(provider=name), patch('httpx.AsyncClient.post', new=AsyncMock(return_value=response(name, summary_payload()))) as post:
                result = asyncio.run(summarize(TEXT, 'https://example.com', name, 'test-model', provider=self.backend(name)))
                self.assertNotEqual(result.mode, '基本摘錄')
                self.assertIn('[S001](https://example.com)', result.summary)
                args, kwargs = post.call_args
                self.assertNotIn(KEY, args[0])
                self.assertNotIn(KEY, json.dumps(kwargs['json']))
                if name == 'openai':
                    self.assertEqual(kwargs['headers']['Authorization'], 'Bearer ' + KEY)
                    self.assertTrue(kwargs['json']['response_format']['json_schema']['strict'])
                    self.assertFalse(kwargs['json']['store'])
                if name == 'gemini':
                    self.assertEqual(kwargs['headers']['x-goog-api-key'], KEY)
                    self.assertIn('responseJsonSchema', kwargs['json']['generationConfig'])

    def test_cloud_requires_consent_and_secret(self):
        for name in ('openai', 'gemini'):
            with self.assertRaises(ProviderError):
                create_provider(AIProviderConfig(name, 'model'), api_key=KEY)
            with self.assertRaises(ProviderError):
                create_provider(AIProviderConfig(name, 'model'), cloud_allowed=True)
        with self.assertRaises(ProviderError):
            create_provider(AIProviderConfig('openai', 'model', 'https://attacker.test'), api_key=KEY, cloud_allowed=True)
        self.assertNotIn(KEY, repr(self.backend('openai')))

    def test_auth_and_quota_errors_stop_later_requests_and_hide_response(self):
        for status in (401, 403, 429, 500):
            backend = self.backend('openai')
            with patch('httpx.AsyncClient.post', new=AsyncMock(return_value=response('openai', {}, status))) as post:
                first = asyncio.run(summarize(TEXT, 'https://example.com', 'openai', 'test-model', provider=backend))
                second = asyncio.run(summarize(TEXT, 'https://example.com', 'openai', 'test-model', provider=backend))
                self.assertEqual(first.mode, '基本摘錄')
                self.assertEqual(second.mode, '基本摘錄')
                self.assertEqual(post.await_count, 1)
                self.assertNotIn(KEY, first.warning + second.warning)

    def test_invalid_citations_are_retried_once_and_never_accepted(self):
        bad = summary_payload()
        bad['overview']['sources'] = ['S999']
        with patch('httpx.AsyncClient.post', new=AsyncMock(return_value=response('gemini', bad))) as post:
            result = asyncio.run(summarize(TEXT, 'https://example.com', 'gemini', 'test-model', provider=self.backend('gemini')))
            self.assertEqual(result.mode, '基本摘錄')
            self.assertEqual(post.await_count, 2)

    def test_cross_source_comparison_uses_selected_cloud_provider(self):
        pages = [Page(url=f'https://example.com/{n}', title=str(n), success=True, markdown=TEXT) for n in (1, 2)]
        payload = {'common': [{'text': '兩份來源都指出報名費用為三百元。', 'sources': ['S001', 'S002']}], 'differences': [], 'unique': []}
        for name in ('openai', 'gemini'):
            with tempfile.TemporaryDirectory() as temp, patch('httpx.AsyncClient.post', new=AsyncMock(return_value=response(name, payload))):
                report = asyncio.run(compare_pages(pages, Path(temp), name, 'test-model', None, provider=self.backend(name)))
                self.assertNotIn('比較未完成', report)
                self.assertIn('S002', report)
                self.assertNotIn(KEY, ''.join(p.read_text(encoding='utf-8') for p in Path(temp).iterdir()))

    def test_cloud_pipeline_preserves_raw_text_after_api_failure(self):
        with tempfile.TemporaryDirectory() as temp, patch('httpx.AsyncClient.post', new=AsyncMock(return_value=response('openai', {}, 429))):
            results = asyncio.run(crawl_batch([], Path(temp), 1, 10, '', threading.Event(), lambda *a: None,
                summary_mode='openai', model='test-model', pasted_text=TEXT, provider=self.backend('openai')))
            self.assertTrue(results[0].success)
            self.assertEqual(results[0].summary_mode, '基本摘錄')
            files = list(Path(temp).rglob('*.md')) + list(Path(temp).rglob('*.json'))
            saved = ''.join(p.read_text(encoding='utf-8') for p in files)
            self.assertIn(TEXT, saved)
            self.assertNotIn(KEY, saved)

    def test_cancel_propagates_without_retry(self):
        with patch('httpx.AsyncClient.post', new=AsyncMock(side_effect=asyncio.CancelledError)) as post:
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(summarize(TEXT, 'https://example.com', 'openai', 'test-model', provider=self.backend('openai')))
            self.assertEqual(post.await_count, 1)

    def test_vault_is_explicit_and_provider_keys_are_separate(self):
        import credentials
        from unittest.mock import MagicMock
        vault = MagicMock()
        vault.get_password.return_value = KEY
        with patch.object(credentials, '_vault', return_value=vault):
            credentials.save_key('openai', KEY)
            self.assertEqual(credentials.load_key('gemini'), KEY)
            credentials.delete_key('openai')
            vault.set_password.assert_called_once_with('LocalCrawler.AI', 'openai', KEY)
            vault.get_password.assert_any_call('LocalCrawler.AI', 'gemini')
            vault.delete_password.assert_called_once_with('LocalCrawler.AI', 'openai')


if __name__ == '__main__':
    unittest.main()
