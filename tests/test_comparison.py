import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison import compare_pages, validate_comparison
from engine import Page
from insights import Insight


class ComparisonTests(unittest.TestCase):
    def test_comparison_uses_all_sources_and_exports_reports(self):
        pages = [
            Page(url="https://a.example", title="A", success=True, markdown="活動在十月開始，費用是 300 元。"),
            Page(url="https://b.example", title="B", success=True, markdown="活動費用是 300 元，但是十一月才開始。"),
        ]
        async def fake_summary(*args, **kwargs):
            answer = {'common': [{'text': '兩份資料都指出活動費用為三百元。', 'sources': ['S001', 'S002']}], 'differences': [], 'unique': []}
            args[-1](answer)
            return answer
        with tempfile.TemporaryDirectory() as temp, patch("comparison.structured_reply", new=fake_summary):
            report = asyncio.run(compare_pages(pages, Path(temp), "ollama", "test", None))
            self.assertIn("方式：本機 AI · test", report)
            self.assertIn("三百元", report)
            self.assertTrue((Path(temp) / "batch_summary.md").is_file())
            self.assertTrue((Path(temp) / "batch_sources.md").is_file())

    def test_common_requires_distinct_documents(self):
        units = [{'id': 'S001', 'document': 1}, {'id': 'S002', 'document': 1}]
        answer = {'common': [{'text': '兩份文件都確認售價相同。', 'sources': ['S001', 'S002']}], 'differences': [], 'unique': []}
        with self.assertRaisesRegex(ValueError, '不同文件'):
            validate_comparison(answer, units)
        answer['common'][0]['sources'] = ['S999']
        with self.assertRaisesRegex(ValueError, '來源編號'):
            validate_comparison(answer, units)
