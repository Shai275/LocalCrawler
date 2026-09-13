"""Explicit Windows vault storage. No plaintext or fallback keyring backend."""
import sys
from ai_providers import CLOUD_PROVIDERS, ProviderError

SERVICE = "LocalCrawler.AI"


def _vault():
    if sys.platform != "win32":
        raise ProviderError("此平台請使用僅本次金鑰；安全儲存目前支援 Windows")
    try:
        from keyring.backends.Windows import WinVaultKeyring
        return WinVaultKeyring()
    except Exception:
        raise ProviderError("無法使用 Windows 認證管理員，請重新執行 setup.ps1 或使用僅本次金鑰") from None


def _check(provider):
    if provider not in CLOUD_PROVIDERS:
        raise ProviderError("只有雲端供應商需要 API 金鑰")


def load_key(provider):
    _check(provider)
    try:
        return _vault().get_password(SERVICE, provider) or ""
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("無法讀取已儲存的 API 金鑰") from None


def save_key(provider, key):
    _check(provider)
    if not key.strip():
        raise ProviderError("請先填入 API 金鑰")
    try:
        _vault().set_password(SERVICE, provider, key.strip())
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("API 金鑰儲存失敗，請使用僅本次金鑰") from None


def delete_key(provider):
    _check(provider)
    try:
        vault = _vault()
        if vault.get_password(SERVICE, provider) is not None:
            vault.delete_password(SERVICE, provider)
    except ProviderError:
        raise
    except Exception:
        raise ProviderError("API 金鑰刪除失敗") from None
