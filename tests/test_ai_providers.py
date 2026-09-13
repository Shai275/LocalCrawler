import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai_providers import AIProviderConfig, SUPPORTED_PROVIDERS, validate_provider_config


class AIProviderContractTests(unittest.TestCase):
    def test_supported_provider_settings(self):
        self.assertEqual(SUPPORTED_PROVIDERS, ("basic", "ollama", "openai", "gemini"))
        validate_provider_config(AIProviderConfig())
        validate_provider_config(AIProviderConfig(provider="basic", model=""))

    def test_invalid_provider_settings(self):
        with self.assertRaises(ValueError):
            validate_provider_config(AIProviderConfig(provider="unknown"))
        with self.assertRaises(ValueError):
            validate_provider_config(AIProviderConfig(provider="openai", model=""))
        with self.assertRaises(ValueError):
            validate_provider_config(AIProviderConfig(endpoint="localhost:11434"))


if __name__ == "__main__":
    unittest.main()
