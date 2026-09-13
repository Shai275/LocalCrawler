"""Scriptable entry point for the same pipeline as the desktop app."""
import argparse
import asyncio
from pathlib import Path
import threading
import os
from engine import crawl_batch, parse_urls
from insights import DEFAULT_MODEL
from ai_providers import AIProviderConfig, CLOUD_PROVIDERS, LABELS, SUPPORTED_PROVIDERS, create_provider

def main():
    parser = argparse.ArgumentParser(description='LocalCrawler: local webpage and video research')
    parser.add_argument('urls', nargs='+', help='HTTP(S) page or YouTube URLs')
    parser.add_argument('--output', type=Path, default=Path('downloads'))
    parser.add_argument('--basic', action='store_true', help='Extract without an AI model')
    parser.add_argument('--provider', choices=SUPPORTED_PROVIDERS, default='ollama')
    parser.add_argument('--model', help='Model ID; required for cloud providers')
    parser.add_argument('--allow-cloud', action='store_true', help='Consent to sending extracted text to the selected cloud API')
    args = parser.parse_args()
    stop = threading.Event()
    def emit(kind, value):
        if kind in ('stage', 'folder'):
            print(value, flush=True)
    try:
        mode = 'basic' if args.basic else args.provider
        model = args.model or (DEFAULT_MODEL if mode == 'ollama' else '')
        key = ''
        if mode in CLOUD_PROVIDERS:
            if not args.allow_cloud:
                raise ValueError('雲端模式會傳送擷取文字並可能計費；同意後加上 --allow-cloud')
            key = os.environ.get('OPENAI_API_KEY' if mode == 'openai' else 'GEMINI_API_KEY', '')
            if not key:
                from credentials import load_key
                key = load_key(mode)
        provider = create_provider(AIProviderConfig(mode, model), api_key=key, cloud_allowed=args.allow_cloud)
        results = asyncio.run(crawl_batch(parse_urls('\n'.join(args.urls)), args.output, 1, 40, '', stop, emit,
                                         summary_mode=mode, model=model, provider=provider))
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + '\n')
    except KeyboardInterrupt:
        return 130
    return 0 if results and all(p.success and (mode == 'basic' or p.summary_mode.startswith(LABELS[mode] + ' · ')) for p in results) else 1

if __name__ == '__main__':
    raise SystemExit(main())
