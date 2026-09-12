"""Explicit safe browser launch policy for pinned Crawl4AI 0.9.3."""
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.browser_manager import BrowserManager


class VerifiedBrowserManager(BrowserManager):
    def _build_browser_args(self):
        options = super()._build_browser_args()
        options['args'] = [arg for arg in options['args'] if not arg.startswith((
            '--ignore-certificate-errors', '--no-sandbox', '--disable-ipc-flooding-protection'))]
        options['chromium_sandbox'] = True
        return options


def verified_strategy(config):
    if config.use_managed_browser or config.use_persistent_context or config.cdp_url:
        raise ValueError('Only a fresh dedicated browser is supported by the security policy.')
    config.ignore_https_errors = False
    strategy = AsyncPlaywrightCrawlerStrategy(browser_config=config)
    strategy.browser_manager = VerifiedBrowserManager(config, logger=strategy.logger)
    return strategy
