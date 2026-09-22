import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image
from pypdf import PdfReader

from deliverables import export_deliverables


class DeliverableTests(unittest.TestCase):
    def test_all_formats_are_portable_and_traceable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Image.new('RGB', (320, 180), '#345678').save(root / 'frame.jpg')
            source = root / 'report.md'
            source.write_text(
                '# 研究報告\n\n## 發現\n\n- 有來源的結論\n\n'
                '![證據影格](frame.jpg)\n\n## 建議\n\n|項目|結果|\n|---|---|\n|驗證|通過|',
                encoding='utf-8')
            result = export_deliverables(source, '測試研究', 'https://example.com/source')
            self.assertGreaterEqual(len(PdfReader(result['pdf']).pages), 1)
            with zipfile.ZipFile(result['notion']) as archive:
                self.assertIn('notion-import.md', archive.namelist())
                self.assertTrue(any(name.startswith('assets/') for name in archive.namelist()))
            canvas = json.loads(result['canvas'].read_text(encoding='utf-8'))
            self.assertTrue(canvas['nodes'])
            manifest = json.loads((result['folder'] / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['schema'], 'localcrawler.deliverables.v1')
            self.assertEqual(len(manifest['source_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
