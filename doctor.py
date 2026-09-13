"""Read-only local installation diagnostics; never downloads models."""
import asyncio
import importlib.util
import sys

def main():
    print('Python:', sys.version.split()[0])
    missing = []
    for module in ('tkinter', 'crawl4ai', 'playwright', 'youtube_transcript_api', 'yt_dlp', 'faster_whisper', 'httpx', 'keyring', 'opencc'):
        present = importlib.util.find_spec(module) is not None
        print(module + ':', 'OK' if present else 'MISSING')
        if not present:
            missing.append(module)
    try:
        from insights import ollama_models
        print('Ollama models:', ', '.join(asyncio.run(ollama_models())) or 'none')
    except Exception:
        print('Ollama: unavailable. Basic extraction remains available.')
    return bool(missing)

if __name__ == '__main__':
    raise SystemExit(main())
