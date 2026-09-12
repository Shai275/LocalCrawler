"""Scriptable entry point for the same pipeline as the desktop app."""
import argparse
import asyncio
from pathlib import Path
import threading
from engine import crawl_batch, parse_urls
from insights import DEFAULT_MODEL

def main():
    parser = argparse.ArgumentParser(description='LocalCrawler: local webpage and video research')
    parser.add_argument('urls', nargs='+', help='HTTP(S) page or YouTube URLs')
    parser.add_argument('--output', type=Path, default=Path('downloads'))
    parser.add_argument('--basic', action='store_true', help='Extract without an AI model')
    parser.add_argument('--model', default=DEFAULT_MODEL)
    args = parser.parse_args()
    stop = threading.Event()
    def emit(kind, value):
        if kind in ('stage', 'folder'):
            print(value, flush=True)
    try:
        results = asyncio.run(crawl_batch(parse_urls('\n'.join(args.urls)), args.output, 1, 40, '', stop, emit,
                                         summary_mode='basic' if args.basic else 'ollama', model=args.model))
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + '\n')
    except KeyboardInterrupt:
        return 130
    return 0 if all(p.success and (args.basic or p.summary_mode.startswith('本機 AI')) for p in results) else 1

if __name__ == '__main__':
    raise SystemExit(main())
