"""Exercise the real Windows vault under a unique disposable test service."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import credentials


class WindowsVaultTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32' and importlib.util.find_spec('keyring'), 'Windows keyring required')
    def test_real_vault_roundtrip_and_delete(self):
        service = 'LocalCrawler.Test.' + uuid4().hex
        with patch.object(credentials, 'SERVICE', service):
            try:
                self.assertEqual(credentials.load_key('openai'), '')
                credentials.save_key('openai', 'fake-test-value')
                self.assertEqual(credentials.load_key('openai'), 'fake-test-value')
                self.assertEqual(credentials.load_key('gemini'), '')
            finally:
                credentials.delete_key('openai')
            self.assertEqual(credentials.load_key('openai'), '')
